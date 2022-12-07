import numpy as np
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.temporal import TemporalEffect


class FadeEffect(TemporalEffect, GradientEffect):
    """
    Fades through the colors of a gradient
    """

    NAME = "Fade"
    CATEGORY = "Non-Reactive"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                default=0.5,
                description="Rate of change of color",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
        }
    )

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
