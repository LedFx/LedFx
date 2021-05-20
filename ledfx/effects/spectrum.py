import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect


class SpectrumAudioEffect(AudioReactiveEffect):

    NAME = "Spectrum"
    CATEGORY = "1.0"

    CONFIG_SCHEMA = vol.Schema({})

    _prev_y = None

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)
        self.g = np.zeros(pixel_count)
        self.b = np.zeros(pixel_count)

    def config_updated(self, config):

        # Create all the filters used for the effect
        self._b_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.5)

    def audio_data_updated(self, data):

        # Grab the filtered and interpolated melbank data
        # Grab the filtered melbank
        y = self.melbanks(filtered=False)
        if self._prev_y is None:
            self._prev_y = y
        self.r = self.melbanks(filtered=True)
        self.g = np.abs(y - self._prev_y)
        self.b = self._b_filter.update(y)

        self._prev_y = y

    def render(self):
        output = np.array([self.r, self.g, self.b]) * 255
        return output.T
