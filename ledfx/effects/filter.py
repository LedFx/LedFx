import logging
import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect

_LOGGER = logging.getLogger(__name__)


class Filter(AudioReactiveEffect, GradientEffect):
    NAME = "Filter"
    CATEGORY = "Simple"
    HIDDEN_KEYS = [
        "background_color",
        "background_brightness",
        "blur",
        "mirror",
        "flip",
        # we can't use gradient_roll as it is not time invariant
        "gradient_roll",
    ]
    ADVANCED_KEYS = []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color",
                description="Simple color selector",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "frequency_range",
                description="Frequency range for derived brightness",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "use_gradient",
                description="Use gradient instead of color",
                default=False,
            ): bool,
            vol.Optional(
                "roll_speed",
                description="0= no gradient roll, range 60 secs to 1 sec",
                default=0.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        }
    )

    def on_activate(self, pixel_count):
        self.filtered_power = 0
        self.current_time = timeit.default_timer()

    def config_updated(self, config):
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.color = np.array(parse_color(self._config["color"]))
        self.use_gradient = self._config["use_gradient"]
        self.roll_speed = self._config["roll_speed"]
        if self.roll_speed > 0:
            # ranging time from 20 to 1 seconds
            self.roll_time = (1 - self.roll_speed) * 59 + 1

    def audio_data_updated(self, data):
        self.filtered_power = getattr(data, self.power_func)()

    def render(self):

        if self.use_gradient:

            if self.roll_speed > 0:
                # some mod magic to get a value between 0 and 1 according to time passed
                gradient_index = (
                    timeit.default_timer() % self.roll_time
                ) / self.roll_time
            else:
                gradient_index = 0

            color = self.get_gradient_color(gradient_index)
        else:
            color = self.color

        # just fill the pixels to the selected color multiplied by the brightness
        # we don't care if it is a single pixel or a massive matrix!
        self.pixels[:] = color * self.filtered_power
