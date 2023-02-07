import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Lavalamp(AudioReactiveEffect, HSVEffect):
    NAME = "Lava lamp"
    CATEGORY = "Atmospheric"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=15.0)),
            vol.Optional(
                "contrast",
                description="Difference between lighter and darker spots",
                default=0.6,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "reactivity",
                description="Audio Reactive modifier",
                default=0.3,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=0.9)),
        }
    )

    def config_updated(self, config):
        self._lows_power = 0
        reactivity = self._config["reactivity"]
        self._lows_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=reactivity
        )
        self._contrast = 1 - self._config["contrast"]

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(
            data.lows_power(filtered=False)
        )

    def render_hsv(self):
        # "Global expression"
        t1 = self.time(
            self._config["speed"] * np.maximum(1, 1 + self._lows_power * 0.004)
        )
        t2 = self.time(
            self._config["speed"]
            * 2
            * np.maximum(1, 1 + self._lows_power * 0.007)
        )

        # Vectorised pixel expression
        il = np.linspace(0, 1, self.pixel_count)
        w1 = np.add(t1, il)
        self.array_sin(w1)
        w2 = np.subtract(t2, il)
        self.array_sin(w2)

        w3 = np.add(il, w1)
        np.add(w3, w2, out=w3)
        np.mod(w3, 1, out=w3)
        self.array_sin(w3)
        h = np.add(t1, il)

        np.add(w1, 0.1, out=w1)
        np.add(w2, self._lows_power * 0.7, out=w2)
        np.add(w3, self._lows_power * 0.9, out=w3)

        np.multiply(w1, w2, out=w1)
        np.multiply(w1, w3, out=w1)

        h_shift = np.multiply(w1, 0.1)
        np.add(h, h_shift, out=h)

        np.add(w1, self._contrast, out=w1)
        np.power(w1, 2, out=w1)

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = w1
