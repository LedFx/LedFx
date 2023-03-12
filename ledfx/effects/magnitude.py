import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class MagnitudeAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Magnitude"
    CATEGORY = "Classic"

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
        }
    )

    def on_activate(self, pixel_count):
        self.magnitude = 0

    def config_updated(self, config):
        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        self.magnitude = getattr(data, self.power_func)()

    def render(self):
        self.pixels = self.apply_gradient(self.magnitude)
