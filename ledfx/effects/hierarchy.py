import logging
import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.utils import aggressive_top_end_bias

_LOGGER = logging.getLogger(__name__)


class Hierarchy(AudioReactiveEffect):
    NAME = "Hierarchy"
    CATEGORY = "Simple"
    HIDDEN_KEYS = [
        "background_color",
        "background_brightness",
        "blur",
        "mirror",
        "flip",
    ]
    ADVANCED_KEYS = []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color_lows",
                description="Color of low, bassy sounds",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "color_mids",
                description="Color of midrange sounds",
                default="#00FF00",
            ): validate_color,
            vol.Optional(
                "color_high",
                description="Color of high sounds",
                default="#0000FF",
            ): validate_color,
            vol.Optional(
                "brightness_boost",
                description="Boost the brightness of the effect on a parabolic curve",
                default=0.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "threshold_lows",
                description="If Lows are below this value, Mids are used.",
                default=0.05,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "threshold_mids",
                description="If Mids are below this value, Highs are used",
                default=0.05,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "switch_time",
                description="Time Lows/Mids have to be below threshold before switch",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        }
    )

    def on_activate(self, pixel_count):
        self.filtered_power = 0
        self.last_low = timeit.default_timer()
        self.last_mid = timeit.default_timer()
        self.color = np.array(parse_color("#000000"))

    def config_updated(self, config):
        self.switch_time = self._config["switch_time"]
        self.switch_threshold_lows = self._config["switch_threshold_lows"]
        self.switch_threshold_mids = self._config["switch_threshold_mids"]
        self.color_low = np.array(parse_color(self._config["color_lows"]))
        self.color_mids = np.array(parse_color(self._config["color_mids"]))
        self.color_high = np.array(parse_color(self._config["color_high"]))

    def audio_data_updated(self, data):
        current_time  = timeit.default_timer()
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
        self.pixels[:] = self.color * aggressive_top_end_bias(self.filtered_power , self._config["brightness_boost"])
        