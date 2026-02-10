import time
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


class CalibratorPatternCache:
    """
    Manages cached calibration patterns for efficient rendering.

    The pattern consists of 4 phases:
    1. Full brightness
    2. Fade to dim (20%)
    3. Dim brightness
    4. Fade to full

    Patterns are pre-computed and cached, then animated by rolling.
    Pre-parses calibration colors to avoid repeated parsing overhead.
    """

    # Pre-parsed calibration colors (RGBCMY) as numpy arrays
    _CALIBRATION_COLORS = None
    _BLACK_COLOR = None
    _WHITE_COLOR = None

    def __init__(self, animation_period=3.0, dim_factor=0.2):
        """
        Args:
            animation_period: Time in seconds for one complete animation cycle
            dim_factor: Brightness multiplier for dim phase (0.0-1.0)
        """
        self.animation_period = animation_period
        self.dim_factor = dim_factor
        self._time_offset = time.perf_counter()  # For animation timing
        self._color_index = 0  # For cycling through colors

        # Initialize pre-parsed colors on first instantiation
        if CalibratorPatternCache._CALIBRATION_COLORS is None:
            from ledfx.color import parse_color

            color_names = [
                "red",
                "green",
                "blue",
                "cyan",
                "magenta",
                "#ffff00",
            ]
            CalibratorPatternCache._CALIBRATION_COLORS = [
                np.array(parse_color(name), dtype=float)
                for name in color_names
            ]
            CalibratorPatternCache._BLACK_COLOR = np.array(
                [0.0, 0.0, 0.0], dtype=float
            )
            CalibratorPatternCache._WHITE_COLOR = np.array(
                parse_color("white"), dtype=float
            )

    def get_next_color(self):
        """
        Get the next color in the calibration sequence (RGBCMY).

        Returns:
            np.ndarray: RGB color array
        """
        color = self._CALIBRATION_COLORS[self._color_index]
        self._color_index = (self._color_index + 1) % len(
            self._CALIBRATION_COLORS
        )
        return color

    def reset_color_sequence(self):
        """Reset color sequence to start from red."""
        self._color_index = 0

    @property
    def black_color(self):
        """Get cached black color array."""
        return self._BLACK_COLOR

    @property
    def white_color(self):
        """Get cached white color array."""
        return self._WHITE_COLOR

    @staticmethod
    @lru_cache(maxsize=32)
    def _create_base_pattern(length, dim_factor):
        """
        Creates a base calibration pattern for a given length.

        This is cached based on length and dim_factor.
        Uses efficient numpy operations to create the entire pattern at once.

        Args:
            length: Number of pixels in the pattern
            dim_factor: Brightness multiplier for dim phase

        Returns:
            np.ndarray: Shape (length, 1) with brightness values 0.0-1.0
        """
        # Create brightness envelope for entire pattern using vectorized operations
        # This is much faster than creating 4 separate interpolations and vstacking
        indices = np.arange(length)

        # Determine which phase each pixel is in
        phase = (indices / length) * 4.0  # 0-4 range

        # Calculate brightness for each pixel based on phase
        brightness = np.ones(length)

        # Phase 0: [0.0, 1.0) - Full brightness (1.0)
        # Phase 1: [1.0, 2.0) - Fade from 1.0 to dim_factor
        # Phase 2: [2.0, 3.0) - Dim brightness (dim_factor)
        # Phase 3: [3.0, 4.0) - Fade from dim_factor to 1.0

        # Vectorized brightness calculation
        mask_phase1 = (phase >= 1.0) & (phase < 2.0)
        mask_phase2 = (phase >= 2.0) & (phase < 3.0)
        mask_phase3 = (phase >= 3.0) & (phase < 4.0)

        brightness[mask_phase1] = 1.0 - (phase[mask_phase1] - 1.0) * (
            1.0 - dim_factor
        )
        brightness[mask_phase2] = dim_factor
        brightness[mask_phase3] = dim_factor + (phase[mask_phase3] - 3.0) * (
            1.0 - dim_factor
        )

        # Return as (length, 1) array for broadcasting with color
        return brightness[:, np.newaxis]

    def get_pattern(self, color, length, step):
        """
        Get an animated calibration pattern for the current time.

        This is the optimized replacement for make_pattern() in calibration mode.

        Args:
            color: RGB color as numpy array [R, G, B] with values 0.0-255.0
            length: Number of pixels in the pattern
            step: Direction multiplier (+1 or -1 for forward/reverse)

        Returns:
            np.ndarray: Shape (length, 3) with RGB values
        """
        # Get or create cached base pattern
        base_pattern = self._create_base_pattern(length, self.dim_factor)

        # Apply color (broadcasting: (length, 1) * (3,) -> (length, 3))
        pattern = base_pattern * color

        # Calculate roll amount based on current time
        time_fraction = (
            (time.perf_counter() - self._time_offset) % self.animation_period
        ) / self.animation_period
        shift_amount = int(length * time_fraction * step)

        # Roll the pattern
        if shift_amount != 0:
            pattern = np.roll(pattern, shift_amount, axis=0)

        return pattern

    def get_pattern_batch(self, segments_data, current_time=None):
        """
        Generate patterns for multiple segments efficiently.

        This allows sharing the time calculation across all segments.

        Args:
            segments_data: List of (color, length, step) tuples
            current_time: Optional pre-calculated time (avoids timer call)

        Returns:
            List of pattern arrays
        """
        if current_time is None:
            current_time = time.perf_counter()

        time_fraction = (
            (current_time - self._time_offset) % self.animation_period
        ) / self.animation_period

        patterns = []
        for color, length, step in segments_data:
            base_pattern = self._create_base_pattern(length, self.dim_factor)
            pattern = base_pattern * color

            shift_amount = int(length * time_fraction * step)
            if shift_amount != 0:
                pattern = np.roll(pattern, shift_amount, axis=0)

            patterns.append(pattern)

        return patterns
