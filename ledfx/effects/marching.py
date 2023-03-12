import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Marching(AudioReactiveEffect, HSVEffect):
    NAME = "Marching"
    CATEGORY = "Atmospheric"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "reactivity",
                description="Audio Reactive modifier",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
        }
    )

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.2
        )

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(
            data.lows_power(filtered=False)
        )

    def render_hsv(self):
        # "Global expression"

        t1 = self.time(self._config["speed"] * 20)
        t2 = self.time(self._config["speed"])
        # t1 += self._config["reactivity"] * self._lows_power
        t2 += self._config["reactivity"] * self._lows_power * 20

        # Vectorised pixel expression
        self.w2 = np.linspace(0, 1, self.pixel_count)
        self.w1 = np.copy(self.w2)
        np.add(t1, self.w1, out=self.w1)
        self.array_sin(self.w1)
        self.h = np.copy(self.w1)
        np.subtract(self.h, self.w2, out=self.h)
        self.array_sin(self.h)
        self.array_sin(self.h)
        np.multiply(self.w2, 10, out=self.w2)
        np.subtract(t2 + 2, self.w2, out=self.w2)
        self.array_sin(self.w2)
        np.subtract(self.w1, self.w2, out=self.w2)

        self.hsv_array[:, 0] = self.h
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = self.w2

        # # "Pixel expression"
        # for i in range(self.pixel_count):

        #     w1 = self.wave(t1 + i/self.pixel_count)
        #     w2 = self.wave(t2 - i/self.pixel_count * 10 + 2)
        #     v = w1 - w2
        #     h = self.wave(self.wave(self.wave(t1 + i/self.pixel_count)) - i/self.pixel_count)

        #     self.hsv_array[i] = (h, 1, v)
