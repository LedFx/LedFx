import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class MagnitudeAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Magnitude"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
        }
    )

    def on_activate(self, pixel_count):
        self.magnitude = 0

    def config_updated(self, config):
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]

    def audio_data_updated(self, data):
        self.magnitude = getattr(data, self.power_func)()

    def render(self):
        self.pixels = self.apply_gradient(self.magnitude)
