import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect


class SpectrumAudioEffect(AudioReactiveEffect):
    NAME = "Spectrum"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema({})

    def on_activate(self, pixel_count):
        self.out = np.zeros((pixel_count, 3))
        self._prev_y = np.zeros(pixel_count)

    def config_updated(self, config):
        # Create all the filters used for the effect
        self._b_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.5)

    def audio_data_updated(self, data):
        # Grab the filtered and interpolated melbank data
        # Grab the filtered melbank
        y = self.melbank(filtered=False, size=self.pixel_count)
        self.out[:, 0] = self.melbank(filtered=True, size=self.pixel_count)
        self.out[:, 1] = np.abs(y - self._prev_y)
        self.out[:, 2] = self._b_filter.update(y)
        self.out *= 1000

        self._prev_y = y

    def render(self):
        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self.out
