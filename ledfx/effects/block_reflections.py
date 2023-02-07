import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class BlockReflections(AudioReactiveEffect, HSVEffect):
    NAME = "Block Reflections"
    CATEGORY = "Atmospheric"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "reactivity",
                description="Audio Reactive modifier",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
        }
    )

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.05
        )

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(
            data.lows_power(filtered=False)
        )

    def render_hsv(self):
        t2 = self.time(1 * self._config["speed"]) * (np.pi**2) + (
            0.8 * self._config["reactivity"] * self._lows_power
        )
        t1 = self.time(1 * self._config["speed"])
        t3 = self.time(5 * self._config["speed"]) + (
            self._config["reactivity"] * self._lows_power
        )
        t4 = self.time(2 * self._config["speed"]) * (np.pi**2)

        m = 0.3 + self.triangle(t1) * 0.2
        c = self.triangle(t3) * 10 + 4 * self.sin(t4)
        s = 1

        h = np.arange(self.pixel_count, dtype=np.float64)
        np.subtract(h, self.pixel_count / 2, out=h)
        np.divide(h, self.pixel_count, out=h)
        np.multiply(h, c, out=h)
        np.mod(h, m, out=h)
        np.add(h, self.sin(t2), out=h)

        v = np.abs(h)
        np.add(v, abs(m) + t1, out=v)
        np.mod(v, 1, out=v)
        np.power(v, 2, out=v)

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = s
        self.hsv_array[:, 2] = v
