from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects import fill_rainbow
from ledfx.effects.temporal import TemporalEffect


class RainbowEffect(TemporalEffect):
    NAME = "Rainbow"
    CATEGORY = "Non-Reactive"

    class Config(TemporalEffect.Config):
        speed: CoercedFloat = Field(
            1.0, description="Speed of the effect", ge=0.1, le=20
        )
        frequency: CoercedFloat = Field(
            1.0, description="Frequency of the effect curve", ge=0.1, le=64
        )

    config = TypedConfig(Config)

    _hue = 0.1

    def on_activate(self, pixel_count):
        pass

    def effect_loop(self):
        hue_delta = self.config.frequency / self.pixel_count
        self.pixels = fill_rainbow(self.pixels, self._hue, hue_delta)

        self._hue = self._hue + 0.01
