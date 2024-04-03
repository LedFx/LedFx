import logging
import noise
import vnoise
import timeit
import opensimplex
import random
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod
from PIL import Image
import numpy as np

_LOGGER = logging.getLogger(__name__)

# this effect is inspired by the WLED soap effect found at
# https://github.com/Aircoookie/WLED/blob/f513cae66eecb2c9b4e8198bd0eb52d209ee281f/wled00/FX.cpp#L7472


def random16():
    return random.randint(0, 65535)

def scale_uint16_to_01(value):
    return value / 65535.0

def scale_uint8_to_01(value):
    return value / 255.0

def scale8(i, scale):
    return i * ( scale / 256 )

class Soap2d(Twod, GradientEffect):
    NAME = "Soap"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "a_switch",
                description="Does a boolean thing",
                default=False,
            ): bool,
            vol.Optional(
                "speed",
                description="Speed of the effect",
                default = 128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "intensity",
                description="intensity of the effect",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "stretch",
                description="Stretch of the effect",
                default = 1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.5)),
            vol.Optional(
                "zoom",
                description="zoom density",
                default=5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=20)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["a_switch"]
        self.speed = self._config["speed"]
        self.intensity = self._config["intensity"]
        self.stretch = self._config["stretch"]
        self.zoom = self._config["zoom"]

    # prior to rework at 32 x 32 with int / float mix and brute force 80 ms / frame
    def do_once(self):
        super().do_once()
        cols = self.r_width
        rows = self.r_height
        self.noise3d = np.zeros((rows, cols), dtype=np.float64)
        self.noise_x = random.random()
        self.noise_y = random.random()
        self.noise_z = random.random()
        self.scale_x = self.zoom/cols
        self.scale_y = self.zoom/rows
        self.mov = min(cols, rows)*(self.speed + 2)/2/65535
        self.smoothness = min(250, self.intensity)
        self.seed_image = Image.new("RGB", (self.r_width, self.r_height))
        self.seed_matrix = True
        self.noise = vnoise.Noise()

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def draw(self):

        if self.test:
            self.draw_test(self.m_draw)

        # move the plane through the noise space
        # this is a candidate for audio reaction
        self.noise_x += self.mov
        self.noise_y += self.mov
        self.noise_z += self.mov

        # TODO: this is currently done to make following code more readable and will be removed later
        cols = self.r_width
        rows = self.r_height

        # if we are pixel stuffing into a seed image, setup here
        # pixels = self.seed_image.load()

        log = False

        # generate arrays of the X adn Y axis of our plane, with a singular Z
        # this should allow libs to use any internal acceleration for unrolling across all points

        start = timeit.default_timer()
        x_array = np.linspace(self.noise_x, self.noise_x + self.scale_x * cols, cols)
        y_array = np.linspace(self.noise_y, self.noise_y + self.scale_y * rows, rows)
        z_array = np.array([self.noise_z])
        next1 = timeit.default_timer()
        if log:
            _LOGGER.info(f"array generation time: {next1 - start}")

        # This is where the magic happens, calling the lib of choice to get the noise plane
#        self.noise_3d = opensimplex.noise3array(x_array, y_array, z_array)
        self.noise_3d = self.noise.noise3(x_array, y_array, z_array)
        next2 = timeit.default_timer()
        if log:
            _LOGGER.info(f"simple noise time: {next2 - next1}")

        # if the lib happens to return in a 3 dimensionsal, even though Z is depth of 1, then squeeze it down
        self.noise_squeezed = np.squeeze(self.noise_3d)
        # apply the stetch param to expand the range of the color space, as noise is likely not full -1 to 1
        # TODO: look at what color mapping does with out of range values, do we need to cap here
        self.noise_stretched = self.noise_squeezed * self.stretch
        # normalise the noise from -1,1 range to 0,1
        self.noise_normalised = (self.noise_stretched + 1) / 2
        next3 = timeit.default_timer()
        if log:
            _LOGGER.info(f"simple squeeze time: {next3 - next2}")

        # _LOGGER.info(f"x_array: {x_array}")
        # _LOGGER.info(f"y_array: {y_array}")
        # _LOGGER.info(f"z_array: {z_array}")
        # _LOGGER.info(f"simple_noise3d: {self.simple_n3d}")
        # _LOGGER.info(f"shape: {self.simple_n3d.shape}")
        # _LOGGER.info(f"min {np.min(self.simple_n3d)}, max {np.max(self.simple_n3d)}")

        # map from 0,1 space into the gradient color space via our nicely vecotrised function
        self.color_array = self.get_gradient_color_vectorized2d(self.noise_normalised).astype(np.uint8)
        next4 = timeit.default_timer()
        if log:
            _LOGGER.info(f"color array time: {next4 - next3}")

        # _LOGGER.info(f"color_array: {self.color_array}")

        # transform the numpy array into a PIL image in one easy step
        self.matrix = Image.fromarray(self.color_array, "RGB")
        next5 = timeit.default_timer()
        if log:
            _LOGGER.info(f"image from array time: {next5 - next4}")

