"""Tests for websocket event subscription."""

from unittest.mock import MagicMock

import pytest

from ledfx.api.websocket import WebsocketConnection


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
