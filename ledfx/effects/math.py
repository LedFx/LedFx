from functools import lru_cache

import numpy as np

from ledfx.utils import NUMBA_AVAILABLE, maybe_jit


@lru_cache(maxsize=32)
def _normalized_linspace(size):
    return np.linspace(0, 1, size)


@maybe_jit()
def interpolate(pixels, x_new, x_old):
    """Resizes pixels array by linearly interpolating the values"""
    new_pixels = np.zeros((len(x_new), pixels.shape[1]))
    for i in range(3):
        new_pixels[:, i] = np.interp(x_new, x_old, pixels[:, i])
    return new_pixels


def interpolate_pixels(pixels, new_length):
    """Resizes a pixel array by linearly interpolating the values"""
    if len(pixels) == new_length:
        return pixels

    x_old = _normalized_linspace(len(pixels))
    x_new = _normalized_linspace(new_length)

    return interpolate(pixels, x_new, x_old)


@maybe_jit()
def update_array_nb(value_new, value_old, alpha_rise, alpha_decay):
    alpha = value_new - value_old
    shape = alpha.shape
    alpha = alpha.flatten()
    for i in range(len(alpha)):
        alpha[i] = alpha_rise if i > 0 else alpha_decay
    alpha = alpha.reshape(shape)
    value_new *= alpha
    value_new += (1.0 - alpha) * value_old
    return value_new


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
            if NUMBA_AVAILABLE:
                self.value = update_array_nb(
                    value, self.value, self.alpha_rise, self.alpha_decay
                )
            else:
                alpha = value - self.value
                alpha[alpha > 0.0] = self.alpha_rise
                alpha[alpha <= 0.0] = self.alpha_decay
                self.value = alpha * value + (1.0 - alpha) * self.value
        else:
            alpha = self.alpha_rise if value > self.value else self.alpha_decay
            self.value = alpha * value + (1.0 - alpha) * self.value

        return self.value
