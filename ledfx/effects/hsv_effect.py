import time

import numpy as np

from ledfx.effects import Effect


@Effect.no_registration
class HSVEffect(Effect):

    # CONFIG_SCHEMA = vol.Schema(
    #     {}
    # )

    _last_time = time.time()
    _timestep = 0
    hsv_array = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def activate(self, pixel_count):
        self.hsv_array = np.ones((pixel_count, 3))
        super().activate(pixel_count)

    # def _invalidate_caches(self):
    #     """Invalidates the cache for all wavefunctions"""
    #     self.time.cache_clear()
    #     self.triangle.cache_clear()
    #     self.sin.cache_clear()
    #     self.square.cache_clear()

    def get_pixels(self):
        # self._invalidate_caches()
        self._update_timestep()
        self.render()
        return self.hsv_to_rgb(self.hsv_array)

    def render(self):
        """
        To be defined by child class
        Be sure to update self.hsv_array
        """
        pass

    def _update_timestep(self):
        time_now = time.time()
        self._timestep += time_now - self._last_time
        self._last_time = time_now

    def time(self, modifier=1.0):
        return modifier * self._timestep % 1

    def triangle(self, x=1.0):
        return 1 - 2 * np.abs(x - 0.5)

    def sin(self, x=1.0):
        return 0.5 * np.sin(x * 2 * np.pi) + 0.5

    def square(self, x=1.0):
        return 0.5 * np.sign(np.sin(x * 2 * np.pi)) + 0.5

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
