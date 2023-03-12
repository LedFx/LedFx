import logging
from collections import namedtuple

import numpy as np
import voluptuous as vol

from ledfx.color import validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect

RGB = namedtuple("RGB", "red, green, blue")
hsv = namedtuple("hsv", "hue, saturation, value")

_LOGGER = logging.getLogger(__name__)


class BladePowerPlus(AudioReactiveEffect, HSVEffect):
    NAME = "Blade Power+"
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
                "decay",
                description="Rate of color decay",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(0, 1)),
            vol.Optional(
                "multiplier",
                description="Make the reactive bar bigger/smaller",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "background_color",
                description="Color of Background",
                default="#000000",
            ): validate_color,
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "invert_roll",
                description="Invert the direction of the gradient roll",
                default=False,
            ): bool,
        }
    )

    def on_activate(self, pixel_count):
        self.bar = 0
        self.hsv_array[:, 0] = np.linspace(0, 1, self.pixel_count)
        self.hsv_array[:, 1] = 1

    def config_updated(self, config):
        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = (
            getattr(data, self.power_func)() * self._config["multiplier"] * 2
        )

    def render_hsv(self):
        # Must be zeroed every cycle to clear the previous frame
        bar_idx = int(self.bar * self.pixel_count)
        self.hsv_array[:, 2] *= self._config["decay"] / 2 + 0.45
        self.hsv_array[:bar_idx, 2] = self._config["brightness"]
