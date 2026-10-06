"""Producer telemetry owns admitted data and bounds work before loop wakeup."""

import asyncio
import gc
import threading
import weakref
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from types import SimpleNamespace
from typing import ParamSpec
from unittest.mock import MagicMock, Mock

import numpy as np
import pytest
from numpy.typing import NDArray

from ledfx.api.websocket import WebsocketConnection
from ledfx.configuration.models import AudioConfig
from ledfx.effects.audio import AudioAnalysisSource, AudioInputSource
from ledfx.effects.melbank import Melbanks
from ledfx.effects.utils.logsec_helper import LogSecHelper
from ledfx.events import (
    Event,
    Events,
    GeneralDiagEvent,
    GraphUpdateEvent,
    VirtualDiagEvent,
    VirtualUpdateEvent,
    _DiagnosticDropSummary,
    _PendingGraph,
)
from tests.test_utilities.fake_ledfx import fake_ledfx
from tests.test_utilities.virtuals_core import add_virtual, running_core
from tests.test_websocket_delivery import connection_with_socket, drain

_P = ParamSpec("_P")


class DeferredLoop:
    def __init__(self) -> None:
        self.ready: list[Callable[[], object]] = []

    def call_soon_threadsafe(
        self, callback: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        self.ready.append(partial(callback, *args, **kwargs))

    def drain(self) -> None:
        while self.ready:
            self.ready.pop(0)()


@dataclass
class Host:
    loop: DeferredLoop


def make_bus() -> tuple[Events, DeferredLoop]:
    loop = DeferredLoop()
    return Events(Host(loop)), loop


def diag(virtual_id: str, index: int, phy: dict[str, object]) -> VirtualDiagEvent:
    return VirtualDiagEvent(virtual_id, index, 0.1, 0.01, 0.2, 0.3, 0.1, phy)


def test_graph_producer_latest_before_loop_wake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE, {"graph_id": "melbank"})
    materialize = Mock(wraps=bus._materialize_graph)
    monkeypatch.setattr(bus, "_materialize_graph", materialize)
    for index in range(1000):
        bus.publish_graph("melbank", np.array([index]), np.array([50]))
    assert len(loop.ready) == 1
    assert len(bus._latest) == 1
    materialize.assert_not_called()
    loop.drain()
    materialize.assert_called_once()
    assert len(got) == 1
    assert isinstance(got[0], GraphUpdateEvent)
    assert got[0].melbank == [999] and got[0].frequencies == [50]


def test_graph_admission_owns_both_arrays() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    values = np.array([1, 2, 3])
    frequencies = np.array([50, 100, 150])
    bus.publish_graph("melbank", values, frequencies)
    values[:] = 9
    frequencies[:] = 999
    loop.drain()
    assert isinstance(got[0], GraphUpdateEvent)
    assert got[0].melbank == [1, 2, 3] and got[0].frequencies == [50, 100, 150]


@pytest.mark.parametrize("other_listener", [False, True])
def test_no_graph_interest_does_not_copy_or_construct(
    monkeypatch: pytest.MonkeyPatch, other_listener: bool
) -> None:
    bus, loop = make_bus()
    if other_listener:
        bus.add_listener(lambda event: None, Event.GRAPH_UPDATE, {"graph_id": "other"})
    constructor = Mock(side_effect=AssertionError("uninterested graph construction"))
    monkeypatch.setattr("ledfx.events.GraphUpdateEvent", constructor)
    # Passing objects without ndarray methods proves admission precedes copying.
    values = Mock(side_effect=AssertionError("uninterested copy"))
    bus.publish_graph("melbank", values, values)
    values.copy.assert_not_called()
    constructor.assert_not_called()
    assert loop.ready == [] and bus._latest == {}


@pytest.mark.parametrize("event_type", [Event.GRAPH_UPDATE, Event.VIRTUAL_DIAG])
def test_preconstructed_latest_snapshots_nested_data(event_type: str) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, event_type)
    rssi = [-70, -60]
    phy: dict[str, object] = {"wifi": {"rssi": rssi}}
    for index in range(1000):
        if event_type == Event.VIRTUAL_DIAG:
            event = diag("v", index, phy)
        else:
            event = GraphUpdateEvent("g", np.array([index]), np.array([50]))
        bus.fire_event(event)
    rssi[0] = 0
    phy["wifi"] = {"rssi": [0]}
    if isinstance(event, GraphUpdateEvent):
        event.melbank[0] = -1
    assert len(loop.ready) == 1 and len(bus._latest) == 1
    loop.drain()
    assert len(got) == 1
    selected = got[0]
    if isinstance(selected, VirtualDiagEvent):
        assert selected.fps == 999
        assert selected.phy == {"wifi": {"rssi": [-70, -60]}}
    else:
        assert isinstance(selected, GraphUpdateEvent) and selected.melbank == [999]


def test_full_filters_match_only_retained_latest() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE, {"melbank": [1]})
    bus.publish_graph("g", np.array([1]), np.array([50]))
    bus.publish_graph("g", np.array([2]), np.array([50]))
    loop.drain()
    assert got == []


def test_text_flood_retains_last_100_and_nonrecursive_summary() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    for index in range(1000):
        bus.fire_event(GeneralDiagEvent(str(index), scroll=True))
    assert len(loop.ready) == 1 and len(bus._text_queue) == 100
    loop.drain()
    assert all(isinstance(event, GeneralDiagEvent) for event in got)
    records = [event for event in got if isinstance(event, GeneralDiagEvent)]
    assert [event.debug for event in records] == [
        "Dropped 900 diagnostic messages",
        *map(str, range(900, 1000)),
    ]
    assert records[0].scroll is True and bus._text_dropped == 0


def test_summary_losses_reset_only_when_matching_listener_admits_summary() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GENERAL_DIAG, {"debug": "keep"})
    for _ in range(101):
        bus.fire_event(GeneralDiagEvent("keep"))
    loop.drain()
    assert len(got) == 100 and bus._text_dropped == 1
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    bus.fire_event(GeneralDiagEvent("next"))
    loop.drain()
    assert isinstance(got[-2], GeneralDiagEvent)
    assert got[-2].debug == "Dropped 1 diagnostic messages"
    assert bus._text_dropped == 0


@pytest.mark.parametrize("event_type", [Event.GRAPH_UPDATE, Event.VIRTUAL_DIAG])
@pytest.mark.parametrize("purge", ["demand", "source"])
def test_last_demand_and_source_purge_release_pending(
    event_type: str, purge: str
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    remove = bus.add_listener(got.append, event_type)
    if event_type == Event.GRAPH_UPDATE:
        bus.publish_graph("x", np.array([1]), np.array([50]))
    else:
        bus.fire_event(diag("x", 1, {}))
    if purge == "demand":
        remove()
    else:
        bus.purge_pending(event_type, "x")
    assert bus._latest == {}
    loop.drain()
    assert got == []


def test_revoking_one_source_prunes_only_disjoint_demand() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    remove_a = bus.add_listener(got.append, Event.GRAPH_UPDATE, {"graph_id": "a"})
    bus.add_listener(got.append, Event.GRAPH_UPDATE, {"graph_id": "b"})
    for name in ("a", "b"):
        bus.publish_graph(name, np.array([1]), np.array([50]))
    remove_a()
    assert set(bus._latest) == {(Event.GRAPH_UPDATE, "b")}
    loop.drain()
    assert (
        len(got) == 1
        and isinstance(got[0], GraphUpdateEvent)
        and got[0].graph_id == "b"
    )


def test_closed_socket_drops_pending_producer_work() -> None:
    bus, loop = make_bus()
    host = Mock(loop=loop, events=bus)
    connection = WebsocketConnection(host)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    bus.publish_graph("g", np.array([1]), np.array([50]))
    connection.close()
    assert bus._latest == {} and not bus.has_listeners(Event.GRAPH_UPDATE)
    loop.drain()
    assert connection._select_delivery() is None


def test_closed_socket_rejects_selected_callback_and_releases_its_owner() -> None:
    bus, loop = make_bus()
    connection = WebsocketConnection(Mock(loop=loop, events=bus))
    reference = weakref.ref(connection)
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    bus.publish_graph("g", np.array([1]), np.array([50]))
    loop.ready.pop(0)()  # selected graph has queued its guarded observer callback
    assert len(loop.ready) == 1
    connection.close()
    del connection
    loop.drain()
    gc.collect()
    assert reference() is None and not bus._latest and not bus._draining_latest


def test_purge_during_selected_graph_materialization_skips_disposed_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    original = bus._materialize_graph

    def materialize(pending: _PendingGraph) -> GraphUpdateEvent:
        bus.purge_pending(Event.GRAPH_UPDATE, "a")
        bus.purge_pending(Event.GRAPH_UPDATE, "b")
        return original(pending)

    monkeypatch.setattr(bus, "_materialize_graph", materialize)
    for name in ("a", "b"):
        bus.publish_graph(name, np.array([1]), np.array([50]))
    loop.drain()
    assert got == [] and bus._latest == {} and bus._draining_latest == {}


def test_raced_graph_submission_arms_one_subsequent_drain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    original = bus._materialize_graph
    entered = threading.Event()
    release = threading.Event()
    errors: list[Exception] = []

    def materialize(pending: _PendingGraph) -> GraphUpdateEvent:
        entered.set()
        assert release.wait(2)
        return original(pending)

    def drain_once() -> None:
        try:
            loop.ready.pop(0)()
        except Exception as error:  # noqa: BLE001 - propagate worker failure to the test
            errors.append(error)

    monkeypatch.setattr(bus, "_materialize_graph", materialize)
    bus.publish_graph("g", np.array([0]), np.array([50]))
    worker = threading.Thread(target=drain_once)
    worker.start()
    try:
        assert entered.wait(2)
        for index in range(1, 1001):
            bus.publish_graph("g", np.array([index]), np.array([50]))
        assert loop.ready == [] and len(bus._latest) == 1
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive() and errors == []
    assert len(loop.ready) == 2  # selected invocation and one subsequent drain
    loop.drain()
    assert [event.melbank for event in got if isinstance(event, GraphUpdateEvent)] == [
        [0],
        [1000],
    ]


def test_continuous_text_overload_is_bounded_and_preserves_new_losses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    original = bus._dispatch
    batches = 0

    def dispatch(event: Event) -> bool:
        nonlocal batches
        if (
            isinstance(event, GeneralDiagEvent)
            and event.debug.startswith("Dropped")
            and batches < 2
        ):
            batches += 1
            for index in range(1000):
                bus.fire_event(GeneralDiagEvent(f"batch{batches}:{index}"))
            assert len(bus._text_queue) == 100
            assert len(loop.ready) <= 101
        return original(event)

    monkeypatch.setattr(bus, "_dispatch", dispatch)
    for index in range(1000):
        bus.fire_event(GeneralDiagEvent(str(index)))
    loop.drain()
    records = [event for event in got if isinstance(event, GeneralDiagEvent)]
    assert len(records) == 303
    assert [event.debug for event in records if event.debug.startswith("Dropped")] == [
        "Dropped 900 diagnostic messages"
    ] * 3
    assert bus._text_dropped == 0 and not bus._telemetry_scheduled


def test_graph_producer_rebuild_purges_old_ids_and_uses_selected_actual_data() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    core = fake_ledfx()
    core.events = bus
    audio = SimpleNamespace(_config=AudioConfig(min_volume=0.3))
    melbanks = Melbanks(core, audio, core.config.melbanks.model_dump())
    melbanks.melbanks_filtered[-1][:] = 7
    melbanks.send_melbank_event(len(melbanks.melbank_processors) - 1)
    assert len(bus._latest) == 1
    core.config.melbank_collection = core.config.melbank_collection[:1]
    melbanks.update_config(
        {**core.config.melbanks.model_dump(), "max_frequencies": [350]}
    )
    assert bus._latest == {}
    melbanks.melbanks_filtered[0][:] = 3
    melbanks.send_melbank_event(0)
    loop.drain()
    assert len(got) == 1 and isinstance(got[0], GraphUpdateEvent)
    assert got[0].graph_id == "melbank_0"
    assert got[0].melbank == [3] * melbanks.mel_len
    assert (
        got[0].frequencies
        == melbanks.melbank_processors[0].melbank_frequencies.tolist()
    )


@pytest.fixture
def virtual_core(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.mark.parametrize("action", ["deactivate", "destroy"])
def test_actual_virtual_lifecycle_purges_diag_without_losing_raw_rgb(
    virtual_core: MagicMock, action: str
) -> None:
    bus, loop = make_bus()
    virtual_core.events = bus
    virtual = add_virtual(virtual_core, "sample", "Sample", [])
    got: list[Event] = []
    bus.add_listener(got.append, Event.VIRTUAL_DIAG)
    bus.add_listener(got.append, Event.VIRTUAL_UPDATE)
    rgb: NDArray[np.generic] = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
    bus.fire_event(VirtualUpdateEvent(virtual.id, rgb))
    bus.fire_event(diag(virtual.id, 60, {"name": "physical"}))
    if action == "deactivate":
        virtual.deactivate()
    else:
        virtual_core.virtuals.destroy(virtual.id)
    assert bus._latest == {}
    loop.drain()
    assert len(got) == 1 and isinstance(got[0], VirtualUpdateEvent)
    assert got[0].pixels is rgb and got[0].pixels.tolist() == [[1, 2, 3], [4, 5, 6]]


async def test_257_distinct_graph_sources_reach_socket_explicit_overflow() -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GRAPH_UPDATE})
    for index in range(257):
        core.events.publish_graph(str(index), np.array([index]), np.array([50]))
    assert len(core.events._latest) == 257
    await asyncio.wait_for(socket.close_started.wait(), timeout=1)
    assert socket.closes == [(1013, b"stream backlog; reconnect and resync")]
    assert not core.events.has_listeners(Event.GRAPH_UPDATE)
    assert core.events._latest == {} and core.events._draining_latest == {}
    close_task = connection._close_task
    assert close_task is not None
    await asyncio.wait_for(close_task, timeout=1)


@pytest.mark.parametrize("accept_first", [False, True])
def test_drop_summary_scheduling_failure_keeps_actual_admission_accounting(
    monkeypatch: pytest.MonkeyPatch, accept_first: bool
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    original = loop.call_soon_threadsafe
    attempts = 0

    def schedule(callback: Callable[..., object], *args: object) -> None:
        nonlocal attempts
        event = args[-1] if args else None
        if isinstance(event, GeneralDiagEvent) and event.debug.startswith("Dropped"):
            attempts += 1
            if not accept_first or attempts > 1:
                raise RuntimeError("test scheduler rejected summary callback")
        original(callback, *args)

    monkeypatch.setattr(loop, "call_soon_threadsafe", schedule)
    for index in range(101):
        bus.fire_event(GeneralDiagEvent(str(index)))
    loop.drain()
    summaries = [
        event.debug
        for event in got
        if isinstance(event, GeneralDiagEvent) and event.debug.startswith("Dropped")
    ]
    assert summaries == (["Dropped 1 diagnostic messages"] if accept_first else [])
    assert bus._text_dropped == (0 if accept_first else 1)
    monkeypatch.setattr(loop, "call_soon_threadsafe", original)
    bus.fire_event(GeneralDiagEvent("next"))
    loop.drain()
    assert bus._text_dropped == 0


def test_materialization_and_callbacks_run_outside_bus_and_telemetry_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    checked: list[str] = []

    def check_locks(where: str) -> None:
        for lock in (bus._lock, bus._telemetry_lock):
            assert lock.acquire(blocking=False)
            lock.release()
        checked.append(where)

    def consume(event: Event) -> None:
        check_locks(event.event_type)

    original = bus._materialize_graph

    def materialize(pending: _PendingGraph) -> GraphUpdateEvent:
        check_locks("encoding")
        return original(pending)

    monkeypatch.setattr(bus, "_materialize_graph", materialize)
    for event_type in (Event.GRAPH_UPDATE, Event.GENERAL_DIAG, Event.VIRTUAL_DIAG):
        bus.add_listener(consume, event_type)
    bus.publish_graph("g", np.array([1]), np.array([50]))
    bus.fire_event(diag("v", 60, {}))
    bus.fire_event(GeneralDiagEvent("text"))
    loop.drain()
    assert checked == [
        "encoding",
        Event.GRAPH_UPDATE,
        Event.VIRTUAL_DIAG,
        Event.GENERAL_DIAG,
    ]


def test_last_matching_metadata_demand_prunes_despite_excluded_registration() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    remove = bus.add_listener(got.append, Event.GRAPH_UPDATE)
    bus.add_listener(got.append, Event.GRAPH_UPDATE, {"event_type": "excluded"})
    bus.publish_graph("g", np.array([1]), np.array([50]))
    remove()
    assert bus._latest == {}
    loop.drain()
    assert got == []


@pytest.mark.parametrize("interested", [False, True])
def test_actual_logsec_producer_admits_only_interested_owned_phy_data(
    monkeypatch: pytest.MonkeyPatch, interested: bool
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(
        got.append,
        Event.VIRTUAL_DIAG,
        {"virtual_id": "live" if interested else "other"},
    )
    effect = MagicMock(
        _virtual=SimpleNamespace(id="live"), _ledfx=SimpleNamespace(events=bus)
    )
    helper = LogSecHelper(effect)
    helper.diag = True
    helper.log = True
    helper.fps = 60
    helper.phy.name = "physical"
    constructor = Mock(wraps=VirtualDiagEvent)
    monkeypatch.setattr(
        "ledfx.effects.utils.logsec_helper.VirtualDiagEvent", constructor
    )
    helper.try_log()
    helper.phy.name = "changed"
    loop.drain()
    if interested:
        constructor.assert_called_once()
        assert len(got) == 1 and isinstance(got[0], VirtualDiagEvent)
        assert got[0].phy["name"] == "physical" and got[0].fps == 60
    else:
        constructor.assert_not_called()
        assert got == [] and loop.ready == []


def test_text_snapshot_and_last_demand_release_pending_records() -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    remove = bus.add_listener(got.append, Event.GENERAL_DIAG)
    event = GeneralDiagEvent("owned", scroll=True)
    bus.fire_event(event)
    event.debug = "mutated"
    event.scroll = False
    loop.drain()
    assert len(got) == 1 and isinstance(got[0], GeneralDiagEvent)
    assert got[0].debug == "owned" and got[0].scroll is True
    bus.fire_event(GeneralDiagEvent("revoked"))
    remove()
    assert not bus._text_queue
    bus.add_listener(got.append, Event.GENERAL_DIAG)
    loop.drain()
    assert len(got) == 1


def analysis_source(bus: Events) -> tuple[AudioAnalysisSource, Melbanks]:
    core = fake_ledfx()
    core.events = bus
    audio = SimpleNamespace(_config=AudioConfig(min_volume=0.3))
    melbanks = Melbanks(core, audio, core.config.melbanks.model_dump())
    # Real owning lifecycle methods with only the SDK stream boundary faked.
    source = AudioAnalysisSource.__new__(AudioAnalysisSource)
    source._ledfx = core
    source.melbanks = melbanks
    return source, melbanks


@pytest.mark.parametrize("stop_fails", [False, True])
def test_audio_source_revokes_before_sdk_stop_and_blocks_late_graphs(
    monkeypatch: pytest.MonkeyPatch, stop_fails: bool
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    source, melbanks = analysis_source(bus)
    melbanks.send_melbank_event(0)
    stream = Mock()

    def stop() -> None:
        assert not bus._latest
        assert melbanks._graph_lock.acquire(blocking=False)
        melbanks._graph_lock.release()
        assert AudioInputSource._class_lock.acquire(blocking=False)
        AudioInputSource._class_lock.release()
        melbanks.send_melbank_event(0)
        assert not bus._latest
        if stop_fails:
            raise OSError("SDK stop failed")

    stream.stop.side_effect = stop
    monkeypatch.setattr(AudioInputSource, "_stream", stream)
    monkeypatch.setattr(AudioInputSource, "_audio_stream_active", True)
    if stop_fails:
        with pytest.raises(OSError, match="SDK stop failed"):
            source.deactivate()
        stream.close.assert_not_called()
    else:
        source.deactivate()
        stream.close.assert_called_once()
    assert not AudioInputSource._audio_stream_active
    melbanks.send_melbank_event(0)
    melbanks.update_config(
        {**source._ledfx.config.melbanks.model_dump(), "samples": 10}
    )
    melbanks.send_melbank_event(0)
    loop.drain()
    assert got == [] and bus._latest == {}


@pytest.mark.parametrize("result", ["success", "recovery", "error", "inactive"])
def test_audio_activation_reenables_only_successful_graph_publication(
    monkeypatch: pytest.MonkeyPatch, result: str
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    source, melbanks = analysis_source(bus)
    melbanks.purge_pending()
    monkeypatch.setattr(AudioInputSource, "_audio_stream_active", False)

    def start(owner: AudioInputSource) -> None:
        assert owner is source and melbanks._graph_lock.acquire(blocking=False)
        melbanks._graph_lock.release()
        melbanks.send_melbank_event(0)
        assert len(bus._latest) == 1  # enable before the SDK can call the producer
        if result == "error":
            raise OSError("SDK startup failed")
        if result == "recovery":
            source.deactivate()
        if result in ("success", "recovery"):
            AudioInputSource._audio_stream_active = True

    monkeypatch.setattr(AudioInputSource, "activate", start)
    monkeypatch.setattr(AudioInputSource, "_stream", None)
    if result == "error":
        with pytest.raises(OSError, match="SDK startup failed"):
            source.activate()
    else:
        source.activate()
    melbanks.send_melbank_event(0)
    loop.drain()
    assert len(got) == (1 if result in ("success", "recovery") else 0)


def test_graph_owner_revocation_waits_for_admission_then_purges_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    got: list[Event] = []
    bus.add_listener(got.append, Event.GRAPH_UPDATE)
    source, melbanks = analysis_source(bus)
    entered = threading.Event()
    release = threading.Event()
    stopping = threading.Event()
    stopped = threading.Event()
    original = bus.publish_graph
    errors: list[Exception] = []

    def publish(
        graph_id: str, values: NDArray[np.generic], frequencies: NDArray[np.generic]
    ) -> None:
        entered.set()
        assert release.wait(2)
        original(graph_id, values, frequencies)

    def send() -> None:
        try:
            melbanks.send_melbank_event(0)
        except Exception as error:  # noqa: BLE001 - propagate worker failure
            errors.append(error)

    def stop() -> None:
        stopping.set()
        try:
            source.deactivate()
        except Exception as error:  # noqa: BLE001 - propagate worker failure
            errors.append(error)
        finally:
            stopped.set()

    monkeypatch.setattr(bus, "publish_graph", publish)
    monkeypatch.setattr(AudioInputSource, "_stream", None)
    monkeypatch.setattr(AudioInputSource, "_audio_stream_active", True)
    publisher = threading.Thread(target=send)
    stopper = threading.Thread(target=stop)
    publisher.start()
    try:
        assert entered.wait(2)
        stopper.start()
        assert stopping.wait(2) and not stopped.is_set()
    finally:
        release.set()
        publisher.join(2)
        if stopper.ident is not None:
            stopper.join(2)
    assert not publisher.is_alive() and not stopper.is_alive() and errors == []
    assert stopped.is_set() and bus._latest == {}
    melbanks.send_melbank_event(0)
    loop.drain()
    assert got == []


async def test_producer_text_overload_loss_survives_socket_fifo_admission() -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    for index in range(1000):
        core.events.fire_event(GeneralDiagEvent(str(index), scroll=True))

    async def wait() -> None:
        while len(connection._text_queue) < 100:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)
    await drain(connection, socket, 101)
    assert [message["debug"] for message in socket.messages] == [
        "Dropped 900 diagnostic messages",
        *map(str, range(900, 1000)),
    ]
    assert socket.messages[0] == {
        "id": 1,
        "type": "event",
        "event_type": Event.GENERAL_DIAG,
        "debug": "Dropped 900 diagnostic messages",
        "scroll": True,
    }


async def test_producer_and_socket_losses_combine_once_before_the_next_batch() -> None:
    core, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    for index in range(10):
        connection.send_event(1, GeneralDiagEvent(f"previous:{index}"))
    for index in range(1000):
        core.events.fire_event(GeneralDiagEvent(str(index)))

    async def wait() -> None:
        while connection._text_dropped < 910:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)
    assert len(connection._text_queue) == 100
    await drain(connection, socket, 101)
    assert [message["debug"] for message in socket.messages] == [
        "Dropped 910 diagnostic messages",
        *map(str, range(900, 1000)),
    ]


async def test_revoked_producer_summary_does_not_add_socket_losses() -> None:
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    old_generation = connection._listeners[1].generation
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    connection.send_event(1, _DiagnosticDropSummary(900), old_generation)
    assert connection._text_dropped == 0
    connection.send_event(1, GeneralDiagEvent("Dropped 17 diagnostic messages"))
    assert connection._text_dropped == 0  # ordinary text is never parsed as loss
    await drain(connection, socket, 1)
    assert socket.messages[0]["debug"] == "Dropped 17 diagnostic messages"


async def test_admitted_producer_loss_survives_owner_revocation_until_summary_write() -> (
    None
):
    _, connection, socket = connection_with_socket()
    connection.subscribe_event_handler({"id": 1, "event_type": Event.GENERAL_DIAG})
    connection.send_event(1, _DiagnosticDropSummary(900))
    connection.send_event(1, GeneralDiagEvent("old"))
    selected = connection._select_delivery()
    assert selected is not None
    connection.unsubscribe_event_handler({"id": 1})
    await connection._write_delivery(selected)
    assert not socket.started and connection._text_dropped == 900
    connection.subscribe_event_handler({"id": 2, "event_type": Event.GENERAL_DIAG})
    connection.send_event(2, GeneralDiagEvent("new"))
    await drain(connection, socket, 2)
    assert [message["debug"] for message in socket.messages] == [
        "Dropped 900 diagnostic messages",
        "new",
    ]
    assert [message["id"] for message in socket.messages] == [2, 2]
