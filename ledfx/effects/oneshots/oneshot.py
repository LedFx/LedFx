import timeit
from abc import ABC, abstractmethod

import numpy as np


class Oneshot(ABC):
    """
    Base class for all oneshot types.

    Oneshot is an effect that is triggered manually (through, for example, REST API).
    """

    def __init__(self):
        self._active: bool = True
        self._pixel_count: int = 0

    @abstractmethod
    def init(self):
        raise NotImplementedError("Please implement this method")

    @abstractmethod
    def update(self):
        raise NotImplementedError("Please implement this method")

    @abstractmethod
    def apply(self, seg, start, stop):
        raise NotImplementedError("Please implement this method")

    @property
    def active(self):
        return self._active

    @property
    def pixel_count(self):
        return self._pixel_count

    @pixel_count.setter
    def pixel_count(self, pixel_count):
        self._pixel_count = pixel_count


class Flash(Oneshot):

    def __init__(self, color, ramp, hold, fade, brightness):
        """
        Force all pixels in virtual to color over a time envelope defined in ms.

        Parameters:
            color of the flash
            ramp time from in ms
            hold time in ms
            fade time in ms
            brightness of the flash
        Returns:
            True if oneshot was activated, False if not
        """
        super().__init__()
        self._color = np.array(color, dtype=float) * brightness
        self._ramp = ramp / 1000.0
        self._hold = hold / 1000.0
        self._fade = fade / 1000.0
        self._start = timeit.default_timer()
        self._hold_end = self._ramp + self._hold
        self._fade_end = self._ramp + self._hold + self._fade
        self._weight = 0.0

    def init(self):
        return

    def update(self):
        passed = timeit.default_timer() - self._start
        if passed <= self._ramp:
            self._weight = passed / self._ramp
        elif passed <= self._hold_end:
            self._weight = 1.0
        elif passed <= self._fade_end:
            self._weight = (self._fade_end - passed) / self._fade
        else:
            self._active = False
            self._weight = 0.0

    def apply(self, seg, start, stop):
        blend = np.multiply(self._color, self._weight)
        np.multiply(seg, 1 - self._weight, seg)
        np.add(seg, blend, seg)
