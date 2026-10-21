"""Tests for ledfx/events.py - Event system"""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

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
