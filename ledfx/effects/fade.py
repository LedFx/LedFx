from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.temporal import TemporalEffect


class FadeEffect(TemporalEffect, GradientEffect):
    """
    Fades through the colors of a gradient
    """

    NAME = "Fade"
    CATEGORY = "Non-Reactive"
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]

    class Config(TemporalEffect.Config, GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5, description="Rate of change of color", ge=0.1, le=10
        )

    config = TypedConfig(Config)

    def config_updated(self, config):
        self.idx = 0
        self.forward = True

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        self.idx += 0.0015
        if self.idx > 1:
            self.idx = 1
            self.forward = not self.forward
        self.idx = self.idx % 1

        if self.forward:
            i = self.idx
        else:
            i = 1 - self.idx

        color = self.get_gradient_color(i)
        self.pixels = np.tile(color, (self.pixel_count, 1))
