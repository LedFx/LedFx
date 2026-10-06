"""Preview optimizations preserve demand, cadence and RGB wire format."""

from collections.abc import Iterator
from typing import Literal
from unittest.mock import Mock

import numpy as np
import pytest

from ledfx.preview import PreviewSettings, SourceKey
from tests.test_preview_sampler import Harness, rgb


@pytest.fixture
def harness() -> Iterator[Harness]:
    result = Harness()
    result.sampler.reconfigure(PreviewSettings(60, 81, 0, "compressed"))
    yield result
    result.close()


def test_preview_work_tracks_late_subscribe_and_unsubscribe(
    monkeypatch: pytest.MonkeyPatch, harness: Harness
) -> None:
    resize = Mock(return_value=np.zeros((81, 3), dtype=np.uint8))
    monkeypatch.setattr("ledfx.preview.resize_pixels", resize)
    key = SourceKey("virtual", "strip")
    generation = harness.sampler.allocate_source_generation(key)
    pixels = np.zeros((500, 3))
    # Undemanded producers need not capture, and accidental submission is harmless.
    assert not harness.sampler.interested(key, generation)
    harness.sampler.submit(harness.frame(key, generation, 0, pixels=pixels))
    harness.core.loop.drain()
    resize.assert_not_called()
    unsubscribe = harness.listen()
    harness.sampler.submit(harness.frame(key, generation, 1, pixels=pixels))
    harness.core.loop.drain()
    resize.assert_called_once()
    assert len(harness.delivered) == 1
    assert harness.delivered[0].shape == (1, 81)
    unsubscribe()
    harness.core.loop.drain()
    assert not harness.sampler.interested(key, generation)
    harness.sampler.submit(harness.frame(key, generation, 2, pixels=pixels))
    harness.core.loop.drain()
    assert resize.call_count == 1


@pytest.mark.parametrize("kind", ["device", "virtual"])
@pytest.mark.parametrize("dtype", [np.float64, np.uint8])
def test_preview_preserves_strided_rgb_bytes(
    harness: Harness,
    kind: Literal["device", "virtual"],
    dtype: type[np.float64] | type[np.uint8],
) -> None:
    pixels = np.arange(36, dtype=dtype).reshape(12, 3)[::2]
    original = pixels.copy()
    harness.listen()
    key = SourceKey(kind, "strip")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, pixels=pixels))
    harness.core.loop.drain()
    assert harness.delivered[0].shape == (1, 6)
    assert rgb(harness.delivered[0]) == pixels.astype(np.uint8).tobytes()
    np.testing.assert_array_equal(pixels, original)


@pytest.mark.parametrize("source_fps", [30, 60, 62, 100, 120])
def test_preview_keeps_requested_average_rate_without_duplicate_updates(
    harness: Harness, source_fps: int
) -> None:
    harness.listen()
    key = SourceKey("virtual", "strip")
    generation = harness.sampler.allocate_source_generation(key)
    start = harness.core.loop.time()
    for sequence in range(source_fps * 2):
        harness.core.loop.advance(start + sequence / source_fps)
        frame = harness.frame(key, generation, sequence)
        harness.sampler.submit(frame)
        # Repeating one producer sequence cannot duplicate a sample.
        harness.sampler.submit(frame)
        harness.core.loop.drain()
    harness.core.loop.advance(start + 2)
    assert abs(len(harness.delivered) - 2 * min(source_fps, 60)) <= 1


def test_preview_does_not_replay_missed_frames_after_idle(harness: Harness) -> None:
    harness.listen()
    key = SourceKey("virtual", "strip")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0))
    harness.core.loop.drain()
    harness.core.loop.advance(harness.core.loop.time() + 100)
    for sequence in range(1, 101):
        harness.sampler.submit(harness.frame(key, generation, sequence))
    harness.core.loop.drain()
    assert len(harness.delivered) == 2
