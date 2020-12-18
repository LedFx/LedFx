import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect


class SingleColorEffect(TemporalEffect, ModulateEffect):

    NAME = "Single Color"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="red"
            ): vol.In(list(COLORS.keys())),
        }
    )

    def config_updated(self, config):
        self.color = np.array(COLORS[self._config["color"]], dtype=float)

    def effect_loop(self):
        color_array = np.tile(self.color, (self.pixel_count, 1))
        self.pixels = self.modulate(color_array)
