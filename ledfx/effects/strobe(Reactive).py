import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect


class Strobe(AudioReactiveEffect):

    NAME = "Strobe"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Strobe colour", default="white"
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "frequency",
                description="Strobe frequency",
                default="1/16 (◉﹏◉ )",
            ): vol.In(
                list(
                    [
                        "1/2 (.-. )",
                        "1/4 (.o. )",
                        "1/8 (◉◡◉ )",
                        "1/16 (◉﹏◉ )",
                        "1/32 (⊙▃⊙ )",
                    ]
                )
            ),
        }
    )

    def config_updated(self, config):
        MAPPINGS = {
            "1/2 (.-. )": 2,
            "1/4 (.o. )": 4,
            "1/8 (◉◡◉ )": 8,
            "1/16 (◉﹏◉ )": 16,
            "1/32 (⊙▃⊙ )": 32,
        }
        self.color = np.array(COLORS[self._config["color"]], dtype=float)
        self.f = MAPPINGS[self._config["frequency"]]

    def audio_data_updated(self, data):
        beat_oscillator = data.oscillator()[0]
        brightness = (-beat_oscillator % (2 / self.f)) * (self.f / 2)
        self.pixels = np.tile(self.color * brightness, (self.pixel_count, 1))
