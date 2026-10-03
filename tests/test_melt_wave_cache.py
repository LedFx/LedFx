"""Cached initialization must survive frame mutation and pixel-count changes."""

from types import SimpleNamespace
from typing import cast

import numpy as np

from ledfx.effects.hsv_effect import HSVEffect
from ledfx.effects.melt_and_sparkle import MeltSparkle


def test_melt_initial_wave_matches_original_arithmetic_on_reactivation() -> None:
    effect = SimpleNamespace()

    def array_sin(data: np.ndarray) -> None:
        HSVEffect.array_sin(cast(HSVEffect, effect), data)

    effect.array_sin = array_sin
    for count in (1, 17, 1024, 31):
        effect.pixel_count = count
        MeltSparkle.on_activate(cast(MeltSparkle, effect), count)
        expected = np.linspace(0, 1, count)
        np.subtract(1, expected, out=expected)
        array_sin(expected)
        np.testing.assert_array_equal(effect._initial_wave, expected)
        assert effect.h.shape == effect.s.shape == effect.v.shape == (count,)
        for target in (effect.h, effect.v):
            np.copyto(target, effect._initial_wave)
            target[:] = -99
        effect.s[:] = 0
        np.testing.assert_array_equal(effect._initial_wave, expected)
