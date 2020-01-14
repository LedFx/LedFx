from ledfx.effects.temporal import TemporalEffect
from ledfx.effects.gradient import GradientEffect
#from ledfx.color import COLORS, GRADIENTS
#from ledfx.effects import Effect
import voluptuous as vol
import numpy as np
import logging

class FadeEffect(TemporalEffect, GradientEffect):
    """
    Fades through the colours of a gradient
    """

    NAME = "Fade"

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('gradient_method', description='Function used to generate gradient', default = 'bezier'): vol.In(["cubic_ease", "bezier"]),
    })

    def config_updated(self, config):
        self.location = 1
        self.forward = True

    def effect_loop(self):
        if self.location in (0, 500):
            self.forward = not self.forward
        if self.forward:
            self.location += 1
        else:
            self.location -= 1
        color = self.get_gradient_color(self.location/500.0)
        self.pixels = np.tile(color, (self.pixel_count, 1))