import time

import numpy as np
import voluptuous as vol

from ledfx.effects import Effect

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


@Effect.no_registration
class HSVEffect(Effect):

    hMapSize = 10
    binWidth = 1 / (
        hMapSize - 1
    )  # A 10-point map divides hue's 0-1 phase into 9 arcs of length (binWidth) 0.111
    hMap = np.zeros(hMapSize + 1)
    # The values below were subjectively chosen for perceived equidistant color
    hMap[0] = 0.00  # red
    hMap[1] = 0.015  # orange
    hMap[2] = 0.08  # yellow
    hMap[3] = 0.30  # green
    hMap[4] = 0.44  # cyan
    hMap[5] = 0.65  # blue
    hMap[6] = 0.70  # indigo
    hMap[7] = 0.77  # purple
    hMap[8] = 0.985  # pink
    hMap[9] = 1.00  # red again - same as 0
    hMap[10] = 1.00  # overflow bin

    CONFIG_SCHEMA = vol.Schema(
        {
            # vol.Optional(
            #     "color_correction",
            #     description="Color correct hue for more vivid colors",
            #     default=True,
            # ): bool
        }
    )

    _start_time = time.time_ns()
    # 65.536 s expressed in ns
    _conversion_factor = 65.536 * 1000000000.0

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._config["color_correction"] = True
        self._dt = 0
        self.hsv_array = None

    def activate(self, pixel_count):
        self.hsv_array = np.zeros((pixel_count, 3))
        super().activate(pixel_count)

    def render(self):
        # update the timestep, converting ns to s
        self._dt = time.time_ns() - self._start_time

        self.render_hsv()
        if self._config["color_correction"]:
            self.fix_hue_fast(self.hsv_array[:, 0])
        return self.hsv_to_rgb(self.hsv_array)

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

    def fix_hue(self, hue):
        """
        fix_hue(hue) => hue
        Returns 0-1 hue values for hsv()
        Takes a "perceptual hue" (pH) that aspires to progress evenly across a human-perceived rainbow

        # CURRENTLY BUGGED, MAKING WEIRD COLOURS!
        """
        # Wrap inputs
        np.mod(hue, 1, out=hue)
        # Calculate hue's starting bin index, 0..(hMapSize-1)
        bin = np.divide(hue, self.binWidth)
        bin = np.floor(bin).astype(np.int)
        # Find hue's percentage into that bin index
        binPct = np.mod(hue, self.binWidth)
        np.divide(hue, self.binWidth, out=binPct)
        # base value in hsv()'s h unit
        base = self.hMap[bin]
        # gap is the distance in hsv()'s h units between this base bin and the next
        np.add(bin, 1, out=bin)
        gap = self.hMap[bin]
        np.subtract(gap, base, out=gap)
        # Interpolate the result between the base bin's h value and the next bin's
        np.multiply(binPct, gap, out=gap)
        np.add(base, gap, out=hue)

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

    def hsv_to_rgb(self, hsv):
        """
        Convert pixel array of type np.array([[h,s,v], ...])
                                 to np.array([[r,g,b], ...])

        Copied from:
        https://gist.github.com/PolarNick239/691387158ff1c41ad73c

        >>> from colorsys import hsv_to_rgb as hsv_to_rgb_single
        >>> 'r={:.0f} g={:.0f} b={:.0f}'.format(*hsv_to_rgb_single(0.60, 0.79, 239))
        'r=50 g=126 b=239'
        >>> 'r={:.0f} g={:.0f} b={:.0f}'.format(*hsv_to_rgb_single(0.25, 0.35, 200.0))
        'r=165 g=200 b=130'
        >>> np.set_printoptions(0)
        >>> hsv_to_rgb(np.array([[[0.60, 0.79, 239], [0.25, 0.35, 200.0]]]))
        array([[[  50.,  126.,  239.],
                [ 165.,  200.,  130.]]])
        >>> 'r={:.0f} g={:.0f} b={:.0f}'.format(*hsv_to_rgb_single(0.60, 0.0, 239))
        'r=239 g=239 b=239'
        >>> hsv_to_rgb(np.array([[0.60, 0.79, 239], [0.60, 0.0, 239]]))
        array([[  50.,  126.,  239.],
               [ 239.,  239.,  239.]])
        """
        input_shape = hsv.shape
        hsv = hsv.reshape(-1, 3)
        h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2] * 256
        # print(f"H:\n{h}\nS:\n{s}\nV:\n{v}\n")

        i = np.int32(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6

        rgb = np.zeros_like(hsv)
        v, t, p, q = (
            v.reshape(-1, 1),
            t.reshape(-1, 1),
            p.reshape(-1, 1),
            q.reshape(-1, 1),
        )
        rgb[i == 0] = np.hstack([v, t, p])[i == 0]
        rgb[i == 1] = np.hstack([q, v, p])[i == 1]
        rgb[i == 2] = np.hstack([p, v, t])[i == 2]
        rgb[i == 3] = np.hstack([p, q, v])[i == 3]
        rgb[i == 4] = np.hstack([t, p, v])[i == 4]
        rgb[i == 5] = np.hstack([v, p, q])[i == 5]
        rgb[s <= 0.0] = np.hstack([v, v, v])[s <= 0.0]

        return rgb.reshape(input_shape)

    def rgb_to_hsv(self, rgb):
        """
        Convert pixel array of type np.array([[r,g,b], ...])
                                 to np.array([[h,s,v], ...])

        Copied from:
        https://gist.github.com/PolarNick239/691387158ff1c41ad73c

        >>> from colorsys import rgb_to_hsv as rgb_to_hsv_single
        >>> 'h={:.2f} s={:.2f} v={:.2f}'.format(*rgb_to_hsv_single(50, 120, 239))
        'h=0.60 s=0.79 v=239.00'
        >>> 'h={:.2f} s={:.2f} v={:.2f}'.format(*rgb_to_hsv_single(163, 200, 130))
        'h=0.25 s=0.35 v=200.00'
        >>> np.set_printoptions(2)
        >>> rgb_to_hsv(np.array([[[50, 120, 239], [163, 200, 130]]]))
        array([[[   0.6 ,    0.79,  239.  ],
                [   0.25,    0.35,  200.  ]]])
        >>> 'h={:.2f} s={:.2f} v={:.2f}'.format(*rgb_to_hsv_single(100, 100, 100))
        'h=0.00 s=0.00 v=100.00'
        >>> rgb_to_hsv(np.array([[50, 120, 239], [100, 100, 100]]))
        array([[   0.6 ,    0.79,  239.  ],
               [   0.  ,    0.  ,  100.  ]])
        """
        input_shape = rgb.shape
        rgb = rgb.reshape(-1, 3)
        r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]

        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        v = maxc

        deltac = maxc - minc
        s = deltac / maxc
        deltac[
            deltac == 0
        ] = 1  # to not divide by zero (those results in any way would be overridden in next lines)
        rc = (maxc - r) / deltac
        gc = (maxc - g) / deltac
        bc = (maxc - b) / deltac

        h = 4.0 + gc - rc
        h[g == maxc] = 2.0 + rc[g == maxc] - bc[g == maxc]
        h[r == maxc] = bc[r == maxc] - gc[r == maxc]
        h[minc == maxc] = 0.0

        h = (h / 6.0) % 1.0
        res = np.dstack([h, s, v])
        return res.reshape(input_shape)
