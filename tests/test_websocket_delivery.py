"""Connection ownership, bounded admission, and the socket write boundary."""

import asyncio
from typing import cast

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.websocket import WebsocketConnection
from ledfx.events import Event, Events, GeneralDiagEvent, VisualisationUpdateEvent


class Core:
    def __init__(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.events = Events(self)


class RecordingSocket:
    def __init__(self, *, held: bool = False, held_close: bool = False) -> None:
        self.closed = False
        self.messages: list[dict[str, object]] = []
        self.started: list[dict[str, object]] = []
        self.write_started = asyncio.Event()
        self.release = asyncio.Event()
        self.close_started = asyncio.Event()
        self.release_close = asyncio.Event()
        self.closes: list[tuple[int, bytes]] = []
        if not held:
            self.release.set()
        if not held_close:
            self.release_close.set()

    async def send_json(self, message: dict[str, object], *, dumps: object) -> None:
        self.started.append(message)
        self.write_started.set()
        await self.release.wait()
        self.messages.append(message)

    async def close(self, *, code: int = 1000, message: bytes = b"") -> bool:
        self.closes.append((code, message))
        self.close_started.set()
        await self.release_close.wait()
        self.closed = True
        return True


class EntityEvent(Event):
    def __init__(self, event_type: str, entity: object, value: int = 0) -> None:
        super().__init__(event_type)
        self.graph_id = entity
        self.virtual_id = entity
        self.value = value


def connection_with_socket(
    *, held: bool = False, held_close: bool = False
) -> tuple[Core, WebsocketConnection, RecordingSocket]:
    core = Core()
    connection = WebsocketConnection(core)
    socket = RecordingSocket(held=held, held_close=held_close)
    connection._socket = cast(web.WebSocketResponse, socket)
    return core, connection, socket


async def drain(
    connection: WebsocketConnection, socket: RecordingSocket, count: int
) -> None:
    sender = asyncio.create_task(connection._sender())
    try:

        async def wait_for_messages() -> None:
            while len(socket.messages) < count:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait_for_messages(), timeout=1)
    finally:
        connection.close()
        await asyncio.gather(sender, return_exceptions=True)


async def test_two_subscription_ids_and_preview_kinds_are_not_collapsed() -> None:
    core, connection, socket = connection_with_socket()
    for subscription_id, kind in ((100000, False), (100001, False), (100002, True)):
        connection.subscribe_event_handler(
            {
                "id": subscription_id,
                "event_type": Event.VISUALISATION_UPDATE,
                "event_filter": {"vis_id": "same", "is_device": kind},
            }
        )
    core.events.fire_event(VisualisationUpdateEvent(False, "same", "AQID", (1, 1)))
    core.events.fire_event(VisualisationUpdateEvent(True, "same", "BAUG", (1, 1)))
    await asyncio.sleep(0)
    await drain(connection, socket, 3)
    assert {(m["id"], m["is_device"], m["pixels"]) for m in socket.messages} == {
        (100000, False, "AQID"),
        (100001, False, "AQID"),
        (100002, True, "BAUG"),
    }


@pytest.mark.parametrize(
    "event_type", ["ordinary", Event.GRAPH_UPDATE, Event.GENERAL_DIAG]
)
@pytest.mark.parametrize("replace", [False, True])
async def test_selected_owned_delivery_rechecked_before_write(
    event_type: str, replace: bool
) -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": event_type})
    event = (
        GeneralDiagEvent("log")
        if event_type == Event.GENERAL_DIAG
        else EntityEvent(event_type, "x")
    )
    core.events.fire_event(event)
    await asyncio.sleep(0)
    selected = connection._select_delivery()
    assert selected is not None
    if replace:
        connection.subscribe_event_handler({"id": 1, "event_type": event_type})
    else:
        connection.unsubscribe_event_handler({"id": 1})
    await connection._write_delivery(selected)
    assert socket.started == []
    connection.close()


async def test_write_already_started_can_finish_but_next_owned_delivery_is_purged() -> (
    None
):
    core, connection, socket = connection_with_socket(held=True)
    connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
    core.events.fire_event(EntityEvent("ordinary", "x", 1))
    core.events.fire_event(EntityEvent("ordinary", "x", 2))
    await asyncio.sleep(0)
    sender = asyncio.create_task(connection._sender())
    try:
        await asyncio.wait_for(socket.write_started.wait(), timeout=1)
        connection.unsubscribe_event_handler({"id": 1})
        socket.release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert [m["value"] for m in socket.messages] == [1]
        assert connection._select_delivery() is None
    finally:
        connection.close()
        await asyncio.gather(sender, return_exceptions=True)


async def test_replacement_purges_old_generation_and_preserves_control_replies() -> (
    None
):
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.GRAPH_UPDATE, "ack": True}
    )
    core.events.fire_event(EntityEvent(Event.GRAPH_UPDATE, "x", 1))
    await asyncio.sleep(0)
    connection.subscribe_event_handler(
        {"id": 1, "event_type": Event.GRAPH_UPDATE, "ack": True}
    )
    core.events.fire_event(EntityEvent(Event.GRAPH_UPDATE, "x", 2))
    await asyncio.sleep(0)
    await drain(connection, socket, 3)
    assert [m["type"] for m in socket.messages] == ["result", "result", "event"]
    assert socket.messages[-1]["value"] == 2


@pytest.mark.parametrize("stream", [False, True])
async def test_distinct_backlog_overflow_closes_once_and_rejects_further_admission(
    stream: bool,
) -> None:
    core, connection, socket = connection_with_socket(held_close=True)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    for index in range(256):
        if stream:
            connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, str(index)))
        else:
            connection.send({"id": index})
    if stream:
        connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "0", 2))
    assert not socket.closes
    if stream:
        connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "overflow"))
    else:
        connection.send({"id": 256})
    await asyncio.wait_for(socket.close_started.wait(), timeout=1)
    for index in range(300):
        connection.send({"id": index})
        connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, str(index)))
    sender = asyncio.create_task(connection._sender())
    await asyncio.wait_for(sender, timeout=1)
    assert connection._select_delivery() is None
    assert connection._listeners == {} and core.events._listeners == {}
    assert socket.messages == []
    assert socket.closes == [
        (
            1013,
            ("stream" if stream else "control").encode()
            + b" backlog; reconnect and resync",
        )
    ]
    socket.release_close.set()
    close_task = connection._close_task
    assert close_task is not None
    await asyncio.wait_for(close_task, timeout=1)
    assert socket.closed


async def test_full_control_queue_close_wakes_without_a_sentinel() -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
    for index in range(256):
        connection.send({"id": index})
    connection.close()
    connection.close()
    await asyncio.wait_for(connection._sender(), timeout=1)
    assert connection._select_delivery() is None
    assert connection._listeners == {} and core.events._listeners == {}
    assert socket.started == []


async def test_controls_keep_fifo_and_yield_to_latest_and_text_after_32() -> None:
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    connection.subscribe_event_handler({"id": 2, "event_type": Event.GENERAL_DIAG})
    for index in range(96):
        connection.send({"id": index})
    connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "x"))
    connection.send_event(2, GeneralDiagEvent("log"))
    await drain(connection, socket, 98)
    assert [m["id"] for m in socket.messages if "type" not in m] == list(range(96))
    assert socket.messages[32]["event_type"] == Event.GRAPH_UPDATE
    assert socket.messages[65]["event_type"] == Event.GENERAL_DIAG


async def test_control_only_batch_yields_to_the_loop() -> None:
    _, connection, socket = connection_with_socket()
    for index in range(96):
        connection.send({"id": index})
    observed: list[int] = []
    sender = asyncio.create_task(connection._sender())
    asyncio.get_running_loop().call_soon(lambda: observed.append(len(socket.messages)))
    try:

        async def wait() -> None:
            while len(socket.messages) < 96:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait(), timeout=1)
        assert observed == [32]
    finally:
        connection.close()
        await asyncio.gather(sender, return_exceptions=True)


async def test_latest_replacement_rotates_without_starving_cold_source() -> None:
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "hot", 1))
    connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "cold", 1))
    for value in range(2, 100):
        connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "hot", value))
    await drain(connection, socket, 2)
    assert [(m["graph_id"], m["value"]) for m in socket.messages] == [
        ("hot", 99),
        ("cold", 1),
    ]


class InvalidMetadata:
    def __hash__(self) -> int:
        raise AssertionError("malformed metadata must never be hashed")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("malformed metadata must never be compared")


@pytest.mark.parametrize(
    "event_type", [Event.VISUALISATION_UPDATE, Event.GRAPH_UPDATE, Event.VIRTUAL_DIAG]
)
async def test_malformed_sample_metadata_cannot_create_slots(event_type: str) -> None:
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": event_type})
    for _ in range(300):
        connection.send_event(1, EntityEvent(event_type, InvalidMetadata()))
    assert connection._select_delivery() is None
    assert not socket.closes
    connection.close()


async def test_text_flood_is_bounded_and_reports_aggregate_loss_before_retained_records() -> (
    None
):
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    for index in range(1000):
        connection.send_event(1, GeneralDiagEvent(str(index), scroll=True))
    assert len(connection._text_queue) == 100
    await drain(connection, socket, 101)
    assert socket.messages[0] == {
        "id": 1,
        "type": "event",
        "event_type": Event.GENERAL_DIAG,
        "debug": "Dropped 900 diagnostic messages",
        "scroll": True,
    }
    assert [m["debug"] for m in socket.messages[1:]] == [
        str(index) for index in range(900, 1000)
    ]


async def test_selected_drop_summary_revocation_retains_loss_until_current_owner_writes() -> (
    None
):
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    for index in range(101):
        connection.send_event(1, GeneralDiagEvent(str(index)))
    selected = connection._select_delivery()
    assert (
        selected is not None
        and selected.message["debug"] == "Dropped 1 diagnostic messages"
    )
    connection.unsubscribe_event_handler({"id": 1})
    await connection._write_delivery(selected)
    assert socket.started == [] and not connection._text_queue
    connection.subscribe_event_handler({"id": 2, "event_type": Event.GENERAL_DIAG})
    connection.send_event(2, GeneralDiagEvent("new"))
    await drain(connection, socket, 2)
    assert [m["id"] for m in socket.messages] == [2, 2]
    assert socket.messages[0]["debug"] == "Dropped 1 diagnostic messages"


async def test_sender_socket_exception_finalizes_and_revokes_all_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
    connection.send({"id": 2})

    async def fail_write(message: dict[str, object], *, dumps: object) -> None:
        raise ConnectionResetError("socket failed")

    monkeypatch.setattr(socket, "send_json", fail_write)
    await connection._sender()
    assert connection._listeners == {} and core.events._listeners == {}
    assert connection._select_delivery() is None


async def test_deep_invalid_filter_preserves_old_subscription() -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
    connection.subscribe_event_handler(
        {"id": 1, "event_type": "other", "event_filter": {"vis_id": 42}}
    )
    core.events.fire_event(EntityEvent("ordinary", "x"))
    await asyncio.sleep(0)
    await drain(connection, socket, 2)
    assert socket.messages[0]["success"] is False
    assert socket.messages[1]["event_type"] == "ordinary"


async def test_hot_source_reenters_behind_cold_source_after_held_write() -> None:
    _, connection, socket = connection_with_socket(held=True)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "hot", 1))
    connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "cold", 1))
    sender = asyncio.create_task(connection._sender())
    try:
        await asyncio.wait_for(socket.write_started.wait(), timeout=1)
        for value in range(2, 100):
            connection.send_event(1, EntityEvent(Event.GRAPH_UPDATE, "hot", value))
        socket.release.set()

        async def wait() -> None:
            while len(socket.messages) < 3:
                await asyncio.sleep(0)

        await asyncio.wait_for(wait(), timeout=1)
        assert [(m["graph_id"], m["value"]) for m in socket.messages] == [
            ("hot", 1),
            ("cold", 1),
            ("hot", 99),
        ]
    finally:
        connection.close()
        await asyncio.gather(sender, return_exceptions=True)


async def test_more_text_drops_during_summary_write_preserve_count_and_log_progress() -> (
    None
):
    _, connection, socket = connection_with_socket(held=True)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    for index in range(101):
        connection.send_event(1, GeneralDiagEvent(str(index)))
    summary = connection._select_delivery()
    assert (
        summary is not None
        and summary.message["debug"] == "Dropped 1 diagnostic messages"
    )
    writing = asyncio.create_task(connection._write_delivery(summary))
    try:
        await asyncio.wait_for(socket.write_started.wait(), timeout=1)
        for index in range(101, 151):
            connection.send_event(1, GeneralDiagEvent(str(index)))
        assert len(connection._text_queue) == 100
        socket.release.set()
        await writing
        selected = connection._select_delivery()
        assert selected is not None and selected.message["debug"] == "51"
        await connection._write_delivery(selected)
        next_summary = connection._select_delivery()
        assert (
            next_summary is not None
            and next_summary.message["debug"] == "Dropped 50 diagnostic messages"
        )
        await connection._write_delivery(next_summary)
        assert [m["debug"] for m in socket.messages] == [
            "Dropped 1 diagnostic messages",
            "51",
            "Dropped 50 diagnostic messages",
        ]
    finally:
        socket.release.set()
        await asyncio.gather(writing, return_exceptions=True)
        connection.close()


async def test_socket_failure_cancels_waiting_receiver() -> None:
    core = Core()
    connection = WebsocketConnection(core)
    socket = RecordingSocket()
    connection._socket = cast(web.WebSocketResponse, socket)
    connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
    receiver = connection._receiver_task = asyncio.create_task(asyncio.Event().wait())
    socket.closed = True
    await connection._sender()
    await asyncio.wait_for(asyncio.gather(receiver, return_exceptions=True), timeout=1)
    assert receiver.cancelled()
    assert connection._listeners == {} and core.events._listeners == {}
    assert connection._closed


@pytest.mark.parametrize("pixels", ["AQID", [[1], [2], [3]]])
async def test_actual_encoded_preview_event_reaches_wire(
    pixels: str | list[list[int]],
) -> None:
    core = Core()
    connection = WebsocketConnection(core)

    async def handle(request: web.Request) -> web.StreamResponse:
        return await connection.handle(request)

    app = web.Application()
    app.router.add_get("/websocket", handle)
    async with TestClient(TestServer(app)) as client:
        socket = await client.ws_connect("/websocket")
        assert (await socket.receive_json())["event_type"] == "client_id"
        await socket.send_json(
            {
                "id": 7,
                "type": "subscribe_event",
                "event_type": Event.VISUALISATION_UPDATE,
                "ack": True,
            }
        )
        assert (await socket.receive_json())["result"]["installed"] is True
        core.events.fire_event(VisualisationUpdateEvent(False, "same", pixels, (1, 1)))
        assert await asyncio.wait_for(socket.receive_json(), timeout=1) == {
            "id": 7,
            "type": "event",
            "event_type": Event.VISUALISATION_UPDATE,
            "vis_id": "same",
            "is_device": False,
            "pixels": pixels,
            "shape": [1, 1],
        }
        await socket.close()
    assert core.events._listeners == {}


@pytest.mark.parametrize("control", [False, True])
async def test_selected_delivery_is_invalid_after_connection_close(
    control: bool,
) -> None:
    core, connection, socket = connection_with_socket()
    if control:
        connection.send({"id": 1})
    else:
        connection.subscribe_event_handler({"id": 1, "event_type": "ordinary"})
        core.events.fire_event(EntityEvent("ordinary", "x"))
        await asyncio.sleep(0)
    selected = connection._select_delivery()
    assert selected is not None
    connection.close()
    await connection._write_delivery(selected)
    assert socket.started == []
