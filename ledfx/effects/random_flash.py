import random
import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.temporal import TemporalEffect


class RandomFlashEffect(TemporalEffect):
    """
    Randomly activates sections with a flash/lightning-like effect
    """

    NAME = "Random Flash"
    CATEGORY = "Non-Reactive"
    HIDDEN_KEYS = ["flip", "mirror", "speed"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "hit_color", description="Hit color", default="#FFFFFF"
            ): validate_color,
            vol.Optional(
                "hit_duration",
                description="Hit duration",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
            vol.Optional(
                "hit_probability_per_sec",
                description="Probability of hit per second",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
            vol.Optional(
                "hit_relative_size",
                description="Hit size relative to LED strip",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        }
    )

    def __init__(self, ledfx, config):
        # overriding speed (from TemporalEffect) to achieve smooth fade
        config["speed"] = 5.0
        super().__init__(ledfx, config)
        self.last_time = timeit.default_timer()
        self.last_hit_pixels = None

    def config_updated(self, config):
        self.hit_color = np.array(
            parse_color(self._config["hit_color"]), dtype=float
        )
        self.hit_relative_size = self._config["hit_relative_size"]
        self.hit_duration = self._config["hit_duration"]
        self.probability_per_sec = self.__balance_hit_probability_based_on_speed()


    def on_activate(self, pixel_count):
        self.last_time = timeit.default_timer()

    def effect_loop(self):
        hit_absolute_size = int(self.pixel_count * self.hit_relative_size / 100)

        # handle time variant
        now = timeit.default_timer()
        time_passed = now - self.last_time

        hit_is_still_active = time_passed < self.hit_duration
        if hit_is_still_active and self.last_hit_pixels is not None:
            # fade
            self.pixels = self.last_hit_pixels * (1 - time_passed / self.hit_duration)

        else:
            self.pixels = np.zeros((self.pixel_count, 3), dtype=np.float64)

            is_hit = np.random.random() < self.probability_per_sec
            if is_hit:
                # assign pixel hit at random position
                random_pos = random.randrange(self.pixel_count - hit_absolute_size + 1)
                # frame slice based of random_pos will be hit
                self.pixels[random_pos : random_pos + hit_absolute_size] = np.tile(self.hit_color, (hit_absolute_size, 1))

                self.last_hit_pixels = self.pixels
                self.last_time = timeit.default_timer()

    def __balance_hit_probability_based_on_speed(self) -> float:
        runs_per_sec = self._config["speed"] * 10
        # this is the probability per effect run
        return 1 - (1 - self._config["hit_probability_per_sec"]) ** (1 / runs_per_sec)
