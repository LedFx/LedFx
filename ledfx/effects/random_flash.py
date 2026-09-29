import random
from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.temporal import TemporalEffect


class RandomFlashEffect(TemporalEffect):
    """
    Randomly activates sections with a flash/lightning-like effect
    """

    NAME = "Random Flash"
    CATEGORY = "Non-Reactive"
    HIDDEN_KEYS: ClassVar[list[str]] = ["flip", "mirror", "speed"]
    # based on fixed speed of 5.0
    RUNS_PER_SEC = 50.0

    class Config(TemporalEffect.Config):
        hit_color: Color = Field("#FFFFFF", description="Hit color")
        hit_duration: CoercedFloat = Field(
            0.5, description="Hit duration", ge=0.1, le=5.0
        )
        hit_probability_per_sec: CoercedFloat = Field(
            0.1, description="Probability of hit per second", ge=0.01, le=1.0
        )
        hit_relative_size: CoercedInt = Field(
            10, description="Hit size relative to LED strip", ge=1, le=100
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        # overriding speed (from TemporalEffect) to achieve smooth fade
        super().__init__(ledfx, config.with_values(speed=5.0))
        self.last_time = self.now
        self.last_hit_pixels = None

    def config_updated(self, config):
        self.hit_color = np.array(parse_color(self.config.hit_color), dtype=float)
        self.hit_relative_size = self.config.hit_relative_size
        self.hit_duration = self.config.hit_duration
        self.probability_per_sec = self.__balance_hit_probability_based_on_speed()

    def on_activate(self, pixel_count):
        self.last_time = self.now

    def effect_loop(self):
        hit_absolute_size = int(self.pixel_count * self.hit_relative_size / 100)

        # handle time variant
        time_passed = self.now - self.last_time

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
                self.pixels[random_pos : random_pos + hit_absolute_size] = (
                    self.hit_color
                )

                self.last_hit_pixels = self.pixels
                self.last_time = self.now

    def __balance_hit_probability_based_on_speed(self) -> float:
        # this is the probability per effect run
        return 1 - (1 - self.config.hit_probability_per_sec) ** (1 / self.RUNS_PER_SEC)
