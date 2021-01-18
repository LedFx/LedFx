import numpy as np
import voluptuous as vol

from ledfx.effects.audio import FREQUENCY_RANGES, AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class MagnitudeAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Magnitude"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Bass (60-250Hz)",
            ): vol.In(list(FREQUENCY_RANGES.keys())),
        }
    )

    def config_updated(self, config):
        self._frequency_range = np.linspace(
            FREQUENCY_RANGES[self.config["frequency_range"]].min,
            FREQUENCY_RANGES[self.config["frequency_range"]].max,
            20,
        )

    def audio_data_updated(self, data):

        # Grab the filtered and interpolated melbank data
        magnitude = np.max(data.sample_melbank(list(self._frequency_range)))
        if magnitude > 1.0:
            magnitude = 1.0
        self.pixels = self.apply_gradient(magnitude)
