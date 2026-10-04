"""Check shared gradient HSV output against a scalar saturation/value reference."""

from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest

from ledfx.effects.hsv_effect import HSVEffect


@pytest.mark.parametrize("count", [1, 17, 1024])
def test_hsv_gradient_saturation_and_value_match_scalar_reference(count: int) -> None:
    rng = np.random.default_rng(72)
    gradient = rng.uniform(0, 255, (3, count))
    hues = rng.uniform(-2, 2, count)
    saturations = rng.uniform(-0.1, 1.1, count)
    values = rng.uniform(0, 1, count)
    source = np.column_stack((hues, saturations, values))
    indices = np.floor((hues % 1) * (count - 1)).astype(int)
    expected = np.array(
        [
            [
                (channel + (max(gradient[:, index]) - channel) * (1 - saturation))
                * value
                for channel in gradient[:, index]
            ]
            for index, saturation, value in zip(indices, saturations, values)
        ]
    )
    effect = SimpleNamespace(
        _start_time=0,
        render_hsv=lambda: None,
        hsv_array=source,
        config=SimpleNamespace(fix_hues=False),
        pixel_count=count,
        pixels=np.empty((count, 3)),
        _h_indices=np.zeros(count, dtype=int),
        _pixel_max=np.empty((count, 1)),
        _saturation_work=np.empty(count),
        _inverse_saturation=np.empty(count),
        get_gradient=lambda: gradient,
        roll_gradient=lambda: None,
    )
    HSVEffect.render(cast(HSVEffect, effect))
    np.testing.assert_array_equal(effect.pixels, expected)
    np.testing.assert_array_equal(effect.hsv_array[:, 1], saturations)
    np.testing.assert_array_equal(effect.hsv_array[:, 2], values)
