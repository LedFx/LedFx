import time

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Fire(AudioReactiveEffect, HSVEffect):
    NAME = "Fire"
    CATEGORY = "Atmospheric"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.04,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=0.5)),
            vol.Optional(
                "color_shift",
                description="Fire color",
                default=0.15,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "intensity",
                description="Fire intensity",
                default=8,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        }
    )

    def on_activate(self, pixel_count):
        self.spark_pixels = np.zeros(self.pixel_count)
        self.h = np.zeros(self.pixel_count)
        self.s = np.zeros(self.pixel_count)
        self.v = np.zeros(self.pixel_count)
        self.delta_last = time.time()

    def config_updated(self, config):
        self.accel = 0.03
        self.speed = self._config["speed"]
        self.cooling = 0.95
        self._lows_power = 0
        self._lows_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.99
        )

        self.spark_count = self._config["intensity"]
        self.color_shift = self._config["color_shift"]
        self.sparks = np.zeros(self.spark_count)
        self.sparkX = np.zeros(self.spark_count)

    def audio_data_updated(self, data):
        _lows_power = self._lows_filter.update(
            np.mean(data.lows_power(filtered=False))
        )
        self.cooling = 0.75 + _lows_power * 0.25
        self.accel = 0.02 + _lows_power * 0.1
        self.speed = self._config["speed"] + _lows_power * 0.01

    def render_hsv(self):
        current_time = time.time()
        delta = (current_time - self.delta_last) * 1000 * self.speed
        self.delta_last = current_time

        pixels = self.spark_pixels

        np.multiply(pixels, self.cooling, out=pixels)

        for k in range(self.pixel_count - 1, 4, -1):
            h1 = pixels[k - 1]
            h2 = pixels[k - 2]
            h3 = pixels[k - 3]
            h4 = pixels[k - 4]
            pixels[k] = (h1 + h2 + h3 * 2 + h4 * 3) / 7

        for i in range(self.spark_count):
            if self.sparks[i] <= 0:
                self.sparks[i] = np.random.random(1)

            self.sparks[i] += self.accel * delta
            ox = self.sparkX[i]
            self.sparkX[i] += self.sparks[i] * self.sparks[i] * delta

            if self.sparkX[i] > self.pixel_count:
                self.sparkX[i] = 0
                self.sparks[i] = 0
                continue

            j = int(ox)
            while j < self.sparkX[i]:
                pixels[j] += np.clip(1 - self.sparks[i] * 0.4, 0, 1) * 0.5
                j += 1

        np.power(pixels, 2, out=self.h)
        np.clip(self.h, 0, 1, out=self.h)
        np.multiply(self.h, 0.1, out=self.h)
        np.add(self.h, self.color_shift, out=self.h)

        np.subtract(pixels, 1, out=self.s)
        np.multiply(self.s, 2, out=self.s)
        np.subtract(1, self.s, out=self.s)

        np.multiply(pixels, 2, out=self.v)

        self.hsv_array[:, 0] = self.h
        self.hsv_array[:, 1] = self.s
        self.hsv_array[:, 2] = self.v
