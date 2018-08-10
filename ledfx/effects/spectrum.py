from ledfx.effects.audio import AudioReactiveEffect, ExpFilter
import ledfx.effects.math as math
import voluptuous as vol
import numpy as np


class SpectrumAudioEffect(AudioReactiveEffect):

    NAME = "Spectrum"
    _prev_y = None

    def audio_data_updated(self, data):

        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count, filtered = False)
        filtered_y = data.interpolated_melbank(self.pixel_count, filtered = True)
        if self._prev_y is None:
            self._prev_y = y

        # Update all the filters
        r = data.get_filter(
            filter_key = "filtered_difference",
            filter_size = self.pixel_count,
            alpha_decay = 0.2,
            alpha_rise = 0.99).update(y - filtered_y)
        g = np.abs(y - self._prev_y)
        b = data.get_filter(
            filter_key = "filtered_difference",
            filter_size = self.pixel_count,
            alpha_decay = 0.1,
            alpha_rise = 0.5).update(y)

        self._prev_y = y

        output = np.array([r,g,b]) * 255
        self.pixels = output.T