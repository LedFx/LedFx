import logging
from collections import namedtuple
from typing import Annotated

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect

RGB = namedtuple("RGB", "red, green, blue")
hsv = namedtuple("hsv", "hue, saturation, value")

_LOGGER = logging.getLogger(__name__)


class BladePowerPlus(AudioReactiveEffect, HSVEffect):
    NAME = "Blade Power+"
    CATEGORY = "Classic"

    class Config(HSVEffect.Config):
        mirror: bool = Field(False, description="Mirror the effect")
        blur: CoercedFloat = Field(
            2, description="Amount to blur the effect", ge=0.0, le=10
        )
        decay: CoercedFloat = Field(0.7, description="Rate of color decay", ge=0, le=1)
        multiplier: CoercedFloat = Field(
            0.5, description="Make the reactive bar bigger/smaller", ge=0.0, le=1.0
        )
        background_color: Color = Field("#000000", description="Color of Background")
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for the beat detection"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.bar = 0

    def config_updated(self, config):
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = getattr(data, self.power_func)() * self.config.multiplier * 2

    def render_hsv(self):
        self.hsv_array[:, 0] = np.linspace(0, 1, self.pixel_count)
        self.hsv_array[:, 1] = 1
        # Must be zeroed every cycle to clear the previous frame
        bar_idx = int(self.bar * self.pixel_count)
        self.hsv_array[:, 2] *= self.config.decay / 2 + 0.45
        self.hsv_array[:bar_idx, 2] = self.config.brightness
