"""Keep RGB values stable when optimizing the large-array color conversion."""

import colorsys

import numpy as np
import pytest

from ledfx.color import hsv_to_rgb


@pytest.mark.parametrize(
    "saturation,value", [(0, 1), (1, 1), (0.95, 1), (0.3, 0.7), (1, 0)]
)
def test_hsv_matches_scalar_reference_across_wrapped_hues(
    saturation: float, value: float
) -> None:
    boundaries = np.arange(-12, 19) / 6
    hues = np.concatenate(
        [
            boundaries,
            np.nextafter(boundaries, -np.inf),
            np.nextafter(boundaries, np.inf),
            np.random.default_rng(42).uniform(-5, 5, 1000),
        ]
    )
    original = hues.copy()
    expected = (
        np.array([colorsys.hsv_to_rgb(h % 1, saturation, value) for h in hues]) * 255
    )
    actual = hsv_to_rgb(hues, saturation, value)
    np.testing.assert_allclose(actual, expected, atol=2e-12, rtol=0)
    np.testing.assert_array_equal(hues, original)
    assert actual.dtype == np.float64


def test_hsv_empty_and_noncontiguous_inputs() -> None:
    assert hsv_to_rgb(np.array([]), 1, 1).shape == (0, 3)
    hues = np.array([0, 9, 0.25, 9, 0.5, 9, 0.75, 9, 1], dtype=np.float32)[::2]
    np.testing.assert_array_equal(
        hsv_to_rgb(hues, 1, 1),
        [[255, 0, 0], [127.5, 255, 0], [0, 255, 255], [127.5, 0, 255], [255, 0, 0]],
    )
