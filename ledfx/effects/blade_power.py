import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect


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
                "blade_color",
                description="NEW Color",
                default="hsl(0, 100%, 25%)",
            ): str,
        }
    )

    def on_activate(self, pixel_count):
        self.bar = 0

    def config_updated(self, config):

        # Create the filters used for the effect
        self.bar_color = np.array(COLORS[self._config["color"]], dtype=float)

    def audio_data_updated(self, data):
        # Get filtered bass power
        self.bar = data.lows_power(filtered=True) * self.config["multiplier"]

    def render(self):
        self.out = np.zeros((self.pixel_count, 3))
        # Map it to the length of the strip and apply it
        bar_idx = int(self.bar * self.pixel_count)
        self.out[:bar_idx] = self.bar_color

        # Update the pixels
        return self.out
