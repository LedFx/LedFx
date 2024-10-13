import random
import time

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.temporal import TemporalEffect


class RandomEffect(TemporalEffect):
    """
    Randomly activates sections
    """

    NAME = "Random"
    CATEGORY = "Non-Reactive"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "hit_color", description="Hit color", default="#FFFFFF"
            ): validate_color,
            vol.Optional(
                "hit_duration",
                description="Hit duration",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
            vol.Optional(
                "hit_probability_per_sec",
                description="Probability of hit per second",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
            vol.Optional(
                "hit_relative_size",
                description="Hit size relative to LED strip",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.seconds_since_last_hit = 0

    def config_updated(self, config):
        self.hit_color = np.array(
            parse_color(self._config["hit_color"]), dtype=float
        )
        self.hit_relative_size = self._config["hit_relative_size"]
        self.hit_duration = self._config["hit_duration"]
        self.speed = self._config["speed"]
        self.probability_per_sec = (
            self.__balance_hit_probability_based_on_speed()
        )

    def on_activate(self, pixel_count):
        self.seconds_since_last_hit = 0

    def effect_loop(self):
        hit_absolute_size = int(self.pixel_count * self.hit_relative_size)
        self.__update_duration_since_last_hit()

        hit_is_still_active = self.seconds_since_last_hit < self.hit_duration
        if not hit_is_still_active:
            # Create a base frame of all-off (black) pixels
            frame = np.zeros((self.pixel_count, 3), dtype=np.float64)

            is_hit = np.random.random() < self.probability_per_sec
            if is_hit:
                # assign pixel hit at random position
                random_pos = random.randrange(
                    self.pixel_count - hit_absolute_size
                )
                # frame slice based of random_pos will be hited
                frame[random_pos : random_pos + hit_absolute_size, :] = (
                    np.tile(self.hit_color, (hit_absolute_size, 1))
                )
                # frame = np.tile(self.hit_color, (self.pixel_count, 1))
                self.seconds_since_last_hit = 0
            self.pixels = frame

    def __update_duration_since_last_hit(self):
        # NOTE: speed 0.1 is 1 update per sec
        self.seconds_since_last_hit += 1 / (10 * self.speed)

    def __balance_hit_probability_based_on_speed(self) -> float:
        runs_per_sec = self.speed * 10
        # this is the probability per effect run
        return 1 - (1 - self._config["hit_probability_per_sec"]) ** (
            1 / runs_per_sec
        )
