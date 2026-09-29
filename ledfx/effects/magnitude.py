from typing import Annotated

from pydantic import Field

from ledfx.configuration.fields import OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class MagnitudeAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Magnitude"
    CATEGORY = "Classic"

    class Config(GradientEffect.Config):
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for the beat detection"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.magnitude = 0

    def config_updated(self, config):
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]

    def audio_data_updated(self, data):
        self.magnitude = getattr(data, self.power_func)()

    def render(self):
        self.pixels = self.apply_gradient(self.magnitude)
