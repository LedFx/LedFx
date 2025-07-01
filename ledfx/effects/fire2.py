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
            vol.Optional("speed", default=0.04): vol.All(
                vol.Coerce(float), vol.Range(min=0.00001, max=0.5)
            ),
            vol.Optional("color_shift", default=0.15): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=1)
            ),
            vol.Optional("intensity", default=8): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=30)
            ),
            vol.Optional("fade_chance", default=0.5): vol.All(
                vol.Coerce(float), vol.Range(min=0.05, max=1.0)
            ),
        }
    )

    def on_activate(self, pixel_count):
        self.spark_pixels = np.zeros(self.pixel_count, dtype=np.float32)
        self.h = np.zeros(self.pixel_count, dtype=np.float32)
        self.s = np.zeros(self.pixel_count, dtype=np.float32)
        self.v = np.zeros(self.pixel_count, dtype=np.float32)
        self.delta_last = time.time()

    def config_updated(self, config):
        self.speed = self._config["speed"]
        self.cooling = 0.95
        self.accel = 0.03
        self.fade_chance = self._config["fade_chance"] / 10
        self._lows_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.99
        )

        self.spark_count = self._config["intensity"]
        self.color_shift = self._config["color_shift"]
        self.sparks = np.zeros(self.spark_count, dtype=np.float32)
        self.sparkX = np.random.uniform(0, 5, size=self.spark_count).astype(
            np.float32
        )

    def audio_data_updated(self, data):
        _lows_power = self._lows_filter.update(
            np.mean(data.lows_power(filtered=False))
        )
        self.cooling = 0.75 + _lows_power * 0.25
        self.accel = 0.02 + _lows_power * 0.1
        self.speed = self._config["speed"] + _lows_power * 0.01

    def render_hsv(self):
        current_time = time.time()
        delta_ms = (current_time - self.delta_last) * 1000
        self.delta_last = current_time
        delta_scaled = delta_ms * self.speed

        pixels = self.spark_pixels
        np.multiply(pixels, self.cooling, out=pixels)

        # Vectorized heat diffusion
        if self.pixel_count > 5:
            pixels[5:] = (
                pixels[4:-1]
                + pixels[3:-2]
                + pixels[2:-3] * 2
                + pixels[1:-4] * 3
            ) / 7

        sparks = self.sparks
        sparkX = self.sparkX
        pixel_limit = self.pixel_count

        # Reset dead sparks
        dead_sparks = sparks <= 0
        sparks[dead_sparks] = np.random.uniform(
            0.5, 1.0, size=np.count_nonzero(dead_sparks)
        )
        sparkX[dead_sparks] = np.random.uniform(
            0, 5, size=np.count_nonzero(dead_sparks)
        )

        # Advance sparks
        step = sparks**2 * delta_scaled * (pixel_limit / 100)
        sparkX += step

        # Fade chance from config simulates lifetime flicker
        random_fade_mask = np.random.rand(self.spark_count) < self.fade_chance
        reset_mask = (sparkX >= pixel_limit) | random_fade_mask
        sparks[reset_mask] = 0
        sparkX[reset_mask] = 0

        # Heat up pixels where sparks pass
        for i in range(self.spark_count):
            j_start = int(sparkX[i] - step[i])
            j_end = int(sparkX[i])
            if j_end > j_start:
                j_range = np.clip(
                    np.arange(j_start, j_end), 0, pixel_limit - 1
                )
                pixels[j_range] += np.clip(1 - sparks[i] * 0.4, 0, 1) * 0.5

        # Map to HSV
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
