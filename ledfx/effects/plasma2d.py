import logging
import timeit

import numpy as np
import PIL.Image as Image
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Plasma2d(Twod, GradientEffect):
    NAME = "Plasma2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["background_color", "gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "v density",
                description="Lets pretend its vertical density",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "twist",
                description="Like a slice of lemon",
                default=0.07,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "radius",
                description="If you squint its the distance from the center",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
            vol.Optional(
                "density",
                description="kinda how small the plasma is, but who realy knows",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.001, max=2.0)),
            vol.Optional(
                "lower",
                description="lower band of density",
                default=0.01,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        self.time = timeit.default_timer()
        self.density = self._config["density"]
        self.lower = self._config["lower"]
        self.power_func = self._power_funcs[self._config["frequency_range"]]
        self.v_density = self._config["v density"]
        self.twist = self._config["twist"]
        self.radius = self.config["radius"]
        super().config_updated(config)

    def do_once(self):
        super().do_once()

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = getattr(data, self.power_func)()

    def generate_plasma(self, width, height, time, power):
        # Calculate the scale
        scale = self.lower + (power * self.density)

        # Create coordinate grids with a limited number of steps
        y, x = np.ogrid[
            0 : min(height, height * scale) : complex(height),
            0 : min(width, width * scale) : complex(width),
        ]

        # Calculate the plasma values
        plasma = (
            np.sin(x * 0.1 + time) * np.cos(y * 0.1 - time)
            + np.sin((x * self.v_density + y * self.twist + time) * 2.5)
            + np.sin(np.sqrt(x**2 + y**2) * self.radius - time)
        ) * 128 + 128

        # Normalize the plasma values to the range [0, 1]
        plasma_normalized = (plasma - np.min(plasma)) / (
            np.max(plasma) - np.min(plasma)
        )
        return plasma_normalized

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        current_time = timeit.default_timer() - self.start_time

        plasma_array = self.generate_plasma(
            self.r_width, self.r_height, current_time, self.bar
        )

        color_mapped_plasma = self.get_gradient_color_vectorized(
            plasma_array
        ).astype(np.uint8)

        self.matrix = Image.fromarray(color_mapped_plasma, "RGB")
