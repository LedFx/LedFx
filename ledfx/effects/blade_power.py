import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import FREQUENCY_RANGES, AudioReactiveEffect


class BladePowerAudioEffect(AudioReactiveEffect):

    NAME = "Blade Power"
    CATEGORY = "1.0"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=False,
            ): bool,
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "multiplier",
                description="Make the reactive bar bigger/smaller",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "background_color",
                description="Color of Background",
                default="orange",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "color", description="Color of bar", default="brown"
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Bass (60-250Hz)",
            ): vol.In(list(FREQUENCY_RANGES.keys())),
        }
    )

    def activate(self, pixel_count):
        self.bar = 0
        super().activate(pixel_count)

    def config_updated(self, config):

        # Create the filters used for the effect
        self._bar_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.99)
        self.bar_color = np.array(COLORS[self._config["color"]], dtype=float)
        self._frequency_range = np.linspace(
            FREQUENCY_RANGES[self.config["frequency_range"]].min,
            FREQUENCY_RANGES[self.config["frequency_range"]].max,
            20,
        )

    def audio_data_updated(self, data):
        # Get frequency range power through filter

        self.bar = (
            np.max(data.sample_melbank(list(self._frequency_range)))
            * self.config["multiplier"]
        )
        self.bar = self._bar_filter.update(self.bar)

    def render(self):
        self.out = np.zeros((self.pixel_count, 3))
        # Map it to the length of the strip and apply it
        bar_idx = int(self.bar * self.pixel_count)
        self.out[:bar_idx] = self.bar_color

        # Update the pixels
        return self.out
