"""Tests for websocket event subscription."""

import asyncio
import gc
import weakref
from collections.abc import Callable
from types import MappingProxyType, SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.websocket import (
    MAX_PENDING_MESSAGES,
    WebsocketConnection,
    websocket_handlers,
)
from ledfx.events import Event, Events


def take_control(connection: WebsocketConnection) -> dict[str, object]:
    message = connection._control_queue.get_nowait()
    assert message is not None
    return message


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
    assert take_control(conn)["success"] is False
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    await asyncio.sleep(0)
    assert conn._control_queue.qsize() == 1
    conn.clear_subscriptions()
    assert core.events._listeners == {}


async def test_idle_installation_ack_and_legacy_opt_out() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    assert "get_event_capabilities" in websocket_handlers
    connection.get_event_capabilities_handler({"id": 120001})
    assert connection._control_queue.get_nowait() == {
        "id": 120001,
        "type": "result",
        "success": True,
        "result": {"subscription_ack": 1},
    }
    connection.subscribe_event_handler(
        {"id": 120002, "event_type": "never_fires", "ack": True}
    )
    assert core.events.has_listeners("never_fires")
    assert connection._control_queue.get_nowait() == {
        "id": 120002,
        "type": "result",
        "success": True,
        "result": {
            "subscription_id": 120002,
            "event_type": "never_fires",
            "installed": True,
        },
    }
    legacy_requests: list[tuple[int, dict[str, object]]] = [
        (120003, {}),
        (120004, {"ack": False}),
    ]
    for subscription_id, ack in legacy_requests:
        connection.subscribe_event_handler(
            {"id": subscription_id, "event_type": "never_fires", **ack}
        )
    assert connection._control_queue.empty()
    connection.clear_subscriptions()


@pytest.mark.parametrize("ack", [1, "true", None, [], {}])
async def test_invalid_ack_does_not_install(ack: object) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler(
        {"id": 1, "event_type": "never_fires", "ack": ack}
    )
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "success": False,
        "error": {"message": "ack must be a boolean"},
    }
    assert not core.events.has_listeners("never_fires")
    assert connection._listeners == {}
    assert connection._control_queue.empty()


@pytest.mark.parametrize("event_type", ["device_update", "virtual_update"])
async def test_prohibited_event_with_ack_only_returns_error(event_type: str) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler({"id": 1, "event_type": event_type, "ack": True})
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "success": False,
        "error": {
            "message": f"Websocket cannot subscribe to {event_type} events - use visualisation_update instead"
        },
    }
    assert connection._control_queue.empty()
    assert connection._listeners == {}
    assert not core.events.has_listeners(event_type)


@pytest.mark.parametrize(
    "invalid",
    [
        {"ack": 1},
        {"event_type": ""},
        {"event_type": None},
        {"event_type": []},
        {"event_type": 1},
        {"event_filter": []},
        {"event_filter": "invalid"},
    ],
)
async def test_invalid_replacement_preserves_registration(
    invalid: dict[str, object],
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.GRAPH_UPDATE, "ack": True, **invalid}
    )
    assert take_control(connection)["success"] is False
    assert not core.events.has_listeners(Event.GRAPH_UPDATE)
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    await asyncio.sleep(0)
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "type": "event",
        "event_type": Event.VIRTUAL_DIAG,
    }
    assert connection._control_queue.empty()
    connection.clear_subscriptions()


async def test_validated_replacement_ack_and_immediate_event() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    connection.subscribe_event_handler(
        {
            "id": 1,
            "event_type": Event.GRAPH_UPDATE,
            "ack": True,
            "event_filter": MappingProxyType({"event_type": Event.GRAPH_UPDATE}),
        }
    )
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    core.events.fire_event(Event(Event.GRAPH_UPDATE))
    await asyncio.sleep(0)
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "type": "result",
        "success": True,
        "result": {
            "subscription_id": 1,
            "event_type": Event.GRAPH_UPDATE,
            "installed": True,
        },
    }
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "type": "event",
        "event_type": Event.GRAPH_UPDATE,
    }
    assert connection._control_queue.empty()
    assert len(core.events._listeners[Event.GRAPH_UPDATE]) == 1
    assert not core.events.has_listeners(Event.VIRTUAL_DIAG)
    connection.clear_subscriptions()


@pytest.mark.parametrize("error_type", [TypeError, ValueError])
@pytest.mark.parametrize("replacement", [False, True])
async def test_registration_failure_has_no_installed_reply(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    replacement: bool,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    if replacement:
        connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})

    def fail_registration(*args: object, **kwargs: object) -> Callable[[], None]:
        raise error_type("registration rejected")

    monkeypatch.setattr(core.events, "add_listener", fail_registration)
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.GRAPH_UPDATE, "ack": True}
    )
    assert connection._control_queue.get_nowait() == {
        "id": 1,
        "success": False,
        "error": {"message": "registration rejected"},
    }
    assert connection._control_queue.empty()
    assert connection._listeners == {}
    assert core.events._listeners == {}


class HeldCloseSocket:
    def __init__(self) -> None:
        self.closed = False
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()
        self.close_calls: list[tuple[int, bytes]] = []
        self.messages: list[object] = []

    async def close(self, *, code: int, message: bytes) -> bool:
        self.close_calls.append((code, message))
        self.close_started.set()
        await self.release_close.wait()
        self.closed = True
        return True

    async def send_json(self, message: object, *, dumps: object) -> None:
        self.messages.append(message)


@pytest.mark.parametrize("capability", [False, True])
async def test_full_installation_reply_queue_revokes_and_closes_once(
    capability: bool,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldCloseSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    sender = asyncio.create_task(connection._sender())
    await asyncio.sleep(0)
    assert not sender.done()
    for request_id in range(MAX_PENDING_MESSAGES):
        connection._control_queue.put_nowait(
            {"id": request_id, "type": "result", "success": True, "result": {}}
        )
    connection._has_work.clear()
    if capability:
        connection.get_event_capabilities_handler({"id": 2})
    else:
        connection.subscribe_event_handler(
            {"id": 2, "event_type": Event.GRAPH_UPDATE, "ack": True}
        )
    assert connection._listeners == {}
    assert core.events._listeners == {}
    assert connection._has_work.is_set()
    assert connection._control_queue.qsize() == MAX_PENDING_MESSAGES
    task = connection._installation_close_task
    assert task is not None
    await socket.close_started.wait()
    connection.subscribe_event_handler(
        {"id": 3, "event_type": "new_event", "ack": True}
    )
    connection.get_event_capabilities_handler({"id": 4})
    core.events.fire_event(Event(Event.GRAPH_UPDATE))
    await asyncio.sleep(0)
    assert sender.done()
    assert socket.messages == []
    assert connection._installation_close_task is task
    assert connection._listeners == {}
    assert core.events._listeners == {}
    assert socket.close_calls == [(1013, b"control backlog; reconnect and resync")]
    socket.release_close.set()
    await task
    await sender
    assert socket.closed
    assert connection._control_queue.qsize() == MAX_PENDING_MESSAGES


async def test_installation_results_survive_unsubscribe() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.get_event_capabilities_handler({"id": 10})
    connection.subscribe_event_handler(
        {"id": 1, "event_type": "never_fires", "ack": True}
    )
    connection.unsubscribe_event_handler({"id": 1})
    assert take_control(connection)["id"] == 10
    assert take_control(connection)["id"] == 1
    assert connection._control_queue.empty()
    assert core.events._listeners == {}


async def test_replacement_revokes_deferred_callbacks_and_pending_events() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.VIRTUAL_DIAG, "ack": True}
    )
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    await asyncio.sleep(0)
    connection.subscribe_event_handler({"id": 2, "event_type": Event.VIRTUAL_DIAG})
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.GRAPH_UPDATE, "ack": True}
    )
    await asyncio.sleep(0)
    assert take_control(connection)["result"] == {
        "subscription_id": 1,
        "event_type": Event.VIRTUAL_DIAG,
        "installed": True,
    }
    assert take_control(connection)["result"] == {
        "subscription_id": 1,
        "event_type": Event.GRAPH_UPDATE,
        "installed": True,
    }
    assert connection._control_queue.get_nowait() == {
        "id": 2,
        "type": "event",
        "event_type": Event.VIRTUAL_DIAG,
    }
    assert connection._control_queue.empty()
    core.events.fire_event(Event(Event.GRAPH_UPDATE))
    await asyncio.sleep(0)
    connection.unsubscribe_event_handler({"id": 1})
    assert connection._control_queue.empty()
    connection.clear_subscriptions()


async def test_reply_failure_rejects_already_deferred_events() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    core.events.fire_event(Event(Event.VIRTUAL_DIAG))
    for request_id in range(MAX_PENDING_MESSAGES):
        connection._control_queue.put_nowait(
            {"id": request_id, "type": "result", "success": True, "result": {}}
        )
    connection.get_event_capabilities_handler({"id": 1000})
    task = connection._installation_close_task
    assert task is not None
    await task
    assert connection._control_queue.qsize() == MAX_PENDING_MESSAGES
    assert connection._listeners == {}
    assert core.events._listeners == {}


async def test_wire_results_route_by_id_and_disconnect_releases_owner() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    finished = asyncio.Event()

    async def handle(request: web.Request) -> web.StreamResponse:
        try:
            return await connection.handle(request)
        finally:
            finished.set()

    app = web.Application()
    app.router.add_get("/websocket", handle)
    async with TestClient(TestServer(app)) as client:
        socket = await client.ws_connect("/websocket")
        initial = await socket.receive_json()
        assert initial["event_type"] == "client_id"
        await socket.send_json({"id": 10, "type": "get_event_capabilities"})
        assert await socket.receive_json() == {
            "id": 10,
            "type": "result",
            "success": True,
            "result": {"subscription_ack": 1},
        }
        await socket.send_json(
            {
                "id": 1,
                "type": "subscribe_event",
                "event_type": "never_fires",
                "ack": True,
            }
        )
        assert await socket.receive_json() == {
            "id": 1,
            "type": "result",
            "success": True,
            "result": {
                "subscription_id": 1,
                "event_type": "never_fires",
                "installed": True,
            },
        }
        core.events.fire_event(Event("never_fires"))
        assert await socket.receive_json() == {
            "id": 1,
            "type": "event",
            "event_type": "never_fires",
        }
        await socket.close()
        await asyncio.wait_for(finished.wait(), timeout=5)
    assert connection._listeners == {}
    assert core.events._listeners == {}
    assert connection.uid not in WebsocketConnection.ip_uid_map


async def test_disconnect_cancels_and_awaits_pending_installation_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    finished = asyncio.Event()
    close_started = asyncio.Event()
    close_cancelled = asyncio.Event()
    original_close = web.WebSocketResponse.close

    async def hold_failure_close(
        socket: web.WebSocketResponse,
        *,
        code: int = 1000,
        message: bytes = b"",
        drain: bool = True,
    ) -> bool:
        if code == 1013:
            close_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                close_cancelled.set()
        return await original_close(socket, code=code, message=message, drain=drain)

    monkeypatch.setattr(web.WebSocketResponse, "close", hold_failure_close)

    async def handle(request: web.Request) -> web.StreamResponse:
        try:
            return await connection.handle(request)
        finally:
            finished.set()

    app = web.Application()
    app.router.add_get("/websocket", handle)
    async with TestClient(TestServer(app)) as client:
        socket = await client.ws_connect("/websocket")
        assert (await socket.receive()).type == WSMsgType.TEXT
        connection.subscribe_event_handler({"id": 1, "event_type": "never_fires"})
        for request_id in range(MAX_PENDING_MESSAGES):
            connection._control_queue.put_nowait(
                {"id": request_id, "type": "result", "success": True, "result": {}}
            )
        connection.get_event_capabilities_handler({"id": 2})
        await asyncio.wait_for(close_started.wait(), timeout=5)
        task = connection._installation_close_task
        assert task is not None
        await socket.close()
        await asyncio.wait_for(finished.wait(), timeout=5)
    assert close_cancelled.is_set()
    assert task.done()
    assert task.cancelled()
    sender_task = connection._sender_task
    assert sender_task is not None
    assert sender_task.done()
    assert connection._listeners == {}
    assert core.events._listeners == {}


async def test_installation_close_error_is_observed(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldCloseSocket()

    async def fail_close(*, code: int, message: bytes) -> bool:
        raise RuntimeError("close failed")

    monkeypatch.setattr(socket, "close", fail_close)
    connection._socket = cast(web.WebSocketResponse, socket)
    connection.subscribe_event_handler({"id": 1, "event_type": "never_fires"})
    for request_id in range(MAX_PENDING_MESSAGES):
        connection._control_queue.put_nowait(
            {"id": request_id, "type": "result", "success": True, "result": {}}
        )
    connection.get_event_capabilities_handler({"id": 2})
    task = connection._installation_close_task
    assert task is not None
    await asyncio.gather(task, return_exceptions=True)
    assert (
        "Unable to close websocket after installation reply failure: close failed"
        in caplog.text
    )
    assert connection._closed
    assert connection._listeners == {}
    assert core.events._listeners == {}
