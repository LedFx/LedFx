import logging
from typing import Annotated

import numpy as np
from PIL import Image
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Plasma2d(Twod, GradientEffect):
    NAME = "Plasma2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "background_brightness",
        "background_mode",
        "gradient_roll",
    ]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    class Config(Twod.Config, GradientEffect.Config):
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for the beat detection"
        )
        density_vertical: CoercedFloat = Field(
            0.1, description="Lets pretend its vertical density", ge=0.01, le=0.3
        )
        twist: CoercedFloat = Field(
            0.07, description="Like a slice of lemon", ge=0.01, le=0.3
        )
        radius: CoercedFloat = Field(
            0.2,
            description="If you squint its the distance from the center",
            ge=0.01,
            le=1.0,
        )
        density: CoercedFloat = Field(
            0.5,
            description="kinda how small the plasma is, but who realy knows",
            ge=0.001,
            le=2.0,
        )
        lower: CoercedFloat = Field(
            0.01, description="lower band of density", ge=0.01, le=1.0
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        self.density = self.config.density
        self.lower = self.config.lower
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]
        self.density_vertical = self.config.density_vertical
        self.twist = self.config.twist
        self.radius = self.config.radius
        super().config_updated(config)

    def do_once(self):
        super().do_once()

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = getattr(data, self.power_func)()

    def generate_plasma(self, width, height, time, power):
        # Protect against invalid dimensions
        if width <= 0 or height <= 0:
            return np.zeros((max(1, height), max(1, width)))

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
            + np.sin((x * self.density_vertical + y * self.twist + time) * 2.5)
            + np.sin(np.sqrt(x**2 + y**2) * self.radius - time)
        ) * 128 + 128

        # Normalize the plasma values to the range [0, 1]
        plasma_range = np.max(plasma) - np.min(plasma)
        if plasma_range > 0:
            plasma_normalized = (plasma - np.min(plasma)) / plasma_range
        else:
            plasma_normalized = np.zeros_like(plasma)
        return plasma_normalized

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        plasma_array = self.generate_plasma(
            self.r_width, self.r_height, self.now, self.bar
        )

        color_mapped_plasma = self.get_gradient_color_vectorized2d(plasma_array).astype(
            np.uint8
        )

        self.matrix = Image.fromarray(color_mapped_plasma, "RGB")
