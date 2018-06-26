from ledfxcontroller.effects.temporal import TemporalEffect
from ledfxcontroller.consts import COLOR_TABLE
from ledfxcontroller.effects import Effect
from scipy.misc import comb
import voluptuous as vol
import numpy as np
import logging

_LOGGER = logging.getLogger(__name__)

class GradientEffect(Effect):
    """
    Simple effect base class that supplies gradient functionality. This
    is intended for effect which instead of outputing exact colors output
    colors based upon some configured color pallet.
    """

    # TODO: Strong schema validation for the gradients
    CONFIG_SCHEMA = vol.Schema({
        vol.Required('gradient', default = 'Spectral'): str,
        vol.Required('gradient_flip', default = False): bool,
        vol.Required('gradient_roll', default = 0): int,
    })

    GRADIENT_TABLE = {
        "Spectral"  : ["Red", "Orange", "Yellow", "Green", "Light Blue", "Blue", "Purple", "Pink"],
        "Dancefloor": ["Red", "Pink", "Purple", "Blue"],
        "Sunset"    : ["Red", "Orange", "Yellow"],
        "Ocean"     : ["Green", "Light Blue", "Blue"],
        "Jungle"    : ["Green", "Red", "Orange"],
        "Sunny"     : ["Yellow", "Light Blue", "Orange", "Blue"],
        "Fruity"    : ["Orange", "Blue"],
        "Peach"     : ["Orange", "Pink"],
        "Rust"      : ["Orange", "Red"]
    }

    _gradient_name = None
    _gradient_curve = None

    def _bernstein_poly(self, i, n, t):
        """
        The Bernstein polynomial of n, i as a function of t
        """
        return comb(n, i) * ( t**(n-i) ) * (1 - t)**i

    def _generate_bezier_curve(self, gradient_name, gradient_length):

        rgb_list = np.array([COLOR_TABLE[color] for color in self.GRADIENT_TABLE[gradient_name]]).T
        n_colors = len(rgb_list[0])

        t = np.linspace(0.0, 1.0, gradient_length)
        polynomial_array = np.array([self._bernstein_poly(i, n_colors-1, t) for i in range(0, n_colors)])
        gradient = np.array([np.dot(rgb_list[0], polynomial_array),
                            np.dot(rgb_list[1], polynomial_array),
                            np.dot(rgb_list[2], polynomial_array)])

        self._gradient_curve = gradient
        self._gradient_name = gradient_name

    def _gradient_valid(self):
        if self._gradient_curve is None:
            return False # Uninitialized gradient
        if self._gradient_name != self._config['gradient']:
            return False # Incorrect gradient
        if len(self._gradient_curve[0]) != self.pixel_count:
            return False # Incorrect size
        return True

    def _validate_gradient(self):
        if not self._gradient_valid():
            self._generate_bezier_curve(self._config['gradient'], self.pixel_count)

    def _roll_gradient(self):
        if self._config['gradient_roll'] == 0:
            return

        self._gradient_curve = np.roll(
            self._gradient_curve,
            self._config['gradient_roll'],
            axis=1)

    def apply_gradient(self, y):
        self._validate_gradient()

        # Apply and roll the gradient if necessary
        flip_index = -1 if self._config['gradient_flip'] else 1
        output = (self._gradient_curve[:][::flip_index]*y).T
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