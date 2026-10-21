"""The preview sampler keeps the newest frame per source and encodes on a tick."""

import base64
import threading
from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest

from ledfx.events import Event, Events, VisualisationUpdateEvent
from ledfx.preview import PreviewSampler
from ledfx.utils import pixels_boost, resize_pixels, shape_to_fit_len
from tests.test_utilities.fake_loop import FakeLoop


def make_sampler(**config: object) -> tuple[PreviewSampler, SimpleNamespace]:
    host = SimpleNamespace(
        loop=FakeLoop(),
        config=SimpleNamespace(
            visualisation_fps=60,
            visualisation_maxlen=81,
            ui_brightness_boost=0,
            transmission_mode="compressed",
        ),
    )
    vars(host.config).update(config)
    host.events = Events(host)
    return PreviewSampler(host), host


def listen(host: SimpleNamespace, **event_filter: object):
    received: list[VisualisationUpdateEvent] = []
    dispose = host.events.add_listener(
        received.append, Event.VISUALISATION_UPDATE, event_filter
    )
    return received, dispose


def decoded(event: VisualisationUpdateEvent) -> bytes:
    return base64.b64decode(cast(str, event.pixels))


def test_no_interest_no_copy_no_wake():
    sampler, host = make_sampler()
    listen(host, vis_id="other")

    assert not sampler.wants(False, "strip")
    sampler.submit(False, "strip", np.zeros((10, 3)), 1)

    assert host.loop.run_ready() == 0
    assert host.loop.armed_timers == []


def test_delayed_loop_encodes_only_newest_frame():
    sampler, host = make_sampler()
    received, _ = listen(host)

    for value in range(1000):
        sampler.submit(False, "strip", np.full((10, 3), value % 256), 1)
    host.loop.run_ready()

    assert len(received) == 1
    assert decoded(received[0]) == bytes([999 % 256] * 30)


@pytest.mark.parametrize("source_fps", [30, 60, 62, 100, 120])
def test_requested_average_rate(source_fps: int):
    sampler, host = make_sampler()
    received, _ = listen(host)
    start = host.loop.time()

    for frame in range(source_fps * 2):
        host.loop.advance(start + frame / source_fps - host.loop.time())
        sampler.submit(False, "strip", np.zeros((1, 3)), 1)
        # A duplicate at the same instant must not burst.
        sampler.submit(False, "strip", np.zeros((1, 3)), 1)
        host.loop.run_ready()

    assert abs(len(received) - 2 * min(source_fps, 60)) <= 1


def test_idle_gap_does_not_replay():
    sampler, host = make_sampler()
    received, _ = listen(host)

    sampler.submit(False, "strip", np.zeros((1, 3)), 1)
    host.loop.run_ready()
    host.loop.advance(100)
    for _ in range(100):
        sampler.submit(False, "strip", np.zeros((1, 3)), 1)
    host.loop.advance(1)

    assert len(received) == 2


def test_device_and_virtual_with_same_id_keep_separate_streams():
    sampler, host = make_sampler()
    received, _ = listen(host)

    sampler.submit(True, "x", np.full((2, 3), 10), 1)
    sampler.submit(False, "x", np.full((2, 3), 20), 1)
    host.loop.run_ready()

    streams = {(event.is_device, event.vis_id): decoded(event) for event in received}
    assert streams == {(True, "x"): bytes([10] * 6), (False, "x"): bytes([20] * 6)}


@pytest.mark.parametrize("is_device", [True, False])
@pytest.mark.parametrize("dtype", [np.float64, np.uint8])
def test_rows_and_strided_rgb_bytes(is_device: bool, dtype: type):
    sampler, host = make_sampler()
    received, _ = listen(host)
    strided = np.arange(36, dtype=dtype).reshape(12, 3)[::2]
    original = strided.copy()

    sampler.submit(is_device, "strip", strided, 1)
    sampler.submit(is_device, "matrix", np.zeros((64, 3), dtype=dtype), 8)
    host.loop.run_ready()

    by_id = {event.vis_id: event for event in received}
    assert by_id["strip"].shape == (1, 6)
    assert decoded(by_id["strip"]) == bytes(strided.astype(np.uint8).flatten())
    np.testing.assert_array_equal(strided, original)
    assert by_id["matrix"].shape == (8, 8)


def test_geometry_and_boost_match_main_math():
    sampler, host = make_sampler(ui_brightness_boost=0.5)
    received, _ = listen(host)
    pixels = np.random.default_rng(1).uniform(0, 255, (500, 3))
    shape, length = shape_to_fit_len(81, (1, 500), 500)
    expected = pixels_boost(resize_pixels(pixels[:length], (1, 500), shape), 0.5, 100)

    sampler.submit(False, "strip", pixels, 1)
    host.loop.run_ready()
    # Config is read when encoding, so a changed mode applies to the next frame.
    host.config.transmission_mode = "uncompressed"
    host.loop.advance(1)
    sampler.submit(False, "strip", pixels, 1)
    host.loop.run_ready()

    assert [event.shape for event in received] == [(1, 81), (1, 81)]
    assert decoded(received[0]) == expected.astype(np.uint8).tobytes()
    assert received[1].pixels == expected.astype(np.uint8).T.tolist()


def test_interest_removed_releases_pending_at_next_tick():
    sampler, host = make_sampler()
    received, dispose = listen(host)

    sampler.submit(False, "strip", np.zeros((10, 3)), 1)
    dispose()
    host.loop.run_ready()

    assert received == []
    # No public surface holds the pending frames; this is the retention check.
    assert sampler._pending == {}
    assert host.loop.armed_timers == []


def test_forget_from_thread_drops_pending_without_touching_timers():
    sampler, host = make_sampler()
    received, _ = listen(host)
    sampler.submit(False, "strip", np.zeros((1, 3)), 1)
    host.loop.run_ready()
    sampler.submit(False, "strip", np.ones((1, 3)), 1)
    host.loop.run_ready()
    [timer] = host.loop.armed_timers

    thread = threading.Thread(target=sampler.forget, args=(False, "strip"))
    thread.start()
    thread.join(5)
    assert not thread.is_alive()
    assert not timer.cancelled
    host.loop.advance(1)

    assert len(received) == 1
    assert host.loop.armed_timers == []


def test_close_is_idempotent_and_stops_delivery():
    sampler, host = make_sampler()
    received, _ = listen(host)

    sampler.submit(False, "strip", np.zeros((1, 3)), 1)
    sampler.close()
    sampler.close()
    host.loop.run_ready()
    assert not sampler.wants(False, "strip")
    sampler.submit(False, "strip", np.zeros((1, 3)), 1)

    assert host.loop.run_ready() == 0
    assert received == []
