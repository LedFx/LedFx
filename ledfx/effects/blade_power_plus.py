import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.hsv_effect import HSVEffect


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
                default="black",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "color", description="Color of bar", default="cyan"
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "solid_color",
                description="Display a solid color bar",
                default=False,
            ): bool,
            vol.Optional(
                "invert_roll",
                description="Invert the direction of the gradient roll",
                default=False,
            ): bool,
            # vol.Optional(
            #    "blade_color",
            #    description="NEW Color",
            #    default="hsl(0, 100%, 25%)",
            # ): str,
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

        if self.config["solid_color"] is True:
            hsv_color = self.rgb_to_hsv(
                np.array(COLORS[self._config["color"]])
            )
            self.hsv[:, 0] = hsv_color[0]
            self.hsv[:, 1] = hsv_color[1]
            self.hsv[:, 2] = hsv_color[2]

    def config_updated(self, config):
        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = (
            getattr(data, self.power_func)() * self.config["multiplier"] * 2
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
        self.out[:bar_idx, 2] = self.config["brightness"]

        self.hsv_array = self.out
