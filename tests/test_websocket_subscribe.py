"""Tests for websocket event subscription."""

import asyncio
import gc
import weakref
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ledfx.api.websocket import WebsocketConnection
from ledfx.events import Event, Events


@pytest.mark.parametrize("event_type", ["device_update", "virtual_update"])
def test_raw_pixel_events_are_not_subscribable(event_type: str) -> None:
    # Raw pixel events carry an ndarray every frame; clients must use
    # visualisation_update, which is rate limited and JSON safe.
    ledfx = MagicMock()
    conn = WebsocketConnection(ledfx)
    conn.send_error = MagicMock()

    conn.subscribe_event_handler(
        {"id": 1, "type": "subscribe_event", "event_type": event_type}
    )

    ledfx.events.add_listener.assert_not_called()
    conn.send_error.assert_called_once_with(
        1,
        f"Websocket cannot subscribe to {event_type} events - "
        "use visualisation_update instead",
    )


async def test_duplicate_subscription_id_delivers_once_and_is_removable() -> None:

    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    conn = WebsocketConnection(core)
    for _ in range(100):
        conn.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})

    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    await asyncio.sleep(0)
    assert conn._control_queue.qsize() == 1
    conn.unsubscribe_event_handler({"id": 1})
    assert core.events._listeners == {}


async def test_reused_subscription_id_replaces_event_and_filter() -> None:

    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    conn = WebsocketConnection(core)
    conn.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    conn.subscribe_event_handler(
        {
            "id": 1,
            "event_type": Event.GRAPH_UPDATE,
            "event_filter": {"event_type": "will-not-match"},
        }
    )
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    core.events.fire_event(Event(Event.GRAPH_UPDATE))
    await asyncio.sleep(0)
    assert conn._control_queue.empty()

    conn.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    core.events.fire_event(Event(Event.GRAPH_UPDATE))
    await asyncio.sleep(0)
    assert conn._control_queue.qsize() == 1
    conn.clear_subscriptions()
    assert core.events._listeners == {}


async def test_disconnect_cleanup_releases_resubscribed_connection() -> None:

    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    conn = WebsocketConnection(core)
    reference = weakref.ref(conn)
    for _ in range(100):
        conn.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    conn.subscribe_event_handler({"id": 2, "event_type": Event.GRAPH_UPDATE})
    conn.clear_subscriptions()
    conn.clear_subscriptions()
    assert conn._listeners == {}
    del conn
    gc.collect()
    assert reference() is None
    assert core.events._listeners == {}


async def test_rejected_replacement_preserves_existing_subscription() -> None:

    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    conn = WebsocketConnection(core)
    conn.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    conn.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_UPDATE})
    assert conn._control_queue.get_nowait()["success"] is False
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    await asyncio.sleep(0)
    assert conn._control_queue.qsize() == 1
    conn.clear_subscriptions()
    assert core.events._listeners == {}
