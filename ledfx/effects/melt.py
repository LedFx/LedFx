import time

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Melt(AudioReactiveEffect, HSVEffect):
    NAME = "Melt"
    CATEGORY = "Atmospheric"

    class Config(HSVEffect.Config):
        speed: CoercedFloat = Field(
            0.5, description="Effect Speed modifier", ge=0.001, le=1
        )
        reactivity: CoercedFloat = Field(
            0.5, description="Audio Reactive modifier", ge=0.0001, le=1
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.hl = pixel_count
        self.c1 = np.linspace(0, 1, pixel_count)

        self.timestep: float = 0
        self.last_time = time.time_ns()
        self.dt = 0

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.1)

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(data.lows_power(filtered=False))

    def render_hsv(self):
        self.dt = time.time_ns() - self.last_time
        self.timestep += self.dt
        self.timestep += (
            self._lows_power * self.config.reactivity / self.config.speed * 1000000000.0
        )
        self.last_time = time.time_ns()

        t1 = self.time(self.config.speed * 5, timestep=self.timestep)
        t2 = self.time(self.config.speed * 6.5, timestep=self.timestep)

        self.c1[:] = np.linspace(0, 1, self.pixel_count)
        # np.subtract(self.c1, self.hl, out=self.c1)
        # np.abs(self.c1, out=self.c1)
        # np.divide(self.c1, self.hl, out=self.c1)
        np.subtract(1, self.c1, out=self.c1)

        self.v = np.copy(self.c1)
        np.add(self.c1, t2, out=self.c1)

        self.array_sin(self.v)
        np.add(self.v, t1, out=self.v)
        self.array_sin(self.v)
        np.add(self.v, t1, out=self.v)
        self.array_sin(self.v)
        np.power(self.v, 2, out=self.v)

        self.hsv_array[:, 0] = self.c1
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = self.v
