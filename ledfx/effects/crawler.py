import time

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Crawler(AudioReactiveEffect, HSVEffect):
    NAME = "Crawler"
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
                default=0.25,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "sway",
                description="Sway modifier",
                default=20,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=50)),
            vol.Optional(
                "chop",
                description="Chop modifier",
                default=30,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=100)),
            vol.Optional(
                "stretch",
                description="Stretch modifier",
                default=2.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=10)),
        }
    )

    def on_activate(self, pixel_count):
        self.pc = pixel_count
        self.i = np.arange(pixel_count, dtype=np.float64)
        self.i1 = np.linspace(0, 1, pixel_count)

        self.timestep = 0
        self.last_time = time.time_ns()
        self.dt = 0

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.1)

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(
            data.lows_power(filtered=False)
        )

    def render_hsv(self):
        self.dt = time.time_ns() - self.last_time
        self.timestep += self.dt
        self.timestep += (
            self._lows_power
            * self._config["reactivity"]
            * self._config["speed"]
            * 1000000000.0
        )
        self.last_time = time.time_ns()

        t1 = self.time(
            self._config["speed"] * self._config["sway"],
            timestep=self.timestep,
        )
        t2 = self.time(
            self._config["speed"] * self._config["chop"],
            timestep=self.timestep,
        )
        t3 = self.time(
            self._config["speed"] * self._config["chop"]
            + self._lows_power * self._config["reactivity"]
        )

        h = np.copy(self.i)
        np.add(h, t3 * self.pc, h)
        np.divide(h, self.pc, h)
        np.multiply(h, self._config["stretch"], h)
        np.mod(h, self._config["stretch"] / 10, h)
        np.add(h, self.i1, h)
        np.add(h, self.sin(t1), h)
        v = np.copy(h)
        np.add(v, t2)
        self.array_sin(v)
        np.power(v, 2, v)

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = v
