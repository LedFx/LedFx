from functools import lru_cache

import numpy as np


@lru_cache(maxsize=64)
def _normalized_linspace(size):
    return np.linspace(0, 1, size)


def interpolate_pixels(pixels, new_length):
    """Resizes a pixel array by linearly interpolating the values"""
    if len(pixels) == new_length:
        return pixels

    x_old = _normalized_linspace(len(pixels))
    x_new = _normalized_linspace(new_length)
    new_pixels = np.zeros((len(x_new), pixels.shape[1]))

    new_pixels[:, 0] = np.interp(x_new, x_old, pixels[:, 0])
    new_pixels[:, 1] = np.interp(x_new, x_old, pixels[:, 1])
    new_pixels[:, 2] = np.interp(x_new, x_old, pixels[:, 2])

    return new_pixels


class ExpFilter:
    """Simple exponential smoothing filter"""

    def __init__(self, val=None, alpha_decay=0.5, alpha_rise=0.5):
        assert 0.0 < alpha_decay < 1.0, "Invalid decay smoothing factor"
        assert 0.0 < alpha_rise < 1.0, "Invalid rise smoothing factor"
        self.alpha_decay = alpha_decay
        self.alpha_rise = alpha_rise
        self.value = val

    def update(self, value):

        # Handle deferred initilization
        if self.value is None:
            self.value = value
            return self.value

        if isinstance(self.value, (list, np.ndarray, tuple)):
            alpha = value - self.value
            alpha[alpha > 0.0] = self.alpha_rise
            alpha[alpha <= 0.0] = self.alpha_decay
        else:
            alpha = self.alpha_rise if value > self.value else self.alpha_decay

        self.value = alpha * value + (1.0 - alpha) * self.value

        return self.value
