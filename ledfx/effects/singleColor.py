import numpy as np  # noqa: N999
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect


class SingleColorEffect(TemporalEffect, ModulateEffect):
    NAME = "Single Color"
    CATEGORY = "Non-Reactive"

    class Config(TemporalEffect.Config, ModulateEffect.Config):
        color: Color = Field("#FF0000", description="Color of strip")

    config = TypedConfig(Config)

    def config_updated(self, config):
        self.color = np.array(parse_color(self.config.color), dtype=float)

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        color_array = np.tile(self.color, (self.pixel_count, 1))
        self.pixels = self.modulate(color_array)
