import logging
from collections import namedtuple

import numpy as np
import voluptuous as vol

from ledfx.color import validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.hsv_effect import HSVEffect

RGB = namedtuple("RGB", "red, green, blue")
hsv = namedtuple("hsv", "hue, saturation, value")

_LOGGER = logging.getLogger(__name__)


class BladePowerPlus(AudioReactiveEffect, HSVEffect, GradientEffect):

    NAME = "Blade Power+"
    CATEGORY = "2.0"

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

        #   HSV array is in vertical orientation:
        #   Pixel 1: [ H, S, V ]
        #   Pixel 2: [ H, S, V ]
        #   Pixel 3: [ H, S, V ] and so on...

        self.hsv = np.zeros((pixel_count, 3))
        self.bar = 0

        rgb_gradient = self.apply_gradient(1)
        self.hsv = self.rgb_to_hsv(rgb_gradient)

    def config_updated(self, config):
        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = (
            getattr(data, self.power_func)() * self._config["multiplier"] * 2
        )

    def render_hsv(self):
        # Must be zeroed every cycle to clear the previous frame
        self.out = np.zeros((self.pixel_count, 3))
        bar_idx = int(self.bar * self.pixel_count)

        # Manually roll gradient because apply_gradient is only called once in activate instead of every render
        self._roll_hsv()

        # Construct hsv array
        self.out[:, 0] = self.hsv[:, 0]
        self.out[:, 1] = self.hsv[:, 1]
        self.out[:bar_idx, 2] = self._config["brightness"]

        self.hsv_array = self.out
