import logging
from typing import Annotated, ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.utils import aggressive_top_end_bias

_LOGGER = logging.getLogger(__name__)


class Filter(AudioReactiveEffect, GradientEffect):
    NAME = "Filter"
    CATEGORY = "Simple"
    HIDDEN_KEYS: ClassVar[list[str]] = [
        "background_color",
        "background_brightness",
        "blur",
        "mirror",
        "flip",
        # we can't use gradient_roll as it is not time invariant
        "gradient_roll",
    ]

    class Config(GradientEffect.Config):
        color: Color = Field("#FF0000", description="Simple color selector")
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for derived brightness"
        )
        use_gradient: bool = Field(False, description="Use gradient instead of color")
        roll_speed: CoercedFloat = Field(
            0.0,
            description="0= no gradient roll, range 60 secs to 1 sec",
            ge=0.0,
            le=1.0,
        )
        boost: CoercedFloat = Field(
            0.0,
            description="Boost the brightness of the effect on a parabolic curve",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.filtered_power = 0

    def config_updated(self, config):
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]
        self.color = np.array(parse_color(self.config.color))
        self.use_gradient = self.config.use_gradient
        self.roll_speed = self.config.roll_speed
        if self.roll_speed > 0:
            # ranging time from 20 to 1 seconds
            self.roll_time = (1 - self.roll_speed) * 59 + 1
        self.boost = self.config.boost

    def audio_data_updated(self, data):
        self.filtered_power = getattr(data, self.power_func)()

    def render(self):

        if self.use_gradient:
            if self.roll_speed > 0:
                # some mod magic to get a value between 0 and 1 according to time passed
                gradient_index = (self.now % self.roll_time) / self.roll_time
            else:
                gradient_index = 0
            color = self.get_gradient_color(gradient_index)
        else:
            color = self.color

        boosted = aggressive_top_end_bias(self.filtered_power, self.boost)

        # just fill the pixels to the selected color multiplied by the brightness
        # we don't care if it is a single pixel or a massive matrix!
        self.pixels[:] = color * boosted
