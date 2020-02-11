from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.color import COLORS
import voluptuous as vol
import numpy as np

class BarAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Bar"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
    })

    def config_updated(self, config):
        self._color_idx = 0 
        self.dot_idx = 0
        self._color = COLORS["red"]

    def audio_data_updated(self, data):
        # Calculate the length of the bar
        bar_length = int(self.pixel_count * 0.5 * np.mean(np.clip(data.melbank_lows(), 0, 2)))
        self.dot_idx = bar_length if bar_length > self.dot_idx else self.dot_idx - 1

        # If beat detected, shift colour along 1/10th the gradient
        if self.beat_detected():
            self._color_idx = (self._color_idx + self.pixel_count // 10) % self.pixel_count
            self._color = self.get_gradient_color(self._color_idx)

        # Construct the bar and dot
        p = np.zeros(np.shape(self.pixels))
        p[:bar_length, :] = self._color
        p[self.dot_idx, :] = COLORS["white"]

        # Update the pixel values
        self.pixels = p