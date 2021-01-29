import time

import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect


class HSVTest(AudioReactiveEffect):

    NAME = "HSV Test"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="red"
            ): vol.In(list(COLORS.keys())),
        }
    )

    def activate(self, pixel_count):
        self.hsv_array = np.ones((pixel_count, 3))
        self.colour_array = np.linspace(0, 1, num=pixel_count)
        self.colour_array = np.sin(range(pixel_count))

        # self.hsv_array[:, 0] *= self.colour_array
        self.last_time = time.time()
        self._timestep = 0
        super().activate(pixel_count)

    def timestep(self, modifier=1):
        dt = time.time() - self.last_time
        self.last_time = time.time()
        self._timestep += dt * modifier
        self._timestep %= 1
        return self._timestep

    def triangle(self, x):
        return 1 - 2 * np.abs(x - 0.5)

    def audio_data_updated(self, data):
        dt = self.timestep(modifier=0.1)
        triangle = 1 - 2 * np.abs(dt - 0.5)
        sin = np.sin(dt * 2 * np.pi)
        square = 0.5 * np.sign(sin) + 0.5
        sin = 0.5 * sin + 0.5
        self._dirty = True

        # print(dt, sin, square, triangle)
        # lows_power = min(data.melbank_lows().max(), 1)

        for i in range(self.pixel_count):
            v = self.triangle((2 * sin + i / self.pixel_count) % 1)
            v **= 5
            s = v < 0.9
            self.hsv_array[i] = (dt, s, v)

    def get_pixels(self):
        return self.hsv_to_rgb(self.hsv_array)

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
        rgb[s <= 0.0] = np.hstack([v, v, v])[s == 0.0]

        return rgb.reshape(input_shape)


def rgb_to_hsv(rgb):
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
