"""Tests for event system, particularly mutable default arguments fix."""

from ledfx.events import EventListener, Events


class TestEventListener:
    """Test EventListener class for mutable default argument issues."""

    def test_event_filter_independence(self):
        """Test that event_filter dictionaries are independent between instances."""
        # Create two listeners without providing event_filter
        listener1 = EventListener(lambda e: None)
        listener2 = EventListener(lambda e: None)

        # Modify listener1's filter
        listener1.filter["test_key"] = "test_value"

        # Verify listener2's filter is not affected
        assert "test_key" not in listener2.filter
        assert listener1.filter != listener2.filter

    def test_event_filter_with_provided_dict(self):
        """Test that provided event_filter works correctly."""
        test_filter = {"event_type": "test"}
        listener = EventListener(lambda e: None, event_filter=test_filter)

        assert listener.filter == test_filter
        assert listener.filter is test_filter  # Should be the same object

    def test_event_filter_with_none(self):
        """Test that None event_filter creates empty dict."""
        listener = EventListener(lambda e: None, event_filter=None)

        assert listener.filter == {}
        assert isinstance(listener.filter, dict)


class TestEventsAddListener:
    """Test Events.add_listener method for mutable default argument issues."""

    def test_add_listener_filter_independence(self, mocker):
        """Test that event_filter in add_listener is independent between calls."""
        # Create a mock ledfx instance with an event loop
        mock_ledfx = mocker.Mock()
        mock_ledfx.loop = mocker.Mock()

        events = Events(mock_ledfx)

        # Create listener storage to capture the listeners
        captured_listeners = []

        def capture_listener(event):
            pass

        # Add two listeners without event_filter
        events.add_listener(capture_listener, "test_event_1")
        events.add_listener(capture_listener, "test_event_2")

        # Get the listeners that were created
        listeners_1 = events._listeners.get("test_event_1", [])
        listeners_2 = events._listeners.get("test_event_2", [])

        assert len(listeners_1) == 1
        assert len(listeners_2) == 1

        # Modify first listener's filter
        listeners_1[0].filter["modified"] = True

        # Verify second listener's filter is not affected
        assert "modified" not in listeners_2[0].filter
        assert listeners_1[0].filter != listeners_2[0].filter

    def test_add_listener_with_filter(self, mocker):
        """Test that provided event_filter works correctly in add_listener."""
        mock_ledfx = mocker.Mock()
        mock_ledfx.loop = mocker.Mock()

        events = Events(mock_ledfx)

        test_filter = {"event_type": "specific_type"}

        def test_callback(event):
            pass

        events.add_listener(
            test_callback, "test_event", event_filter=test_filter
        )

        listeners = events._listeners.get("test_event", [])
        assert len(listeners) == 1
        # The listener should have the filter we provided
        assert "event_type" in listeners[0].filter
        assert listeners[0].filter["event_type"] == "specific_type"
