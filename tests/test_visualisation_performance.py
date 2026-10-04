"""Preview optimizations must preserve subscriptions and RGB wire format."""

import base64
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import numpy as np
import pytest

from ledfx.core import LedFxCore
from ledfx.events import (
    DeviceUpdateEvent,
    Event,
    Events,
    VirtualUpdateEvent,
    VisualisationUpdateEvent,
)


def make_core() -> SimpleNamespace:
    def dispatch(callback: Callable[[Event], None], event: Event) -> None:
        callback(event)

    core = SimpleNamespace(
        config=SimpleNamespace(
            visualisation_fps=60,
            visualisation_maxlen=81,
            ui_brightness_boost=0,
            transmission_mode="compressed",
        ),
        loop=SimpleNamespace(call_soon_threadsafe=dispatch),
        virtuals={},
    )
    core.events = Events(core)
    LedFxCore.setup_visualisation_events(cast(LedFxCore, core))
    return core


def test_preview_work_tracks_late_subscribe_and_unsubscribe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    core = make_core()
    resize = Mock(return_value=np.zeros((81, 3), dtype=np.uint8))
    monkeypatch.setattr("ledfx.core.resize_pixels", resize)
    event = VirtualUpdateEvent("strip", np.zeros((500, 3)))
    core.visualisation_update_listener(event)
    resize.assert_not_called()
    received: list[VisualisationUpdateEvent] = []
    unsubscribe = core.events.add_listener(received.append, Event.VISUALISATION_UPDATE)
    core.visualisation_update_listener(event)
    resize.assert_called_once()
    assert len(received) == 1
    assert received[0].shape == (1, 81)
    unsubscribe()
    assert not core.events.has_listeners(Event.VISUALISATION_UPDATE)
    core.visualisation_update_listener(event)
    assert resize.call_count == 1


@pytest.mark.parametrize("event_type", [DeviceUpdateEvent, VirtualUpdateEvent])
@pytest.mark.parametrize("dtype", [np.float64, np.uint8])
def test_preview_preserves_strided_rgb_bytes(
    event_type: type[DeviceUpdateEvent] | type[VirtualUpdateEvent],
    dtype: type[np.float64] | type[np.uint8],
) -> None:
    core = make_core()
    pixels = np.arange(36, dtype=dtype).reshape(12, 3)[::2]
    original = pixels.copy()
    received: list[VisualisationUpdateEvent] = []
    core.events.add_listener(received.append, Event.VISUALISATION_UPDATE)
    core.visualisation_update_listener(event_type("strip", pixels))
    assert received[0].shape == (1, 6)
    assert base64.b64decode(cast(str, received[0].pixels)) == bytes(
        pixels.astype(np.uint8).flatten()
    )
    np.testing.assert_array_equal(pixels, original)
