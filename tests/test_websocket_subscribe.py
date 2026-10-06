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
from typing_extensions import override

import ledfx.api.websocket as websocket_module
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
        self.messages: list[dict[str, object]] = []

    async def close(self, *, code: int, message: bytes) -> bool:
        self.close_calls.append((code, message))
        self.close_started.set()
        await self.release_close.wait()
        self.closed = True
        return True

    async def send_json(self, message: dict[str, object], *, dumps: object) -> None:
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


@pytest.mark.parametrize(
    ("malformed", "error_id"),
    [
        ({"id": 77}, 77),
        ({"id": "77"}, "77"),
        ({"id": "invalid", "type": "get_event_capabilities"}, "invalid"),
        ({"type": "get_event_capabilities"}, None),
        ([], None),
        (42, None),
    ],
    ids=[
        "missing-type",
        "raw-string-id",
        "invalid-id",
        "missing-id",
        "array",
        "scalar",
    ],
)
async def test_wire_malformed_request_error_precedes_close(
    malformed: object, error_id: object
) -> None:
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
        assert (await socket.receive_json())["event_type"] == "client_id"
        # Valid IDs still coerce, and invalid later envelopes must never reuse one.
        await socket.send_json({"id": "10", "type": "get_event_capabilities"})
        assert await socket.receive_json() == {
            "id": 10,
            "type": "result",
            "success": True,
            "result": {"subscription_ack": 1},
        }
        await socket.send_json(malformed)
        if error_id is not None:
            assert await socket.receive_json() == {
                "id": error_id,
                "success": False,
                "error": {"message": "Invalid message format."},
            }
        assert (await socket.receive()).type == WSMsgType.CLOSE
        await asyncio.wait_for(finished.wait(), timeout=5)
    sender = connection._sender_task
    assert sender is not None and sender.done()
    if error_id is not None:
        assert not sender.cancelled()
    assert connection._listeners == {}
    assert core.events._listeners == {}


@pytest.mark.parametrize(
    "boundary",
    [
        "blocked",
        "unwritable",
        "force-close",
        "shutdown",
        "readiness-failure",
        "queued-error-overflow",
    ],
)
async def test_terminal_error_reply_cleanup_at_write_boundary(
    boundary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    finished = asyncio.Event()
    error_started = asyncio.Event()
    error_cancelled = asyncio.Event()
    failure_close_cancelled = asyncio.Event()
    close_calls: list[tuple[int, bytes]] = []
    writes: list[dict[str, object]] = []
    original_send_json = web.WebSocketResponse.send_json
    original_close = web.WebSocketResponse.close
    # Interruptions must complete independently of the long normal grace.
    monkeypatch.setattr(
        websocket_module,
        "FINAL_ERROR_REPLY_TIMEOUT",
        0.05 if boundary == "blocked" else 60.0,
        raising=False,
    )

    async def hold_error(
        socket: web.WebSocketResponse,
        data: dict[str, object],
        *,
        compress: int | None = None,
        dumps: Callable[[object], str] = websocket_module.dumps,
    ) -> None:
        writes.append(data)
        held_id = 76 if boundary == "queued-error-overflow" else 77
        if "error" in data and data["id"] == held_id:
            error_started.set()
            if boundary == "unwritable":
                raise ConnectionResetError("transport no longer writable")
            try:
                await asyncio.Event().wait()
            finally:
                error_cancelled.set()
        await original_send_json(socket, data, compress=compress, dumps=dumps)

    async def hold_failure_close(
        socket: web.WebSocketResponse,
        *,
        code: int = 1000,
        message: bytes = b"",
        drain: bool = True,
    ) -> bool:
        if code == 1013:
            close_calls.append((code, message))
            try:
                await asyncio.Event().wait()
            finally:
                failure_close_cancelled.set()
        return await original_close(socket, code=code, message=message, drain=drain)

    monkeypatch.setattr(web.WebSocketResponse, "send_json", hold_error)
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
        assert (await socket.receive_json())["event_type"] == "client_id"
        await socket.send_json(
            {
                "id": 1,
                "type": "subscribe_event",
                "event_type": "never_fires",
                "ack": True,
            }
        )
        assert (await socket.receive_json())["result"] == {
            "subscription_id": 1,
            "event_type": "never_fires",
            "installed": True,
        }
        # The final error must use the same writer after existing FIFO replies.
        await socket.send_json({"id": 76, "type": "unknown-command"})
        await socket.send_json({"id": 77})
        if boundary != "queued-error-overflow":
            assert await socket.receive_json() == {
                "id": 76,
                "success": False,
                "error": {"message": "Unknown command type."},
            }
        await asyncio.wait_for(error_started.wait(), timeout=1)
        if boundary == "queued-error-overflow":

            async def wait_for_terminal_reply() -> None:
                while connection._receiver_error_reply is None:
                    await asyncio.sleep(0)

            await asyncio.wait_for(wait_for_terminal_reply(), timeout=1)
        assert connection._listeners == {}
        assert not core.events.has_listeners("never_fires")
        if boundary == "force-close":
            connection.close()
        elif boundary == "shutdown":
            core.events.fire_event(Event(Event.LEDFX_SHUTDOWN))
        elif boundary == "queued-error-overflow":
            assert connection._control_queue.qsize() == 1
            for _ in range(MAX_PENDING_MESSAGES - 1):
                connection.send_event(99, Event(Event.GRAPH_UPDATE))
            assert connection._control_queue.full()
            connection.send_event(99, Event(Event.GRAPH_UPDATE))
        elif boundary == "readiness-failure":
            for request_id in range(MAX_PENDING_MESSAGES):
                connection._control_queue.put_nowait(
                    {"id": request_id, "type": "result"}
                )
            connection.get_event_capabilities_handler({"id": 1000})
        assert (
            await asyncio.wait_for(socket.receive(), timeout=1)
        ).type == WSMsgType.CLOSE
        await asyncio.wait_for(finished.wait(), timeout=1)
    assert [message.get("id") for message in writes] == (
        [None, 1, 76] if boundary == "queued-error-overflow" else [None, 1, 76, 77]
    )
    assert error_cancelled.is_set() == (boundary != "unwritable")
    sender = connection._sender_task
    assert sender is not None and sender.done()
    assert sender.cancelled() == (boundary != "unwritable")
    assert core.events._listeners == {}
    if boundary in ("readiness-failure", "queued-error-overflow"):
        assert close_calls == [(1013, b"control backlog; reconnect and resync")]
        task = connection._installation_close_task
        assert task is not None and task.done() and task.cancelled()
        assert failure_close_cancelled.is_set()


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


class HeldFirstWriteSocket(HeldCloseSocket):
    def __init__(self) -> None:
        super().__init__()
        self.first_write_started = asyncio.Event()
        self.release_first_write = asyncio.Event()
        self.started: list[dict[str, object]] = []
        self.completed: list[dict[str, object]] = []

    @override
    async def send_json(self, message: dict[str, object], *, dumps: object) -> None:
        self.started.append(message)
        if len(self.started) == 1:
            self.first_write_started.set()
            await self.release_first_write.wait()
        self.completed.append(message)


@pytest.mark.parametrize(
    "capability", [False, True], ids=["installed-ack", "capability"]
)
@pytest.mark.parametrize("held_write", [False, True], ids=["queued", "held-write"])
async def test_ordinary_overflow_protects_pending_results_and_closes_once(
    capability: bool,
    held_write: bool,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldFirstWriteSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.VIRTUAL_DIAG})
    first: dict[str, object] = {
        "id": 99,
        "type": "event",
        "event_type": Event.GRAPH_UPDATE,
    }
    sender: asyncio.Task[None] | None = None
    try:
        if held_write:
            connection.send(first)
            sender = connection._sender_task = asyncio.create_task(connection._sender())
            await asyncio.wait_for(socket.first_write_started.wait(), timeout=1)
        if capability:
            connection.get_event_capabilities_handler({"id": 2})
        else:
            connection.subscribe_event_handler(
                {"id": 2, "event_type": "never_fires", "ack": True}
            )
        for _ in range(MAX_PENDING_MESSAGES - 1):
            connection.send_event(99, Event(Event.GRAPH_UPDATE))
        assert connection._control_queue.full()
        connection.send_event(99, Event(Event.GRAPH_UPDATE))
        if sender is None:
            sender = connection._sender_task = asyncio.create_task(connection._sender())
        await asyncio.wait_for(socket.close_started.wait(), timeout=1)
        task = connection._installation_close_task
        assert task is not None
        assert connection._listeners == {}
        assert core.events._listeners == {}
        assert connection._control_queue.full()
        for _ in range(3):
            connection.send_event(99, Event(Event.GRAPH_UPDATE))
        connection.get_event_capabilities_handler({"id": 3})
        assert connection._installation_close_task is task
        assert socket.close_calls == [(1013, b"control backlog; reconnect and resync")]
        socket.release_first_write.set()
        await asyncio.wait_for(sender, timeout=1)
        assert socket.started == ([first] if held_write else [])
        assert socket.completed == socket.started
        socket.release_close.set()
        await asyncio.wait_for(task, timeout=1)
        assert task.done() and not task.cancelled() and task.exception() is None
        assert socket.closed and connection._closed
        assert connection._control_queue.full()
        result = take_control(connection)
        assert result["id"] == 2 and result["type"] == "result"
        assert result["result"] == (
            {"subscription_ack": 1}
            if capability
            else {
                "subscription_id": 2,
                "event_type": "never_fires",
                "installed": True,
            }
        )
        assert socket.close_calls == [(1013, b"control backlog; reconnect and resync")]
    finally:
        socket.release_first_write.set()
        socket.release_close.set()
        connection.close()
        tasks = [
            task
            for task in (sender, connection._installation_close_task)
            if task is not None
        ]
        await asyncio.gather(*tasks, return_exceptions=True)


class NonStringProtocolType:
    def __eq__(self, other: object) -> bool:
        raise AssertionError("arbitrary protocol values must not be compared")


async def test_ordinary_only_overflow_keeps_legacy_live_queue_replacement() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldCloseSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    # An equal-looking error is not the receiver-owned terminal marker.
    connection._receiver_error_reply = {"id": 77, "success": False}
    connection.send(dict(connection._receiver_error_reply))
    connection.send({"type": NonStringProtocolType()})
    for _ in range(MAX_PENDING_MESSAGES - 2):
        connection.send_event(99, Event(Event.GRAPH_UPDATE))
    latest: dict[str, object] = {
        "id": 100,
        "type": "event",
        "event_type": Event.GRAPH_UPDATE,
    }
    connection.send(latest)
    assert connection._control_queue.qsize() == 1
    connection.send(None)
    sender = asyncio.create_task(connection._sender())
    await asyncio.wait_for(sender, timeout=1)
    assert socket.messages == [latest]
    assert not socket.closed and not connection._closed
    assert socket.close_calls == []
    assert connection._installation_close_task is None


async def test_pending_results_keep_fifo_before_capacity() -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldFirstWriteSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    first: dict[str, object] = {
        "id": 99,
        "type": "event",
        "event_type": Event.GRAPH_UPDATE,
    }
    connection.send(first)
    sender = connection._sender_task = asyncio.create_task(connection._sender())
    try:
        await asyncio.wait_for(socket.first_write_started.wait(), timeout=1)
        connection.get_event_capabilities_handler({"id": 10})
        connection.subscribe_event_handler(
            {"id": 11, "event_type": "never_fires", "ack": True}
        )
        connection.send_event(99, Event(Event.GRAPH_UPDATE))
        connection.send(None)
        socket.release_first_write.set()
        await asyncio.wait_for(sender, timeout=1)
        assert [message["id"] for message in socket.completed] == [99, 10, 11, 99]
        assert socket.completed[1] == {
            "id": 10,
            "type": "result",
            "success": True,
            "result": {"subscription_ack": 1},
        }
        assert socket.completed[2] == {
            "id": 11,
            "type": "result",
            "success": True,
            "result": {
                "subscription_id": 11,
                "event_type": "never_fires",
                "installed": True,
            },
        }
        assert socket.started == socket.completed
        assert socket.close_calls == []
    finally:
        socket.release_first_write.set()
        connection.close()
        await asyncio.gather(sender, return_exceptions=True)


class PreviewEvent(Event):
    def __init__(self, vis_id: str) -> None:
        super().__init__(Event.VISUALISATION_UPDATE)
        self.vis_id = vis_id


@pytest.mark.parametrize("replacement", [False, True], ids=["unsubscribe", "replace"])
async def test_revoked_second_preview_never_starts_after_held_first_write(
    replacement: bool,
) -> None:
    core = SimpleNamespace(loop=asyncio.get_running_loop())
    core.events = Events(core)
    connection = WebsocketConnection(core)
    socket = HeldFirstWriteSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    for subscription_id, vis_id in ((1, "first"), (2, "second")):
        connection.subscribe_event_handler(
            {
                "id": subscription_id,
                "event_type": Event.VISUALISATION_UPDATE,
                "event_filter": {"vis_id": vis_id},
            }
        )
    core.events.fire_event(PreviewEvent("first"))
    core.events.fire_event(PreviewEvent("second"))
    await asyncio.sleep(0)
    sender = asyncio.create_task(connection._sender())
    try:
        await asyncio.wait_for(socket.first_write_started.wait(), timeout=5)
        assert socket.started == [
            {
                "id": 1,
                "type": "event",
                "event_type": Event.VISUALISATION_UPDATE,
                "vis_id": "first",
            }
        ]
        assert socket.completed == []
        connection.get_event_capabilities_handler({"id": 90})
        if replacement:
            connection.subscribe_event_handler(
                {
                    "id": 2,
                    "event_type": Event.GRAPH_UPDATE,
                    "ack": True,
                }
            )
        else:
            connection.unsubscribe_event_handler({"id": 2})
        # A replenished first source must not extend this preview pass ahead
        # of the capability/installation replies and the shutdown sentinel.
        core.events.fire_event(PreviewEvent("first"))
        await asyncio.sleep(0)
        connection.send(None)
        socket.release_first_write.set()
        await asyncio.wait_for(sender, timeout=5)
        expected: list[dict[str, object]] = [
            {
                "id": 1,
                "type": "event",
                "event_type": Event.VISUALISATION_UPDATE,
                "vis_id": "first",
            },
            {
                "id": 90,
                "type": "result",
                "success": True,
                "result": {"subscription_ack": 1},
            },
        ]
        if replacement:
            expected.append(
                {
                    "id": 2,
                    "type": "result",
                    "success": True,
                    "result": {
                        "subscription_id": 2,
                        "event_type": Event.GRAPH_UPDATE,
                        "installed": True,
                    },
                }
            )
        assert socket.started == expected
        assert socket.completed == expected
        assert connection._vis_slots == {"first": expected[0]}
    finally:
        socket.release_first_write.set()
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        connection.clear_subscriptions()
