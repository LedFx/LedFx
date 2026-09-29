import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Lavalamp(AudioReactiveEffect, HSVEffect):
    NAME = "Lava lamp"
    CATEGORY = "Atmospheric"

    class Config(HSVEffect.Config):
        speed: CoercedFloat = Field(
            7, description="Effect Speed modifier", ge=0.1, le=15.0
        )
        contrast: CoercedFloat = Field(
            0.6, description="Difference between lighter and darker spots", ge=0, le=1
        )
        reactivity: CoercedFloat = Field(
            0.3, description="Audio Reactive modifier", ge=0.00001, le=0.9
        )

    config = TypedConfig(Config)

    def config_updated(self, config):
        self._lows_power = 0
        reactivity = self.config.reactivity
        self._lows_filter = self.create_filter(alpha_decay=0.05, alpha_rise=reactivity)
        self._contrast = 1 - self.config.contrast

    def audio_data_updated(self, data):
        self._lows_power = self._lows_filter.update(data.lows_power(filtered=False))

    def render_hsv(self):
        # "Global expression"
        t1 = self.time(self.config.speed * np.maximum(1, 1 + self._lows_power * 0.004))
        t2 = self.time(
            self.config.speed * 2 * np.maximum(1, 1 + self._lows_power * 0.007)
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
