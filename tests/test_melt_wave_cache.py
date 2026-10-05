"""Cached Melt initialization survives real renders and count changes."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from ledfx.effects.hsv_effect import HSVEffect
from ledfx.effects.melt_and_sparkle import MeltSparkle


def test_melt_initial_wave_survives_render_and_reactivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ledfx.effects.melt_and_sparkle.time.time_ns", lambda: 1_000_000
    )
    effect = MeltSparkle(MagicMock(), MeltSparkle.config_model().model_validate({}))
    for count in (1, 17, 1024, 31):
        effect.pixels = np.zeros((count, 3))
        HSVEffect.on_activate(effect, count)
        MeltSparkle.on_activate(effect, count)
        # The old per-frame initialization is an independent arithmetic oracle.
        expected_wave = np.linspace(0, 1, count)
        np.subtract(1, expected_wave, out=expected_wave)
        HSVEffect.array_sin(effect, expected_wave)
        np.testing.assert_array_equal(effect._initial_wave, expected_wave)

        effect.render()
        expected_pixels = effect.pixels.copy()
        effect.h.fill(-99)
        effect.s.fill(0)
        effect.v.fill(-99)
        assert effect.hsv_array is not None
        effect.hsv_array.fill(-99)
        effect.pixels.fill(-99)
        effect.render()

        np.testing.assert_array_equal(effect.pixels, expected_pixels)
        np.testing.assert_array_equal(effect._initial_wave, expected_wave)
        assert effect.hsv_array is not None
        assert effect.hsv_array.shape == (count, 3)
