import time

import numpy as np

from ledfx.effects import Effect
from ledfx.effects.gradient import GradientEffect

"""
# Example plots of the wavefunctions

import numpy as np
import matplotlib.pyplot as plt

period = 60
x=np.linspace(0,1,period)
duty = 0.5
_time     = np.hstack((x,x,x))
_triangle = 1-2*np.abs(_time-0.5)
_sin      = 0.5*np.sin(_time*2*np.pi)+0.5
_square   = 0.5*np.sign(duty-_time)+0.5

plt.plot(_time)
plt.plot(_sin)
plt.plot(_square)
plt.plot(_triangle)
"""


def hsv_to_rgb(hsv):
    """
    Convert pixel array of type np.array([[h,s,v], ...])
                             to np.array([[r,g,b], ...])

    algorithm from https://en.wikipedia.org/wiki/HSL_and_HSV#HSV_to_RGB
    """
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    c = v * s
    h *= 6
    x = c * (1 - np.abs(h % 2 - 1))
    rgb = np.zeros(hsv.shape)
    mask = (0 <= h) & (h <= 1)
    rgb[mask, 0] = c[mask]
    rgb[mask, 1] = x[mask]
    mask = (1 < h) & (h <= 2)
    rgb[mask, 0] = x[mask]
    rgb[mask, 1] = c[mask]
    mask = (2 < h) & (h <= 3)
    rgb[mask, 1] = c[mask]
    rgb[mask, 2] = x[mask]
    mask = (3 < h) & (h <= 4)
    rgb[mask, 1] = x[mask]
    rgb[mask, 2] = c[mask]
    mask = (4 < h) & (h <= 5)
    rgb[mask, 0] = x[mask]
    rgb[mask, 2] = c[mask]
    mask = (5 < h) & (h <= 6)
    rgb[mask, 0] = c[mask]
    rgb[mask, 2] = x[mask]
    m = v - c

    rgb[:, 0] += m
    rgb[:, 1] += m
    rgb[:, 2] += m

    return rgb * 255


@Effect.no_registration
class HSVEffect(GradientEffect):
    _start_time = time.time_ns()
    # 65.536 s expressed in ns
    _conversion_factor = 65.536 * 1e9
    _hsv_roll_counter = 0

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._dt = 0
        self.hsv_array = None

    def on_activate(self, pixel_count):
        self.hsv_array = np.zeros((pixel_count, 3))
        # self.output = np.zeros((pixel_count, 3))

    def config_updated(self, config):
        # forcibly invalidate the gradient
        self._gradient_curve = None

    def render(self):
        # update the timestep, converting ns to s
        self._dt = time.time_ns() - self._start_time
        self._assert_gradient()
        self.render_hsv()

        hsv = np.copy(self.hsv_array)

        h = hsv[:, 0]
        s = hsv[:, 1].reshape(-1, 1)
        v = hsv[:, 2].reshape(-1, 1)
        pixels = self.pixels

        # Convert hues to gradient indexes
        h %= 1
        h *= self.pixel_count - 1
        h = h.astype(int)
        # Grab the colors from the gradient
        self._assert_gradient()
        pixels[:] = self._gradient_curve[:, h].T
        # Apply saturation to colors
        pixels += (np.max(pixels, axis=1).reshape(-1, 1) - pixels) * (1 - s)
        # Apply value (brightness) to colors
        pixels *= v

    def render_hsv(self):
        """
        To be defined by child class
        Be sure to update self.hsv_array
        """
        pass

    def time(self, modifier=1.0, timestep=None):
        """
        sawtooth 0->1, looping every 65.536/modifier seconds
        lower modifier, slower looping
        you can consider modifier = 1 / sawtooth period
        """
        period = self._conversion_factor / modifier
        if timestep is None:
            timestep = self._dt
        return (timestep % period) / period

    def triangle(self, x=1.0):
        """
        Perform the 'triangle' wavefunction on a value

        Converts a sawtooth waveform v between 0.0 and 1.0 to a triangle waveform between 0.0 to 1.0. v "wraps" between 0.0 and 1.0.
        """
        return 1 - 2 * np.abs(x - 0.5)

    def sin(self, x=1.0):
        """
        Perform the 'sin' wavefunction on a value

        Converts a sawtooth waveform v between 0.0 and 1.0 to a sinusoidal waveform between 0.0 to 1.0. Same as (1+sin(v*PI2))/2 but faster. v "wraps" between 0.0 and 1.0.
        """
        return 0.5 * np.sin(x * 2 * np.pi) + 0.5

    def square(self, x=1.0, duty=0.5):
        """
        Perform the 'square' wavefunction on a value

        Converts a sawtooth waveform v to a square wave using the provided duty cycle where duty is a number between 0.0 and 1.0. v "wraps" between 0.0 and 1.0.
        """
        return 0.5 * np.sign(duty - x) + 0.5

    def array_triangle(self, a):
        """
        Perform the 'triangle' wavefunction on an array
        """
        np.subtract(a, 0.5, out=a)
        np.abs(a, out=a)
        np.multiply(a, 2, out=a)
        np.subtract(1, a, out=a)

    def array_sin(self, a):
        """
        Perform the 'sin' wavefunction on an array
        """
        np.multiply(2 * np.pi, a, out=a)
        np.sin(a, out=a)
        np.multiply(0.5, a, out=a)
        np.add(0.5, a, out=a)

    def array_square(self, a, duty=0.5):
        """
        Perform the 'square' wavefunction on an array
        """
        np.subtract(duty, a, out=a)
        np.sign(a, out=a)
        np.multiply(0.5, a, out=a)
        np.add(0.5, a, out=a)

    # Perceptual hue utility - for better rainbows

    # The HSV model's hue parameter isn't linear to human perception of equidistant color.
    # fix_hue() and fix_hue_fast() stretch reds and compresses greens and blues to produce a more even rainbow.
    # fix_hue() makes better rainbows and is customizable, but fix_hue_fast() is faster

    # See a more complete discussion and intense approaches at:
    # https://stackoverflow.com/questions/5162458/fade-through-more-more-natural-rainbow-spectrum-in-hsv-hsb

    def fix_hue_fast(self, hue):
        """
        Returns 0-1 hue values for hsv()
        Takes a "perceptual hue" (pH) that aspires to progress evenly across a human-perceived rainbow
        This simpler approach is 40% faster than fixH() but to my eyes, bright greens feel over-represented
        and deep blues are under-represented
        """
        np.mod(hue, 1, out=hue)
        np.subtract(hue, 0.5, out=hue)
        np.divide(hue, 2, out=hue)
        self.array_sin(hue)

    def _roll_hsv(self):
        if self._config["gradient_roll"] == 0:
            return

        self._hsv_roll_counter += self._config["gradient_roll"]

        if self._hsv_roll_counter >= 1.0:
            pixels_to_roll = np.floor(self._hsv_roll_counter)
            self._hsv_roll_counter -= pixels_to_roll

            if "invert_roll" in self._config:
                if self._config["invert_roll"]:
                    pixels_to_roll *= -1

            self.hsv = np.roll(
                self.hsv,
                int(pixels_to_roll),
                axis=0,
            )
