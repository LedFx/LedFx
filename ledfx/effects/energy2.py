import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Energy2(AudioReactiveEffect, HSVEffect):
    NAME = "Energy 2"
    CATEGORY = "Atmospheric"

    class Config(HSVEffect.Config):
        speed: CoercedFloat = Field(
            0.1, description="Effect Speed modifier", ge=0.00001, le=1.0
        )
        reactivity: CoercedFloat = Field(
            0.2, description="Audio Reactive modifier", ge=0.00001, le=1.0
        )

    config = TypedConfig(Config)

    def config_updated(self, config):
        self._lows_power = 0
        self._lows_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.1)

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(data.lows_power(filtered=False))

    def render_hsv(self):
        # "Global expression"

        t1 = self.time(self.config.speed)

        # Vectorised pixel expression
        self.v = np.linspace(0, 1, self.pixel_count)
        np.add(
            2.0 * self.sin(t1 + self.config.reactivity * self._lows_power),
            self.v,
            out=self.v,
        )
        np.mod(self.v, 1, out=self.v)
        self.array_triangle(self.v)
        np.power(self.v, 2, out=self.v)
        s = self.v < (0.9 - (self.config.reactivity + 0.3) * self._lows_power)

        self.hsv_array[:, 0] = self._lows_power + t1
        self.hsv_array[:, 1] = s
        self.hsv_array[:, 2] = self.v

        # # "Pixel expression"
        # for i in range(self.pixel_count):

        #     v = self.triangle(
        #         (2.0 * self.sin(t1) + i / self.pixel_count) % 1.0
        #     )
        #     v **= 5.0
        #     s = v < 0.9
        #     self.hsv_array[i] = (self._lows_power, s, v)
