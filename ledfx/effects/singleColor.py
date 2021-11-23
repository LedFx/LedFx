import numpy as np
import voluptuous as vol

from ledfx.color import validate_color, parse_color
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect


class SingleColorEffect(TemporalEffect, ModulateEffect):

    NAME = "Single Color"
    CATEGORY = "BASIC"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="#FF0000"
            ): validate_color,
            vol.Optional(
                "blade_color",
                description="NEW Color",
                default="#FF0000",
            ): str
        },
    )

    def config_updated(self, config):
        self.color = np.array(parse_color(self._config["color"]), dtype=float)

    def effect_loop(self):
        color_array = np.tile(self.color, (self.pixel_count, 1))
        self.pixels = self.modulate(color_array)
