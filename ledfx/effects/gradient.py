import logging

import numpy as np
import voluptuous as vol

from ledfx.color import RGB, parse_gradient, validate_gradient
from ledfx.effects import Effect
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect

_LOGGER = logging.getLogger(__name__)


@Effect.no_registration
class GradientEffect(Effect):
    """
    Simple effect base class that supplies gradient functionality. This
    is intended for effect which instead of outputing exact colors output
    colors based upon some configured color pallet.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "gradient",
                description="Color gradient to display",
                default="linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)",
            ): validate_gradient,
            vol.Optional(
                "gradient_roll",
                description="Amount to shift the gradient",
                default=0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        }
    )

    _gradient_curve = None
    _gradient_roll_counter = 0

    def _comb(self, N, k):
        N = int(N)
        k = int(k)

        if k > N or N < 0 or k < 0:
            return 0

        M = N + 1
        nterms = min(k, N - k)
        numerator = 1
        denominator = 1

        for j in range(1, nterms + 1):
            numerator *= M - j
            denominator *= j

        return numerator // denominator

    def _bernstein_poly(self, i, n, t):
        """The Bernstein polynomial of n, i as a function of t"""
        return self._comb(n, i) * (t ** (n - i)) * (1 - t) ** i

    def _ease(self, chunk_len, start_val, end_val, slope=1.5):
        x = np.linspace(0, 1, chunk_len)
        diff = end_val - start_val
        pow_x = np.power(x, slope)
        return diff * pow_x / (pow_x + np.power(1 - x, slope)) + start_val

    def _generate_gradient_curve(self, gradient, gradient_length):
        _LOGGER.debug(f"Generating new gradient curve: {gradient}")

        try:
            gradient = parse_gradient(gradient)
        except ValueError:
            gradient = RGB(0, 0, 0)

        if isinstance(gradient, RGB):
            self._gradient_curve = (
                np.tile(gradient, (gradient_length, 1)).astype(float).T
            )
            return

        gradient_colors = gradient.colors

        # fill in start and end colors if not explicitly given
        if gradient_colors[0][1] != 0.0:
            gradient_colors.insert(0, (gradient_colors[0][0], 0.0))

        if gradient_colors[-1][1] != 1.0:
            gradient_colors.insert(-1, (gradient_colors[-1][0], 1.0))

        # split colors and splits into two separate groups
        gradient_colors, gradient_splits = zip(*gradient_colors)

        # turn splits into real indexes to split array
        gradient_splits = [
            int(gradient_length * position)
            for position in gradient_splits
            if 0 < position < 1
        ]
        # pair colors (1,2), (2,3), (3,4) for color transition of each segment
        gradient_colors_paired = zip(gradient_colors, gradient_colors[1:])

        # create gradient array and split it up into the segments
        gradient = np.zeros((gradient_length, 3)).astype(float)
        gradient_segments = np.split(gradient, gradient_splits, axis=0)

        for (color_1, color_2), segment in zip(
            gradient_colors_paired, gradient_segments
        ):
            segment_len = len(segment)
            segment[:, 0] = self._ease(segment_len, color_1[0], color_2[0])
            segment[:, 1] = self._ease(segment_len, color_1[1], color_2[1])
            segment[:, 2] = self._ease(segment_len, color_1[2], color_2[2])

        self._gradient_curve = gradient.T

    def _assert_gradient(self):
        if (
            self._gradient_curve is None  # Uninitialized gradient
            or len(self._gradient_curve[0])
            != self.pixel_count  # Incorrect size
        ):
            self._generate_gradient_curve(
                self._config["gradient"],
                self.pixel_count,
            )

    def _roll_gradient(self):
        if self._config["gradient_roll"] == 0:
            return

        self._gradient_roll_counter += self._config["gradient_roll"]

        if self._gradient_roll_counter >= 1.0:
            pixels_to_roll = np.floor(self._gradient_roll_counter)
            self._gradient_roll_counter -= pixels_to_roll

            self._gradient_curve = np.roll(
                self._gradient_curve,
                int(pixels_to_roll),
                axis=1,
            )

    def get_gradient_color(self, point):
        self._assert_gradient()

        return self._gradient_curve[:, int((self.pixel_count - 1) * point)]

    def config_updated(self, config):
        """Invalidate the gradient"""
        self._gradient_curve = None

    def apply_gradient(self, y):
        self._assert_gradient()

        output = self._gradient_curve * y
        # Apply and roll the gradient if necessary
        self._roll_gradient()

        return output.T


class TemporalGradientEffect(TemporalEffect, GradientEffect, ModulateEffect):
    """
    A simple effect that just applies a gradient to the channel. This
    is essentually just the temporal exposure of gradients.
    """

    NAME = "Gradient"
    CATEGORY = "Non-Reactive"

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        # TODO: Could add some cool effects like twinkle or sin modulation
        # of the gradient.
        # kinda done
        pixels = self.apply_gradient(1)
        self.pixels = self.modulate(pixels)
