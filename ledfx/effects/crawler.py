import time

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Crawler(AudioReactiveEffect, HSVEffect):
    NAME = "Crawler"
    CATEGORY = "Atmospheric"

    class Config(HSVEffect.Config):
        speed: CoercedFloat = Field(
            0.5, description="Effect Speed modifier", ge=0.00001, le=1.0
        )
        reactivity: CoercedFloat = Field(
            0.25, description="Audio Reactive modifier", ge=0.00001, le=1.0
        )
        sway: CoercedFloat = Field(20, description="Sway modifier", ge=0.00001, le=50)
        chop: CoercedFloat = Field(30, description="Chop modifier", ge=0.00001, le=100)
        stretch: CoercedFloat = Field(
            2.5, description="Stretch modifier", ge=0.00001, le=10
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.pc = pixel_count
        self.i = np.arange(pixel_count, dtype=np.float64)
        self.i1 = np.linspace(0, 1, pixel_count)

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
            self._lows_power * self.config.reactivity * self.config.speed * 1000000000.0
        )
        self.last_time = time.time_ns()

        t1 = self.time(
            self.config.speed * self.config.sway,
            timestep=self.timestep,
        )
        t2 = self.time(
            self.config.speed * self.config.chop,
            timestep=self.timestep,
        )
        t3 = self.time(
            self.config.speed * self.config.chop
            + self._lows_power * self.config.reactivity
        )

        h = np.copy(self.i)
        np.add(h, t3 * self.pc, h)
        np.divide(h, self.pc, h)
        np.multiply(h, self.config.stretch, h)
        np.mod(h, self.config.stretch / 10, h)
        np.add(h, self.i1, h)
        np.add(h, self.sin(t1), h)
        v = np.copy(h)
        np.add(v, t2)
        self.array_sin(v)
        np.power(v, 2, v)

        self.hsv_array[:, 0] = h
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = v
