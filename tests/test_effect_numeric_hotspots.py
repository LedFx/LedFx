"""Numeric equivalence for the kernels found by the effect catalog profiles."""

from types import SimpleNamespace
from typing import Literal, cast

import numpy as np
import pytest

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.math import sawtooth, triangle
from ledfx.effects.soap2d import Soap2D


@pytest.mark.parametrize("dtype", [np.float16, np.float32, np.float64, np.longdouble])
def test_triangle_preserves_waveform_and_dtype(dtype: type[np.floating]):
    rng = np.random.default_rng(42)
    boundaries = np.arange(-4, 5, dtype=dtype) / 4
    values = np.concatenate(
        [
            rng.uniform(-100, 100, 2048).astype(dtype),
            boundaries,
            np.nextafter(boundaries, dtype(np.inf)),
            np.nextafter(boundaries, dtype(-np.inf)),
            np.array([np.nan, np.inf, -np.inf], dtype=dtype),
        ]
    )
    for points in (values, values[::2], values[:0], np.array(0.25, dtype=dtype)):
        with np.errstate(invalid="ignore"):
            try:
                expected = sawtooth(points * np.pi * 2, 0.5)
            except TypeError:
                # Extended precision is unsupported by the original on some OSes.
                with pytest.raises(TypeError):
                    triangle(points)
                continue
            expected *= 0.5
            expected = expected + 0.5
            actual = triangle(points)
        assert actual.dtype == expected.dtype
        np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("shape", [(), (19,), (7, 11), (0,), (0, 3)])
@pytest.mark.parametrize("layout", ["C", "F", "strided"])
def test_gradient_lookup_preserves_shape_clamping_and_colors(
    shape: tuple[int, ...], layout: Literal["C", "F", "strided"]
):
    rng = np.random.default_rng(42)
    curve = np.array(rng.random((3, 256)), order=layout if layout != "strided" else "C")
    if layout == "strided":
        curve = curve[:, ::2]
    effect = cast(
        GradientEffect,
        SimpleNamespace(
            _gradient_curve=curve,
            gradient_pixel_count=curve.shape[1],
            _assert_gradient=lambda: None,
        ),
    )
    points = rng.uniform(-0.5, 1.5, shape)
    original = points.copy()
    indices = ((curve.shape[1] - 1) * np.clip(points, 0, 1)).astype(int)
    expected = curve[:, indices]
    actual = GradientEffect._get_gradient_colors(effect, points)
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(points, original)


def smear_reference(
    pixels: np.ndarray, palette: np.ndarray, amount: np.ndarray, axis: int
):
    """Scalar tap selection with the original float32 smoothstep weights."""
    sign = np.sign(amount).astype(np.int32)
    magnitude = np.abs(amount)
    whole = np.floor(magnitude).astype(np.int32)
    fraction = (magnitude - whole).astype(np.float32)
    weight = fraction * fraction * (3.0 - 2.0 * fraction)
    other = 1.0 - weight
    output = np.empty(pixels.shape, dtype=np.float32)
    for y in range(pixels.shape[0]):
        for x in range(pixels.shape[1]):
            line = y if axis == 1 else x
            position = x if axis == 1 else y
            taps = []
            for offset in (0, 1):
                source = position + int(sign[line]) * (int(whole[line]) + offset)
                source_pixels = pixels if 0 <= source < pixels.shape[axis] else palette
                source = min(max(source, 0), pixels.shape[axis] - 1)
                taps.append(
                    source_pixels[y, source] if axis == 1 else source_pixels[source, x]
                )
            output[y, x] = taps[0] * other[line] + taps[1] * weight[line]
    return output


@pytest.mark.parametrize("shape", [(1, 1), (1, 41), (41, 1), (9, 13), (129, 131)])
@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_soap_smear_preserves_taps_edges_and_inputs(
    shape: tuple[int, int], axis: int, dtype: type[np.floating]
):
    rng = np.random.default_rng(42)
    # Reversed inputs also exercise non-contiguous rows and columns.
    pixels = rng.uniform(0, 255, (*shape, 3)).astype(dtype)[::-1]
    palette = rng.uniform(0, 255, pixels.shape).astype(dtype)[:, ::-1]
    amounts = np.resize(
        np.array([-200, -2.75, -1, -0.25, 0, 0.25, 1, 2.75, 200], dtype=np.float32),
        shape[1 - axis],
    )
    original = pixels.copy()
    expected = smear_reference(pixels, palette, amounts, axis)
    effect = object.__new__(Soap2D)
    actual = effect._smear_axis_signed_oob(pixels, palette, amounts, axis)
    assert actual.dtype == np.float32
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(pixels, original)
