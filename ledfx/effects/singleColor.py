import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect


class SingleColorEffect(TemporalEffect, ModulateEffect):
    NAME = "Single Color"
    CATEGORY = "Non-Reactive"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="#FF0000"
            ): validate_color,
        },
    )

    def config_updated(self, config):
        self.color = np.array(parse_color(self._config["color"]), dtype=float)

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        color_array = np.tile(self.color, (self.pixel_count, 1))
        self.pixels = self.modulate(color_array)
