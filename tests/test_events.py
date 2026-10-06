"""Behavioral tests for copied, revocable event registrations."""

import asyncio
import logging
from collections.abc import Callable, Coroutine, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from typing import ParamSpec, cast

import numpy as np
import pytest
from typing_extensions import override

from ledfx.events import (
    BaseConfigUpdateEvent,
    Event,
    EventListener,
    Events,
    VisualisationUpdateEvent,
)

_P = ParamSpec("_P")


class DeferredLoop:
    """Queue callbacks until the test crosses the invocation boundary."""

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
class BusHost:
    loop: DeferredLoop


class PayloadEvent(Event):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__("custom")
        self.payload = payload

    @override
    def to_dict(self) -> dict[str, object]:
        return {"event_type": self.event_type, **self.payload}


def make_bus() -> tuple[Events, DeferredLoop]:
    loop = DeferredLoop()
    return Events(BusHost(loop)), loop


def ignore_event(event: Event) -> None:
    pass


class TestEventListener:
    def test_filter_independence_without_args(self) -> None:
        first = EventListener(ignore_event)
        first.filter["type"] = "device"
        second = EventListener(ignore_event)
        assert second.filter == {}
        assert first.filter == {"type": "device"}

    def test_explicit_filter_works(self) -> None:
        source = {"event_type": "virtual_update"}
        listener = EventListener(ignore_event, source)
        assert listener.filter is not source
        source["event_type"] = "other"
        assert listener.filter == {"event_type": "virtual_update"}

    def test_empty_dict_passed_explicitly(self) -> None:
        source: dict[str, object] = {}
        listener = EventListener(ignore_event, source)
        assert listener.filter is not source
        source["value"] = 1
        assert listener.filter == {}


class TestEventsAddListener:
    def test_add_listener_filter_independence(self) -> None:
        bus, _ = make_bus()
        bus.add_listener(ignore_event, "device_update")
        first = bus._listeners["device_update"][0]
        first.filter["source"] = "api"
        bus.add_listener(ignore_event, "virtual_update")
        assert bus._listeners["virtual_update"][0].filter == {}
        assert first.filter == {"source": "api"}

    def test_add_listener_with_explicit_filter(self) -> None:
        bus, _ = make_bus()
        source = {"device_id": "123"}
        bus.add_listener(ignore_event, "device_update", source)
        source["device_id"] = "456"
        assert bus._listeners["device_update"][0].filter == {"device_id": "123"}


def test_original_filter_copy_and_deferred_revocation() -> None:
    bus, loop = make_bus()
    received: list[Event] = []
    shape = [1, 2]
    source_filter: dict[str, object] = {"vis_id": "a", "shape": shape}
    dispose = bus.add_listener(
        received.append, Event.VISUALISATION_UPDATE, source_filter
    )
    source_filter["vis_id"] = "b"
    shape[0] = 9
    event = VisualisationUpdateEvent(False, "a", [[1, 2], [3, 4], [5, 6]], (1, 2))
    bus.fire_event(event)
    assert len(loop.ready) == 1
    dispose()
    dispose()
    loop.drain()
    assert received == []
    assert not bus.has_listeners(Event.VISUALISATION_UPDATE)


def test_nested_filter_mutation_is_isolated() -> None:
    nested: dict[str, object] = {"values": [1, {"enabled": True}]}
    source: dict[str, object] = {"nested": nested}
    listener = EventListener(ignore_event, source)
    nested["values"] = [9]
    source["extra"] = 3
    assert not listener.filter_event(
        PayloadEvent({"nested": {"values": (1, {"enabled": True})}})
    )


@pytest.mark.parametrize(
    ("payload", "event_filter", "excluded"),
    [
        ({}, {"unknown": None}, True),
        ({"unknown": None}, {"unknown": None}, False),
        ({"shape": (1, 2)}, {"shape": [1, 2]}, False),
        ({"shape": [1, 2]}, {"shape": (1, 2)}, False),
        ({"pixels": "AQID"}, {"pixels": "AQID"}, False),
        ({"pixels": [[1, 2], [3, 4]]}, {"pixels": [[1, 2], [3, 4]]}, False),
        ({"pixels": np.array([1, 2])}, {"pixels": [1, 2]}, True),
        ({"value": True}, {"value": 1}, True),
        ({"value": 1}, {"value": True}, True),
        ({"value": 1.0}, {"value": 1}, False),
        ({"nested": {"a": [1, None]}}, {"nested": {"a": (1, None)}}, False),
        ({"nested": {"a": 1, "b": 2}}, {"nested": {"a": 1}}, True),
    ],
)
def test_structural_filter_matching(
    payload: dict[str, object], event_filter: dict[str, object], excluded: bool
) -> None:
    listener = EventListener(ignore_event, event_filter)
    assert listener.filter_event(PayloadEvent(payload)) is excluded


@pytest.mark.parametrize(
    "event_filter",
    [
        {"value": np.array([1, 2])},
        {"value": ignore_event},
        {"value": object()},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": float("-inf")},
        {1: "bad key"},
        {"nested": {1: "bad nested key"}},
        [],
        "not a mapping",
        {"vis_id": None},
        {"device_id": 1},
        {"virtual_id": False},
        {"graph_id": []},
        {"scene_id": object()},
        {"is_device": 1},
    ],
)
def test_invalid_filters_do_not_register(event_filter: object) -> None:
    bus, loop = make_bus()
    with pytest.raises(ValueError):
        bus.add_listener(
            ignore_event, "custom", cast(Mapping[str, object], event_filter)
        )
    assert not bus.has_listeners("custom")
    assert bus.registration_snapshot("custom") == (0, ())
    assert loop.ready == []


class AsyncCallable:
    async def __call__(self, event: Event) -> None:
        pass


async def async_callback(event: Event) -> None:
    pass


@pytest.mark.parametrize("callback", [async_callback, AsyncCallable()])
def test_async_callbacks_rejected_before_registration(callback: object) -> None:
    bus, loop = make_bus()
    with pytest.raises(TypeError, match="synchronous"):
        bus.add_listener(cast(Callable[[Event], None], callback), "custom")
    assert bus.registration_snapshot("custom") == (0, ())
    assert loop.ready == []


def test_returned_coroutine_is_closed_and_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus, loop = make_bus()
    returned: list[Coroutine[object, object, None]] = []
    received: list[Event] = []

    def unexpected_async_result(event: Event) -> Coroutine[object, object, None]:
        result = async_callback(event)
        returned.append(result)
        return result

    bus.add_listener(cast(Callable[[Event], None], unexpected_async_result), "custom")
    bus.add_listener(received.append, "custom")
    event = PayloadEvent({})
    with caplog.at_level(logging.WARNING, logger="ledfx.events"):
        bus.fire_event(event)
        loop.drain()
    with pytest.raises(RuntimeError, match="cannot reuse already awaited coroutine"):
        returned[0].send(None)
    assert received == [event]
    assert len(caplog.records) == 1
    assert "custom" in caplog.text
    assert "TypeError" in caplog.text


@pytest.mark.asyncio
async def test_returned_future_is_cancelled_and_observed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus, loop = make_bus()
    future: asyncio.Future[object] = asyncio.get_running_loop().create_future()

    def unexpected_future(event: Event) -> asyncio.Future[object]:
        return future

    bus.add_listener(cast(Callable[[Event], None], unexpected_future), "custom")
    bus.fire_event(PayloadEvent({}))
    loop.drain()
    await asyncio.sleep(0)
    assert future.cancelled()
    assert len(caplog.records) == 1


def test_callback_exception_does_not_starve_next(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus, loop = make_bus()
    received: list[Event] = []

    def fail(event: Event) -> None:
        raise ValueError("do not include secret pixel payload in logs")

    bus.add_listener(fail, "custom")
    bus.add_listener(received.append, "custom")
    event = PayloadEvent({})
    bus.fire_event(event)
    loop.drain()
    assert received == [event]
    assert len(caplog.records) == 1
    assert "secret pixel" not in caplog.text


def test_registration_changes_inside_callback_use_snapshot_and_claim() -> None:
    bus, loop = make_bus()
    received: list[str] = []

    def late(event: Event) -> None:
        received.append("late")

    def first(event: Event) -> None:
        received.append("first")
        remove_second()
        remove_first()
        bus.add_listener(late, "custom")
        # This callback may finish after its invocation has been claimed.
        received.append("finished")

    remove_first = bus.add_listener(first, "custom")
    remove_second = bus.add_listener(lambda event: received.append("second"), "custom")
    bus.fire_event(PayloadEvent({}))
    assert len(loop.ready) == 2
    loop.drain()
    assert received == ["first", "finished"]
    bus.fire_event(PayloadEvent({}))
    loop.drain()
    assert received == ["first", "finished", "late"]


def test_listener_callback_runs_outside_bus_mutex() -> None:
    bus, loop = make_bus()
    claimed: list[bool] = []

    def callback(event: Event) -> None:
        acquired = bus._lock.acquire(blocking=False)
        claimed.append(acquired)
        if acquired:
            bus._lock.release()

    bus.add_listener(callback, "custom")
    bus.fire_event(PayloadEvent({}))
    loop.drain()
    assert claimed == [True]


def test_matching_exception_is_bounded_and_preserves_other_listener(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    bus, loop = make_bus()
    received: list[Event] = []
    bus.add_listener(ignore_event, "custom")
    bus.add_listener(received.append, "custom")
    _, listeners = bus.registration_snapshot("custom")

    def fail_match(event: Event) -> bool:
        assert bus._lock.acquire(blocking=False)
        bus._lock.release()
        raise RuntimeError("secret pixels must not be logged")

    monkeypatch.setattr(listeners[0], "filter_event", fail_match)
    now = [10.0]
    monkeypatch.setattr("ledfx.events.time.monotonic", lambda: now[0])
    event = PayloadEvent({})
    for _ in range(20):
        bus.fire_event(event)
    loop.drain()
    assert len(received) == 20
    assert len(caplog.records) == 1
    assert "secret pixels" not in caplog.text
    now[0] = 11.0
    bus.fire_event(event)
    loop.drain()
    assert len(caplog.records) == 2
    assert "20" in caplog.records[-1].message


def test_metadata_query_is_conservative_and_revisions_are_per_event() -> None:
    bus, _ = make_bus()
    assert not bus.may_have_listeners("custom", {})
    dispose = bus.add_listener(
        ignore_event,
        "custom",
        {"vis_id": "a", "is_device": False, "pixels": "AQID"},
    )
    revision, listeners = bus.registration_snapshot("custom")
    assert revision == 1
    assert len(listeners) == 1 and listeners[0].active
    assert not bus.may_have_listeners("custom", {"vis_id": "b"})
    assert not bus.may_have_listeners("custom", {"vis_id": "a", "is_device": True})
    assert bus.may_have_listeners("custom", {"vis_id": "a", "is_device": False})
    assert bus.may_have_listeners("custom", {})
    wildcard_dispose = bus.add_listener(ignore_event, "custom")
    assert bus.may_have_listeners("custom", {"vis_id": "b"})
    assert bus.registration_snapshot("custom")[0] == 2
    bus.add_listener(ignore_event, "other")
    assert bus.registration_snapshot("custom")[0] == 2
    assert bus.registration_snapshot("other")[1][0].generation > listeners[0].generation
    wildcard_dispose()
    dispose()
    dispose()
    assert bus.registration_snapshot("custom") == (4, ())
    assert not listeners[0].active


def test_registration_observer_notifications_are_deferred_revocable_and_unlocked() -> (
    None
):
    bus, loop = make_bus()
    observed: list[tuple[str, int]] = []

    def observer(event_type: str, revision: int) -> None:
        assert bus._lock.acquire(blocking=False)
        bus._lock.release()
        observed.append((event_type, revision))

    stop = bus.add_registration_observer(observer)
    dispose = bus.add_listener(ignore_event, "custom")
    dispose()
    dispose()
    assert observed == []
    assert len(loop.ready) == 2
    loop.drain()
    assert observed == [("custom", 1), ("custom", 2)]
    bus.add_listener(ignore_event, "custom")
    stop()
    stop()
    loop.drain()
    assert observed == [("custom", 1), ("custom", 2)]


def test_registration_observer_snapshot_and_exception_isolation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus, loop = make_bus()
    observed: list[tuple[str, int]] = []

    def fail(event_type: str, revision: int) -> None:
        raise RuntimeError("observer error")

    def register_late(event_type: str, revision: int) -> None:
        bus.add_registration_observer(
            lambda kind, version: observed.append((kind, version))
        )
        stop_first()

    bus.add_registration_observer(fail)
    stop_first = bus.add_registration_observer(register_late)
    bus.add_listener(ignore_event, "custom")
    loop.drain()
    assert observed == []
    assert len(caplog.records) == 1
    bus.add_listener(ignore_event, "other")
    loop.drain()
    assert observed == [("other", 1)]


def test_ordinary_observers_share_committed_read_only_payload() -> None:
    bus, loop = make_bus()
    nested = {"brightness": 1}
    producer_config: dict[str, object] = {"nested": nested}
    committed_config = deepcopy(producer_config)
    event = BaseConfigUpdateEvent(committed_config)
    seen: list[tuple[int, int, dict[str, object]]] = []

    def first(delivered: Event) -> None:
        assert isinstance(delivered, BaseConfigUpdateEvent)
        owned_copy = deepcopy(cast(dict[str, object], delivered.config))
        seen.append((id(delivered), id(delivered.config), owned_copy))
        cast(dict[str, object], owned_copy["nested"])["brightness"] = 9

    def second(delivered: Event) -> None:
        assert isinstance(delivered, BaseConfigUpdateEvent)
        seen.append(
            (
                id(delivered),
                id(delivered.config),
                deepcopy(cast(dict[str, object], delivered.config)),
            )
        )

    bus.add_listener(first, Event.BASE_CONFIG_UPDATE)
    bus.add_listener(second, Event.BASE_CONFIG_UPDATE)
    bus.fire_event(event)
    nested["brightness"] = 4
    loop.drain()
    assert seen[0][:2] == seen[1][:2] == (id(event), id(committed_config))
    assert seen[0][2] == {"nested": {"brightness": 9}}
    assert seen[1][2] == {"nested": {"brightness": 1}}
    assert committed_config == {"nested": {"brightness": 1}}


def test_disposal_revokes_already_queued_callback() -> None:
    bus, loop = make_bus()
    received: list[Event] = []
    dispose = bus.add_listener(received.append, "custom")
    bus.fire_event(PayloadEvent({}))
    assert len(loop.ready) == 1
    dispose()
    dispose()
    loop.drain()
    assert received == []


def test_registration_changes_during_matching_keep_captured_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, loop = make_bus()
    received: list[str] = []
    bus.add_listener(lambda event: received.append("first"), "custom")
    dispose_second = bus.add_listener(lambda event: received.append("second"), "custom")
    _, captured = bus.registration_snapshot("custom")

    def change_registrations(event: Event) -> bool:
        dispose_second()
        bus.add_listener(lambda delivered: received.append("late"), "custom")
        return False

    monkeypatch.setattr(captured[0], "filter_event", change_registrations)
    bus.fire_event(PayloadEvent({}))
    assert len(loop.ready) == 2
    assert len(captured) == 2
    loop.drain()
    assert received == ["first"]

    def include_event(event: Event) -> bool:
        return False

    monkeypatch.setattr(captured[0], "filter_event", include_event)
    bus.fire_event(PayloadEvent({}))
    loop.drain()
    assert received == ["first", "first", "late"]


def test_registration_observer_is_captured_at_mutation_time() -> None:
    bus, loop = make_bus()
    received: list[tuple[str, int]] = []
    bus.add_listener(ignore_event, "custom")
    bus.add_registration_observer(
        lambda event_type, revision: received.append((event_type, revision))
    )
    loop.drain()
    assert received == []
    bus.add_listener(ignore_event, "custom")
    loop.drain()
    assert received == [("custom", 2)]


def test_two_registrations_of_same_callback_have_distinct_tokens() -> None:
    bus, loop = make_bus()
    received: list[Event] = []
    first_dispose = bus.add_listener(received.append, "custom")
    second_dispose = bus.add_listener(received.append, "custom")
    revision, listeners = bus.registration_snapshot("custom")
    assert revision == 2
    assert listeners[0] is not listeners[1]
    assert listeners[0].generation < listeners[1].generation
    event = PayloadEvent({})
    bus.fire_event(event)
    first_dispose()
    loop.drain()
    assert received == [event]
    assert bus.has_listeners("custom")
    second_dispose()
    assert not bus.has_listeners("custom")


@pytest.mark.parametrize("callback", [async_callback, AsyncCallable()])
def test_async_registration_observers_are_rejected(callback: object) -> None:
    bus, _ = make_bus()
    with pytest.raises(TypeError, match="synchronous"):
        bus.add_registration_observer(cast(Callable[[str, int], None], callback))
    assert bus._registration_observers == ()


@pytest.mark.asyncio
async def test_returned_failed_future_exception_is_observed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus, loop = make_bus()
    failures: list[dict[str, object]] = []
    actual_loop = asyncio.get_running_loop()
    previous_handler = actual_loop.get_exception_handler()

    def exception_handler(
        actual: asyncio.AbstractEventLoop, context: dict[str, object]
    ) -> None:
        failures.append(context)

    actual_loop.set_exception_handler(exception_handler)
    try:
        future: asyncio.Future[object] = actual_loop.create_future()
        future.set_exception(ValueError("failed async result"))
        returned = [future]

        def unexpected_future(event: Event) -> asyncio.Future[object]:
            return returned[0]

        bus.add_listener(cast(Callable[[Event], None], unexpected_future), "custom")
        bus.fire_event(PayloadEvent({}))
        loop.drain()
        await asyncio.sleep(0)
        assert future.done()
        assert not future.cancelled()
        assert len(caplog.records) == 1
        returned.clear()
        del future
        await asyncio.sleep(0)
        assert failures == []
    finally:
        actual_loop.set_exception_handler(previous_handler)
