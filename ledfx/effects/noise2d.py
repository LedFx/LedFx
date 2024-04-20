import logging
import random

import numpy as np
import vnoise
import voluptuous as vol
from PIL import Image

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# this effect is inspired by the WLED soap effect found at
# https://github.com/Aircoookie/WLED/blob/f513cae66eecb2c9b4e8198bd0eb52d209ee281f/wled00/FX.cpp#L7472


class Noise2d(Twod, GradientEffect):
    NAME = "Noise"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "gradient_roll",
        "intensity",
        "soap",
    ]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Speed of the effect",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
            vol.Optional(
                "intensity",
                description="intensity of the effect",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "stretch",
                description="Stretch of the effect",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.5)),
            vol.Optional(
                "zoom",
                description="zoom density",
                default=2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=20)),
            vol.Optional(
                "impulse_decay",
                description="Decay filter applied to the impulse for development",
                default=0.06,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "multiplier",
                description="audio injection multiplier, 0 is none",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=4.0)),
            vol.Optional(
                "soap",
                description="Add soap smear to noise",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        self.first_run = True
        self.last_rotate = 0
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.speed = self._config["speed"]
        self.intensity = self._config["intensity"]
        self.stretch = self._config["stretch"]
        self.zoom = self._config["zoom"]
        self.multiplier = self._config["multiplier"]
        self.soap = self._config["soap"]

        self.lows_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99
        )
        self.lows_impulse = 0

        if self.last_rotate != self._config["rotate"]:
            # as rotate could be non symetrical we better reseed everything
            self.first_run = True
            self.last_rotate = self._config["rotate"]

    def do_once(self):
        super().do_once()

        if self.first_run:
            self.noise3d = np.zeros(
                (self.r_height, self.r_width), dtype=np.float64
            )
            self.noise_x = random.random()
            self.noise_y = random.random()
            self.noise_z = random.random()
            self.noise = vnoise.Noise()
            self.first_run = False

        self.scale_x = self.zoom / self.r_width
        self.scale_y = self.zoom / self.r_height

        self.smoothness = min(250, self.intensity)
        # self.seed_image = Image.new("RGB", (self.r_width, self.r_height))
        # self.seed_matrix = True

    def audio_data_updated(self, data):
        self.lows_impulse = self.lows_impulse_filter.update(
            data.lows_power(filtered=False) * self.multiplier
        )

    def draw(self):

        if self.test:
            self.draw_test(self.m_draw)

        # time invariant movement throuh the noise space
        self.mov = 0.5 * self.speed * self.passed

        self.noise_x += self.mov
        # handle y only if we are a matrix
        self.noise_z += self.mov


        if self.r_height > 1:
            self.noise_y += self.mov
            bass_x = self.scale_x * self.lows_impulse
            bass_y = self.scale_y * self.lows_impulse
        else:
            bass_x = 0
            bass_y = self.scale_y * self.lows_impulse * (1 / self.r_width)

        scale_x = self.scale_x + bass_x
        scale_y = self.scale_y + bass_y

        noise_x = self.noise_x - (scale_x * self.r_height / 2)
        noise_y = self.noise_y - (scale_y * self.r_width / 2)

        # generate arrays of the X adn Y axis of our plane, with a singular Z
        # this should allow libs to use any internal acceleration for unrolling across all points
        x_array = np.linspace(
            noise_x, noise_x + scale_x * self.r_height, self.r_height
        )
        y_array = np.linspace(
            noise_y, noise_y + scale_y * self.r_width, self.r_width
        )
        z_array = np.array([self.noise_z])

        ###################################################################################
        # This is where the magic happens, calling the lib of choice to get the noise plane
        ###################################################################################
        # opensimplex at 128x128 on dev machine is 200 ms per frame - Unusable
        #        self.noise_3d = opensimplex.noise3array(x_array, y_array, z_array)
        # vnoise at 128x128 on dev machine is 2.5 ms per frame - Current best candidate
        self.noise_3d = self.noise.noise3(
            x_array, y_array, z_array, grid_mode=True
        )

        # slice out the unwanted dimension
        self.noise_sliced = self.noise_3d[..., 0]

        # apply the stetch param to expand the range of the color space, as noise is likely not full -1 to 1
        # TODO: look at what color mapping does with out of range values, do we need to cap here
        self.noise_stretched = self.noise_sliced * self.stretch
        # normalise the noise from -1,1 range to 0,1
        self.noise_normalised = (self.noise_stretched + 1) / 2

        # map from 0,1 space into the gradient color space via our nicely vecotrised function
        self.color_array = self.get_gradient_color_vectorized2d(
            self.noise_normalised
        ).astype(np.uint8)

        # transform the numpy array into a PIL image in one easy step
        self.matrix = Image.fromarray(self.color_array, "RGB")
