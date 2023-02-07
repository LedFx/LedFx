import time

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Glitch(AudioReactiveEffect, HSVEffect):
    NAME = "Glitch"
    CATEGORY = "Atmospheric"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=10.0)),
            vol.Optional(
                "reactivity",
                description="Audio Reactive modifier",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
        }
    )

    def on_activate(self, pixel_count):
        self.i = np.arange(pixel_count, dtype=np.float64)
        self.i2 = np.linspace(0, 5, pixel_count)
        self.i3 = np.linspace(-1, 0, pixel_count)
        np.subtract(self.i, pixel_count / 2, out=self.i)
        np.divide(self.i, pixel_count, out=self.i)

        self.timestep = 0
        self.last_time = time.time_ns()
        self.dt = 0

    def config_updated(self, config):
        self._lows_power = 0

    def audio_data_updated(self, data):
        self._lows_power = data.lows_power()

    def render_hsv(self):
        self.dt = time.time_ns() - self.last_time
        self.timestep += self.dt
        self.timestep += (
            self._lows_power
            * self._config["reactivity"]
            / self._config["speed"]
            * 1e9
        )
        self.last_time = time.time_ns()

        t1 = (
            self.time(self._config["speed"] * 0.5, timestep=self.timestep)
            * np.pi
            * 2
        )
        t2 = self.time(self._config["speed"] * 0.5, timestep=self.timestep)
        t3 = self.time(self._config["speed"] * 2.5, timestep=self.timestep)
        t4 = (
            self.time(self._config["speed"] * 1.0, timestep=self.timestep)
            * np.pi
            * 2
        )
        t5 = self.time(self._config["speed"] * 0.25, timestep=self.timestep)
        t6 = self.time(self._config["speed"] * 10, timestep=self.timestep)

        h = np.copy(self.i)
        s1 = np.copy(self.i2)
        s2 = np.copy(self.i3)

        m = 0.3 + self.triangle(t2) * 0.2
        c = self.triangle(t3) * 10 + 4 * np.sin(t4)

        np.multiply(h, c, out=h)
        np.mod(h, m, out=h)
        np.add(h, np.sin(t1), out=h)
        np.add(t5, s1, out=s1)
        np.mod(s1, 1, out=s1)
        self.array_triangle(s1)
        np.power(s1, 2, out=s1)
        np.subtract(t6, s2, out=s2)
        np.mod(s2, 1, out=s2)
        self.array_triangle(s2)
        np.power(s2, 4, out=s2)
        np.multiply(s1, s2, out=s1)
        self.array_triangle(s1)
        np.subtract(1, s1, out=s1)

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = s1
        self.hsv_array[:, 2] = 1
