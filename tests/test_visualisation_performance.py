"""Preview optimizations must preserve subscriptions and RGB wire format."""

import base64
from collections.abc import Callable
from types import SimpleNamespace
from typing import ParamSpec, cast
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

_P = ParamSpec("_P")


def make_core() -> SimpleNamespace:
    def dispatch(
        callback: Callable[_P, object], *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        callback(*args, **kwargs)

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


@pytest.mark.parametrize("source_fps", [30, 60, 62, 100, 120])
def test_preview_keeps_requested_average_rate_without_duplicate_updates(
    monkeypatch: pytest.MonkeyPatch, source_fps: int
) -> None:
    clock = [1000.0]
    monkeypatch.setattr("ledfx.core.time.time", lambda: clock[0])
    monkeypatch.setattr("ledfx.core.time.monotonic", lambda: clock[0])
    core = make_core()
    received: list[VisualisationUpdateEvent] = []
    core.events.add_listener(received.append, Event.VISUALISATION_UPDATE)
    event = VirtualUpdateEvent("strip", np.zeros((1, 3)))
    for frame in range(source_fps * 2):
        clock[0] = 1000.0 + frame / source_fps
        core.visualisation_update_listener(event)
        # A device/virtual pair or duplicate at the same instant must not burst.
        core.visualisation_update_listener(event)
    assert abs(len(received) - 2 * min(source_fps, 60)) <= 1


def test_preview_does_not_replay_missed_frames_after_idle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [1000.0]
    monkeypatch.setattr("ledfx.core.time.time", lambda: clock[0])
    monkeypatch.setattr("ledfx.core.time.monotonic", lambda: clock[0])
    core = make_core()
    received: list[VisualisationUpdateEvent] = []
    core.events.add_listener(received.append, Event.VISUALISATION_UPDATE)
    event = VirtualUpdateEvent("strip", np.zeros((1, 3)))
    core.visualisation_update_listener(event)
    clock[0] += 100
    for _ in range(100):
        core.visualisation_update_listener(event)
    assert len(received) == 2
