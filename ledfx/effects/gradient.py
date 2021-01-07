import logging

import numpy as np
import voluptuous as vol

from ledfx.color import COLORS, GRADIENTS
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
                "gradient_name",
                description="Color gradient to display",
                default="Rainbow",
            ): vol.In(list(GRADIENTS.keys())),
            vol.Optional(
                "gradient_roll",
                description="Amount to shift the gradient",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
            vol.Optional(
                "gradient_repeat",
                description="Repeat the gradient into segments",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=16))
            # vol.Optional('gradient_method', description='Function used to
            # generate gradient', default = 'cubic_ease'): vol.In(["cubic_ease",
            # "bezier"]),
        }
    )

    _gradient_curve = None

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

    def _color_ease(self, chunk_len, start_color, end_color):
        """Makes a coloured block easing from start to end colour"""
        return np.array(
            [
                self._ease(chunk_len, start_color[i], end_color[i])
                for i in range(3)
            ]
        )

    def _generate_gradient_curve(
        self, gradient_colors, gradient_length, repeat
    ):

        # Check to see if we have a custom gradient, or a predefined one and
        # load the colors accordingly
        if isinstance(gradient_colors, str):
            gradient_name = gradient_colors
            gradient_colors = []
            if GRADIENTS.get(gradient_name):
                gradient_colors = GRADIENTS.get(gradient_name).get("colors")
                # gradient_method = GRADIENTS.get(gradient_name).get("method", gradient_method)
            elif COLORS.get(gradient_name):
                gradient_colors = [gradient_name]

        if not gradient_colors:
            gradient_colors = GRADIENTS.get("Rainbow")

        self.rgb_list = np.array(
            [COLORS[color.lower()] for color in gradient_colors]
        ).T
        n_colors = len(self.rgb_list[0])

        # if gradient_method == "bezier":
        #     t = np.linspace(0.0, 1.0, gradient_length)
        #     polynomial_array = np.array([self._bernstein_poly(i, n_colors-1, t) for i in range(0, n_colors)])
        #     polynomial_array = np.fliplr(polynomial_array)
        #     gradient = np.array([np.dot(self.rgb_list[0], polynomial_array),
        #                          np.dot(self.rgb_list[1], polynomial_array),
        #                          np.dot(self.rgb_list[2], polynomial_array)])
        #     _LOGGER.info(('Generating new gradient curve for {}'.format(gradient_colors)))
        #     self._gradient_curve = gradient

        # elif gradient_method == "cubic_ease":

        gradient = np.zeros((3, gradient_length))
        gradient_split = np.array_split(gradient, repeat, axis=1)
        for i in range(len(gradient_split)):
            segment_length = len(gradient_split[i][0])
            t = np.zeros(segment_length)
            ease_chunks = np.array_split(t, n_colors - 1)
            color_pairs = np.array(
                [
                    (self.rgb_list.T[i], self.rgb_list.T[i + 1])
                    for i in range(n_colors - 1)
                ]
            )
            gradient_split[i] = np.hstack(
                list(
                    self._color_ease(len(ease_chunks[i]), *color_pairs[i])
                    for i in range(n_colors - 1)
                )
            )
        _LOGGER.info(
            ("Generating new gradient curve for {}".format(gradient_colors))
        )
        self._gradient_curve = np.hstack(gradient_split)

        # else:
        #     gradient = np.zeros((gradient_length, 3))
        #     for i in range(gradient_length):
        #         rgb_i = i % n_colors
        #         gradient[i] = (self.rgb_list[0][rgb_i], self.rgb_list[1][rgb_i], self.rgb_list[2][rgb_i])
        #     self._gradient_curve = gradient.T

    def _gradient_valid(self):
        if self._gradient_curve is None:
            return False  # Uninitialized gradient
        if len(self._gradient_curve[0]) != self.pixel_count:
            return False  # Incorrect size
        return True

    def _validate_gradient(self):
        if not self._gradient_valid():
            self._generate_gradient_curve(
                self._config["gradient_name"],
                self.pixel_count,
                self._config["gradient_repeat"],
            )

    def _roll_gradient(self):
        if self._config["gradient_roll"] == 0:
            return

        self._gradient_curve = np.roll(
            self._gradient_curve,
            self._config["gradient_roll"],
            axis=1,
        )

    def get_gradient_color(self, point):
        self._validate_gradient()

        # n_colors = len(self.rgb_list[0])
        # polynomial_array = np.array([self._bernstein_poly(i, n_colors-1, point) for i in range(0, n_colors)])
        # return (np.dot(self.rgb_list[0], polynomial_array),
        #        np.dot(self.rgb_list[1], polynomial_array),
        #        np.dot(self.rgb_list[2], polynomial_array))

        return np.hstack(
            self._gradient_curve[:, int((self.pixel_count - 1) * point)]
        )

    def config_updated(self, config):
        """Invalidate the gradient"""
        self._gradient_curve = None

    def apply_gradient(self, y):
        self._validate_gradient()

        # Apply and roll the gradient if necessary
        output = (self._gradient_curve[:][::1] * y).T
        self._roll_gradient()

        return output


class TemporalGradientEffect(TemporalEffect, GradientEffect, ModulateEffect):
    """
    A simple effect that just applies a gradient to the channel. This
    is essentually just the temporal exposure of gradients.
    """

    NAME = "Gradient"

    def effect_loop(self):
        # TODO: Could add some cool effects like twinkle or sin modulation
        # of the gradient.
        # kinda done
        pixels = self.apply_gradient(1)
        self.pixels = self.modulate(pixels)
