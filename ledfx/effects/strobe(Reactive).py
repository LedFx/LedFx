import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect


class Strobe(AudioReactiveEffect):

    MAPPINGS = {
        "1/2 (.-. )": 2,
        "1/4 (.o. )": 4,
        "1/8 (◉◡◉ )": 8,
        "1/16 (◉﹏◉ )": 16,
        "1/32 (⊙▃⊙ )": 32,
    }

    NAME = "Strobe"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Strobe colour", default="white"
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "frequency",
                description="Strobe frequency",
                default=list(MAPPINGS.keys())[1],
            ): vol.In(list(MAPPINGS.keys())),
        }
    )

    def activate(self, pixel_count):
        self.output = np.zeros((pixel_count, 3))
        self.brightness = 0
        super().activate(pixel_count)

    def config_updated(self, config):
        self.color = np.array(COLORS[self._config["color"]], dtype=float)
        self.f = self.MAPPINGS[self._config["frequency"]]

    def audio_data_updated(self, data):
        beat_oscillator = data.oscillator()[0]
        self.brightness = (-beat_oscillator % (2 / self.f)) * (self.f / 2)

    def render(self):
        self.output[:] = self.color * self.brightness
        return self.output
