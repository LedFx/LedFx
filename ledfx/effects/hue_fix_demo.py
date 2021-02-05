import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class HueFixDemo(AudioReactiveEffect, HSVEffect):

    NAME = "Hue Fix Demo"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color_correction",
                description="Color correct hue for more vivid colors",
                default=False,
            ): bool,
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
        }
    )

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.1)

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(data.melbank_lows().max())

    def render_hsv(self):
        # "Global expression"

        t1 = self.time(self._config["speed"])  # Animate hue's phase angle
        t2 = self.time(0.1)  # Switch between modes every couple seconds

        # Vectorised pixel expression
        # Cycle three modes: linear h, fix_hue(), and fix_hue_fast()
        # Remove t1 to freeze the rainbow. Add 0.5 to inspect reds.
        h = np.linspace(0, 1, self.pixel_count)
        np.add(t1, h, out=h)

        if (t2 > 0.33) and (t2 < 0.66):
            self.fix_hue(h)

        elif t2 > 0.66:
            self.fix_hue_fast(h)

        # Blink off between the modes being compared
        v = (t2 % 0.33) > 0.05

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = v
