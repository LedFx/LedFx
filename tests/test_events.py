"""Tests for ledfx/events.py - Event system"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from ledfx.events import Event, EventListener, Events
from tests.test_utilities.fake_loop import FakeLoop


def make_events() -> tuple[Events, FakeLoop]:
    loop = FakeLoop()
    return Events(SimpleNamespace(loop=loop)), loop


class TestEventListener:
    """Test EventListener class"""

    def test_filter_independence_without_args(self):
        """
        Test that EventListener instances using default filters don't share state.

        This tests the fix for the mutable default argument bug where all
        EventListener instances using the default event_filter={} would
        share the same dict object, causing filter pollution.
        """
        callback1 = MagicMock()
        callback2 = MagicMock()

        # Create first listener with default filter
        listener1 = EventListener(callback1)
        assert listener1.filter == {}

        # Mutate listener1's filter (simulates runtime filter modification)
        listener1.filter["type"] = "device"
        listener1.filter["status"] = "active"

        # Create second listener with default filter
        listener2 = EventListener(callback2)

        # Assert that listener2 has an independent empty filter
        assert listener2.filter == {}, (
            f"Expected empty filter for listener2, got {listener2.filter}. "
            "This indicates mutable default argument bug."
        )

        # Verify listener1 still has its filter
        assert listener1.filter == {"type": "device", "status": "active"}

    def test_explicit_filter_works(self):
        """Test that passing an explicit filter works correctly"""
        callback = MagicMock()
        custom_filter = {"event_type": "virtual_update"}

        listener = EventListener(callback, custom_filter)

        assert listener.filter is custom_filter
        assert listener.filter == {"event_type": "virtual_update"}

    def test_empty_dict_passed_explicitly(self):
        """Test that passing an explicit empty dict works"""
        callback = MagicMock()
        explicit_empty = {}

        listener = EventListener(callback, explicit_empty)

        # Should use the passed dict, not create a new one
        assert listener.filter is explicit_empty


class TestEventsAddListener:
    """Test Events.add_listener method"""

    def test_add_listener_filter_independence(self):
        """
        Test that add_listener with default filters creates independent filters.

        This tests the fix for the mutable default argument in Events.add_listener.
        """
        ledfx_mock = MagicMock()
        ledfx_mock.loop = MagicMock()
        events = Events(ledfx_mock)

        callback1 = MagicMock()
        callback2 = MagicMock()

        # Add first listener with default filter
        events.add_listener(callback1, "device_update")

        # Access the listener and mutate its filter
        listener1 = events._listeners["device_update"][0]
        listener1.filter["source"] = "api"

        # Add second listener with default filter
        events.add_listener(callback2, "virtual_update")

        # Access the second listener
        listener2 = events._listeners["virtual_update"][0]

        # Assert that listener2 has an independent empty filter
        assert listener2.filter == {}, (
            f"Expected empty filter for listener2, got {listener2.filter}. "
            "Filter pollution from listener1 detected."
        )

        # Verify listener1 still has its mutated filter
        assert listener1.filter == {"source": "api"}

    def test_add_listener_with_explicit_filter(self):
        """Test add_listener with an explicit filter"""
        ledfx_mock = MagicMock()
        ledfx_mock.loop = MagicMock()
        events = Events(ledfx_mock)

        callback = MagicMock()
        custom_filter = {"device_id": "123"}

        events.add_listener(callback, "device_update", custom_filter)

        listener = events._listeners["device_update"][0]
        assert listener.filter == {"device_id": "123"}


class TestRevocation:
    """Disposal, snapshot iteration and cross-thread firing"""

    def test_disposal_revokes_already_queued_callback(self):
        events, loop = make_events()
        received: list[Event] = []
        dispose = events.add_listener(received.append, "test")

        events.fire_event(Event("test"))
        dispose()
        loop.run_ready()

        assert received == []

    def test_disposer_is_idempotent(self, caplog: pytest.LogCaptureFixture):
        events, loop = make_events()
        kept: list[Event] = []
        events.add_listener(kept.append, "test")
        dispose = events.add_listener(MagicMock(), "test")

        with caplog.at_level("DEBUG", logger="ledfx.events"):
            dispose()
            dispose()
        events.fire_event(Event("test"))
        loop.run_ready()

        assert caplog.records == []
        assert events.has_listeners("test")
        assert len(kept) == 1

    def test_registration_changes_during_fire_use_captured_snapshot(self):
        events, loop = make_events()
        late: list[Event] = []
        calls: list[Event] = []

        def first(event: Event) -> None:
            calls.append(event)
            events.add_listener(late.append, "test")
            dispose_first()

        dispose_first = events.add_listener(first, "test")
        events.fire_event(Event("test"))
        events.fire_event(Event("test"))
        loop.run_ready()

        # The second queued call was revoked by the first one's disposal, and
        # the listener added meanwhile was not registered for either event.
        assert len(calls) == 1
        assert late == []

    def test_fire_event_from_thread_while_loop_mutates(self):
        events, loop = make_events()
        events.add_listener(MagicMock(), "test")
        errors: list[BaseException] = []
        started = threading.Event()

        def fire() -> None:
            started.set()
            try:
                for _ in range(10_000):
                    events.fire_event(Event("test"))
            except BaseException as error:  # noqa: BLE001 - report to the test
                errors.append(error)

        thread = threading.Thread(target=fire)
        thread.start()
        started.wait(timeout=5)
        while thread.is_alive():
            events.add_listener(MagicMock(), "test")()
        thread.join(timeout=5)

        assert not thread.is_alive()
        assert errors == []
        assert loop.run_ready() >= 10_000

    def test_automated_flag_survives_dispatch(self):
        events, loop = make_events()
        received: list[Event] = []
        events.add_listener(received.append, "test")

        with events.automated():
            events.fire_event(Event("test"))
        events.fire_event(Event("test"))
        loop.run_ready()

        assert [event._automated for event in received] == [True, False]


class PixelEvent(Event):
    def __init__(self, pixels: np.ndarray) -> None:
        super().__init__("pixels")
        self.pixels = pixels


class TestFailureIsolation:
    """A failing listener or filter must not starve the others"""

    def test_callback_exception_does_not_starve_next(self):
        events, loop = make_events()
        received: list[Event] = []

        def broken(event: Event) -> None:
            raise RuntimeError("listener bug")

        events.add_listener(broken, "test")
        events.add_listener(received.append, "test")
        events.fire_event(Event("test"))
        loop.run_ready()

        assert len(received) == 1

    def test_filter_comparison_failure_is_isolated(self):
        events, loop = make_events()
        received: list[Event] = []
        # ndarray != 1 is an array, whose truth value raises.
        events.add_listener(MagicMock(), "pixels", {"pixels": 1})
        events.add_listener(received.append, "pixels")

        events.fire_event(PixelEvent(np.zeros((4, 3))))
        loop.run_ready()

        assert len(received) == 1

    def test_listener_failures_are_rate_limited(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        now = [1000.0]
        monkeypatch.setattr("ledfx.events.time.monotonic", lambda: now[0])
        events, loop = make_events()

        def broken(event: Event) -> None:
            raise ValueError("first listener bug")

        def also_broken(event: Event) -> None:
            raise ValueError("second listener bug")

        events.add_listener(broken, "test")

        with caplog.at_level("WARNING", logger="ledfx.events"):
            for _ in range(100):
                events.fire_event(Event("test"))
            loop.run_ready()
            assert len(caplog.records) == 1

            # Same class from another listener, in the same window, is its own report.
            events.add_listener(also_broken, "test")
            events.fire_event(Event("test"))
            loop.run_ready()
            assert len(caplog.records) == 2

            now[0] += 1.0
            events.fire_event(Event("test"))
            loop.run_ready()

        assert len(caplog.records) == 4
        for record in caplog.records:
            # ERROR with the traceback reaches the log and Sentry like main's loop handler.
            assert record.levelname == "ERROR"
            assert record.exc_info is not None
            assert record.exc_info[0] is ValueError
        first, second, third, fourth = caplog.records
        assert "broken" in first.getMessage()
        assert "also_broken" in second.getMessage()
        assert first.exc_info is not None and "first" in str(first.exc_info[1])
        assert second.exc_info is not None and "second" in str(second.exc_info[1])
        # 99 repeats suppressed in the first batch, one more when also_broken
        # joined, plus the failure that opened the new window.
        assert third.getMessage() == (
            "Event listener TestFailureIsolation.test_listener_failures_are_rate_limited"
            ".<locals>.broken failed on test (101 errors since last report)"
        )
        assert "also_broken" in fourth.getMessage()
        assert "(1 errors since last report)" in fourth.getMessage()


class TestMayHaveListeners:
    """Producers ask before building a payload; only a proven mismatch says no."""

    def test_may_have_listeners_excludes_only_proven_mismatch(self):
        events, _ = make_events()
        assert not events.may_have_listeners("graph_update", {"graph_id": "melbank_0"})

        dispose = events.add_listener(
            MagicMock(), "graph_update", {"graph_id": "melbank_0"}
        )
        assert events.may_have_listeners("graph_update", {"graph_id": "melbank_0"})
        assert not events.may_have_listeners("graph_update", {"graph_id": "melbank_1"})
        # The listener for another event type never counts.
        assert not events.may_have_listeners("virtual_diag", {"graph_id": "melbank_0"})

        # A key the payload metadata does not mention cannot exclude.
        dispose()
        dispose = events.add_listener(MagicMock(), "graph_update", {"other": 1})
        assert events.may_have_listeners("graph_update", {"graph_id": "melbank_1"})

        dispose()
        events.add_listener(MagicMock(), "graph_update", {})
        assert events.may_have_listeners("graph_update", {"graph_id": "melbank_1"})

    def test_may_have_listeners_filters_on_event_type(self):
        events, _ = make_events()
        events.add_listener(
            MagicMock(), "graph_update", {"event_type": "something_else"}
        )
        assert not events.may_have_listeners("graph_update", {"graph_id": "x"})

    def test_may_have_listeners_raising_comparison_is_conservative(
        self, caplog: pytest.LogCaptureFixture
    ):
        class Unequal:
            def __eq__(self, other: object) -> bool:
                raise ValueError("cannot compare")

            __hash__ = object.__hash__

        events, _ = make_events()
        events.add_listener(MagicMock(), "graph_update", {"graph_id": Unequal()})

        with caplog.at_level("ERROR", logger="ledfx.events"):
            assert events.may_have_listeners("graph_update", {"graph_id": "x"})

        assert len(caplog.records) == 1
        assert caplog.records[0].exc_info is not None
        assert caplog.records[0].exc_info[0] is ValueError
