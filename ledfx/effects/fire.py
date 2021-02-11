import time

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


class Fire(AudioReactiveEffect, HSVEffect):

    NAME = "Fire"
    CATEGORY = "2.0"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed modifier",
                default=0.04,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=0.5))
        }
    )

    def activate(self, pixel_count):
        super().activate(pixel_count)
        self.numSparks = 3
        self.sparks = np.zeros(self.numSparks)
        self.sparkX = np.zeros(self.numSparks)
        self.spark_pixels = np.zeros(self.pixel_count)
        self.delta_last = time.time()

        for i in range(0, self.numSparks):
            self.sparks[i] = np.random.random() * 4
            self.sparkX[i] = np.random.randint(self.pixel_count)

    def config_updated(self, config):
        self.accel = 0.03
        self.speed = self._config["speed"]
        self.cooling1 = 0.04
        self.cooling2 = 0.95
        self._lows_power = 0
        self._lows_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.1)

    def audio_data_updated(self, data):
        _lows_power = self._lows_filter.update(data.melbank_lows().max())
        self.cooling2 = 0.88 + _lows_power * 0.1
        self.accel = 0.02 + _lows_power * 0.06
        self.speed = self._config["speed"] + _lows_power * 0.01

    def render_hsv(self):
        current_time = time.time()
        delta = (current_time - self.delta_last) * 1000
        self.delta_last = current_time

        delta = delta * self.speed
        pixels = self.spark_pixels

        for i in range(0, self.pixel_count):
            cooldown = self.cooling1 * delta
            if cooldown > pixels[i]:
                pixels[i] = 0
            else:
                pixels[i] = pixels[i] * self.cooling2 - cooldown

        for k in range(self.pixel_count - 1, 4, -1):
            h1 = pixels[k - 1]
            h2 = pixels[k - 2]
            h3 = pixels[k - 3]
            h4 = pixels[k - 4]
            pixels[k] = (h1 + h2 + h3 * 2 + h4 * 3) / 7

        for i in range(0, self.numSparks):

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

        for index in range(0, self.pixel_count):
            v = pixels[index]
            h = 0.1 * np.clip(v * v, 0, 1) + 0.1
            self.hsv_array[index:, 0] = h
            self.hsv_array[index:, 1] = 1 - (v - 1) * 2
            self.hsv_array[index:, 2] = v * 2
