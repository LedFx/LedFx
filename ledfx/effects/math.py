import timeit
from functools import lru_cache

import numpy as np
from numpy import asarray, extract, mod, nan, pi, place, zeros


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

    # Interpolate the R,G,B portions of the pixel array
    # Lots of attempts at vectorisation/performance improvements here
    # This appears to be optimal from a readability/performance point of view
    # TODO: If we ever move to RGBW pixel arrays, uncomment the last line to operate on the W portion

    new_pixels[:, 0] = np.interp(x_new, x_old, pixels[:, 0])  # R
    new_pixels[:, 1] = np.interp(x_new, x_old, pixels[:, 1])  # G
    new_pixels[:, 2] = np.interp(x_new, x_old, pixels[:, 2])  # B
    # new_pixels[:, 3] = np.interp(x_new, x_old, pixels[:, 3]) # W
    return new_pixels


# Copied from scipy to avoid importing the entire dependency.
# https://github.com/scipy/scipy/blob/main/scipy/signal/_waveforms.py
# Copyright (c) 2001-2002 Enthought, Inc. 2003-2022, SciPy Developers.
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.

# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.


# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
def sawtooth(t, width=1):
    """
    Return a periodic sawtooth or triangle waveform.

    The sawtooth waveform has a period ``2*pi``, rises from -1 to 1 on the
    interval 0 to ``width*2*pi``, then drops from 1 to -1 on the interval
    ``width*2*pi`` to ``2*pi``. `width` must be in the interval [0, 1].

    Note that this is not band-limited.  It produces an infinite number
    of harmonics, which are aliased back and forth across the frequency
    spectrum.

    Parameters
    ----------
    t : array_like
        Time.
    width : array_like, optional
        Width of the rising ramp as a proportion of the total cycle.
        Default is 1, producing a rising ramp, while 0 produces a falling
        ramp.  `width` = 0.5 produces a triangle wave.
        If an array, causes wave shape to change over time, and must be the
        same length as t.

    Returns
    -------
    y : ndarray
        Output array containing the sawtooth waveform.

    Examples
    --------
    A 5 Hz waveform sampled at 500 Hz for 1 second:

    >>> from scipy import signal
    >>> import matplotlib.pyplot as plt
    >>> t = np.linspace(0, 1, 500)
    >>> plt.plot(t, signal.sawtooth(2 * np.pi * 5 * t))

    """
    t, w = asarray(t), asarray(width)
    w = asarray(w + (t - t))
    t = asarray(t + (w - w))
    if t.dtype.char in ["fFdD"]:
        ytype = t.dtype.char
    else:
        ytype = "d"
    y = zeros(t.shape, ytype)

    # width must be between 0 and 1 inclusive
    mask1 = (w > 1) | (w < 0)
    place(y, mask1, nan)

    # take t modulo 2*pi
    tmod = mod(t, 2 * pi)

    # on the interval 0 to width*2*pi function is
    #  tmod / (pi*w) - 1
    mask2 = (1 - mask1) & (tmod < w * 2 * pi)
    tsub = extract(mask2, tmod)
    wsub = extract(mask2, w)
    place(y, mask2, tsub / (pi * wsub) - 1)

    # on the interval width*2*pi to 2*pi function is
    #  (pi*(w+1)-tmod) / (pi*(1-w))

    mask3 = (1 - mask1) & (1 - mask2)
    tsub = extract(mask3, tmod)
    wsub = extract(mask3, w)
    place(y, mask3, (pi * (wsub + 1) - tsub) / (pi * (1 - wsub)))
    return y


# End BSD-3 Licensed Code


# Specialization of sawtooth for a triangle wave. Output is often similar enough
# to a sine wave, but much faster
def triangle(a):
    a = sawtooth(a * np.pi * 2, 0.5)
    np.multiply(a, 0.5, out=a)
    return np.add(a, 0.5)


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


def interpolate_colors(c1, c2, elements):
    """
    Create np color array of equally interpolated values between c1 and c2

    Paramenters:
        c1 a color defined by 3 floats in np array
        c2 a color defined by 3 floats in np array
        elements int value for number of elements in the returned np array

    Returns:
        np.ndarry: np array of equally interpolated color values between
        c1 and c2
    """
    t = np.linspace(0, 1, elements)[:, np.newaxis]
    # Interpolate the colors using broadcasting
    return c1 * (1 - t) + c2 * t


def roll_pixel_array(array, fraction):
    """
    roll a color np array by a fraction of its length

    Paramters:
        array np array of colors
        fraction float value between -1 and 1

    Returns:
        np.ndarry: np array of colors rolled by fraction of its length
    """

    length = array.shape[0]
    shift_amount = int(length * fraction)
    rolled_array = np.roll(array, shift_amount, axis=0)
    return rolled_array


def time_factor(window):
    """
    Returns a value between 0 and 1 based on time modulated by window
    So for example if you want a value that runs from 0 to 1 every 3 seconds
    you would call time_factor(3)

    Paramters:
        window float value of the window in seconds

    Returns:
        float: value between 0 and 1
    """

    return (timeit.default_timer() % window) / window


def make_pattern(color, length, step):
    """
    builds a pattern of quater segments
    full color, fade to dim, dim color, fade to full
    rolls the pattern based on time modulated
    So we don't care when we started or what the update rate is

    Paramters:
        color np array of 3 floats
        length int value of the length of the pattern required
        step value which implies direction of roll

    Returns:
        np.ndarry: np array of colors rolled by fraction of its length
    """

    factor = time_factor(3)
    color2 = color * 0.2
    quart = int(length / 4)
    extra = length - quart * 4
    pattern = np.vstack(
        (
            interpolate_colors(color, color, quart),
            interpolate_colors(color, color2, quart),
            interpolate_colors(color2, color2, quart),
            interpolate_colors(color2, color, quart + extra),
        )
    )
    pattern = roll_pixel_array(pattern, factor * step)
    return pattern
