from ledfx.effects.temporal import TemporalEffect
from ledfx.color import COLORS, GRADIENTS
from ledfx.effects import Effect
import voluptuous as vol
import numpy as np
import logging

_LOGGER = logging.getLogger(__name__)

@Effect.no_registration
class GradientEffect(Effect):
    """
    Simple effect base class that supplies gradient functionality. This
    is intended for effect which instead of outputing exact colors output
    colors based upon some configured color pallet.
    """

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('gradient_name', description='Preset gradient name', default = 'Spectral'): str,
        vol.Optional('gradient_roll', description='Amount to shift the gradient', default = 0): vol.Coerce(int),
    })

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
        return self._comb(n, i) * ( t**(n-i) ) * (1 - t)**i

    def _generate_bezier_curve(self, gradient_colors, gradient_length):

        gradient_method = "bezier"

        # Check to see if we have a custom gradient, or a predefined one and
        # load the colors accordingly
        if isinstance(gradient_colors, str):
            gradient_name = gradient_colors.lower()
            gradient_colors = []
            if GRADIENTS.get(gradient_name):
                gradient_colors = GRADIENTS.get(gradient_name).get("colors")
                gradient_method = GRADIENTS.get(gradient_name).get("method")
            elif COLORS.get(gradient_name):
                gradient_colors = [gradient_name]

        if not gradient_colors:
            gradient_colors = GRADIENTS.get('spectral')

        self.rgb_list = np.array([COLORS[color.lower()] for color in gradient_colors]).T
        n_colors = len(self.rgb_list[0])

        if gradient_method == "bezier":
            t = np.linspace(0.0, 1.0, gradient_length)
            polynomial_array = np.array([self._bernstein_poly(i, n_colors-1, t) for i in range(0, n_colors)])
            gradient = np.array([np.dot(self.rgb_list[0], polynomial_array),
                                np.dot(self.rgb_list[1], polynomial_array),
                                np.dot(self.rgb_list[2], polynomial_array)])

            _LOGGER.info(('Generating new gradient curve for {}'.format(gradient_colors)))
            self._gradient_curve = gradient
        else:
            gradient = np.zeros((gradient_length, 3))
            for i in range(gradient_length):
                rgb_i = i % n_colors
                gradient[i] = (self.rgb_list[0][rgb_i], self.rgb_list[1][rgb_i], self.rgb_list[2][rgb_i])
            self._gradient_curve = gradient.T

    def _gradient_valid(self):
        if self._gradient_curve is None:
            return False # Uninitialized gradient
        if len(self._gradient_curve[0]) != self.pixel_count:
            return False # Incorrect size
        return True

    def _validate_gradient(self):
        if not self._gradient_valid(): 
            self._generate_bezier_curve(self._config['gradient_name'], self.pixel_count)

    def _roll_gradient(self):
        if self._config['gradient_roll'] == 0:
            return

        self._gradient_curve = np.roll(
            self._gradient_curve,
            self._config['gradient_roll'],
            axis=1)

    def get_gradient_color(self, point):
        self._validate_gradient()

        n_colors = len(self.rgb_list[0])
        polynomial_array = np.array([self._bernstein_poly(i, n_colors-1, point) for i in range(0, n_colors)])
        return (np.dot(self.rgb_list[0], polynomial_array),
                np.dot(self.rgb_list[1], polynomial_array),
                np.dot(self.rgb_list[2], polynomial_array))

    def config_updated(self, config):
        """Invalidate the gradient"""
        self._gradient_curve = None

    def apply_gradient(self, y):
        self._validate_gradient()

        # Apply and roll the gradient if necessary
        output = (self._gradient_curve[:][::1]*y).T
        self._roll_gradient()

        return output


class TemporalGradientEffect(TemporalEffect, GradientEffect):
    """
    A simple effect that just applies a gradient to the channel. This
    is essentually just the temporal exposure of gradients.
    """

    NAME = "Gradient"

    def effect_loop(self):
        # TODO: Could add some cool effects like twinkle or sin modulation
        # of the gradient.
        self.pixels = self.apply_gradient(1)