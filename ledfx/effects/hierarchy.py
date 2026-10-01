import logging
import timeit
from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.utils import aggressive_top_end_bias

_LOGGER = logging.getLogger(__name__)


class Hierarchy(AudioReactiveEffect):
    NAME = "Hierarchy"
    CATEGORY = "Simple"
    HIDDEN_KEYS: ClassVar[list[str]] = [
        "background_color",
        "background_brightness",
        "blur",
        "mirror",
        "flip",
    ]

    class Config(AudioReactiveEffect.Config):
        color_lows: Color = Field("#FF0000", description="Color of low, bassy sounds")
        color_mids: Color = Field("#00FF00", description="Color of midrange sounds")
        color_high: Color = Field("#0000FF", description="Color of high sounds")
        brightness_boost: CoercedFloat = Field(
            0.0,
            description="Boost the brightness of the effect on a parabolic curve",
            ge=0.0,
            le=1.0,
        )
        threshold_lows: CoercedFloat = Field(
            0.05,
            description="If Lows are below this value, Mids are used.",
            ge=0.0,
            le=1.0,
        )
        threshold_mids: CoercedFloat = Field(
            0.05,
            description="If Mids are below this value, Highs are used",
            ge=0.0,
            le=1.0,
        )
        switch_time: CoercedFloat = Field(
            0.1,
            description="Time Lows/Mids have to be below threshold before switch",
            ge=0.0,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.filtered_power = 0
        self.last_low = self.now
        self.last_mid = self.now
        self.color = np.array(parse_color("#000000"))

    def config_updated(self, config):
        self.switch_time = self.config.switch_time
        self.switch_threshold_lows = self.config.threshold_lows
        self.switch_threshold_mids = self.config.threshold_mids
        self.brightness_boost = self.config.brightness_boost
        self.color_low = np.array(parse_color(self.config.color_lows))
        self.color_mids = np.array(parse_color(self.config.color_mids))
        self.color_high = np.array(parse_color(self.config.color_high))

    def audio_data_updated(self, data):
        # as this is in the audio_data_updated() not safe to use self.now
        current_time = timeit.default_timer()
        # use Lows (beat+bass)
        self.filtered_power = self.audio.lows_power()
        if self.filtered_power > self.switch_threshold_lows:
            self.color = self.color_low
            self.last_low = current_time
        # use Mids
        elif current_time - self.last_low > self.switch_time:
            self.filtered_power = self.audio.mids_power()
            if self.filtered_power > self.switch_threshold_mids:
                self.color = self.color_mids
                self.last_mid = current_time
            # use High
            elif current_time - self.last_mid > self.switch_time:
                self.filtered_power = self.audio.high_power()
                self.color = self.color_high

    def render(self):
        # Apply the color to all pixels by multiplying the color with the calculated brightness
        self.pixels[:] = self.color * aggressive_top_end_bias(
            self.filtered_power, self.brightness_boost
        )
