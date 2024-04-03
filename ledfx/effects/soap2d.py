import logging
import noise
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

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        # all rotation abstraction is done for you
        # you can use image dimensions now
        # self.matrix.height
        # self.matrix.width

        # look in this function for basic lines etc, use pillow primitives
        # for regular shapes
        if self.test:
            self.draw_test(self.m_draw)

        self.noise_x += self.mov
        self.noise_y += self.mov
        self.noise_z += self.mov

        cols = self.r_width
        rows = self.r_height

        # pixels = self.seed_image.load()
        log = False

        # to move to simple noise we need to generate X, Y and Z arrays
        # we will then use simplenoise to generate the 3d noise
        start = timeit.default_timer()
        x_array = np.linspace(self.noise_x, self.noise_x + self.scale_x * cols, cols)
        y_array = np.linspace(self.noise_y, self.noise_y + self.scale_y * rows, rows)
        z_array = np.array([self.noise_z])
        next1 = timeit.default_timer()
        _LOGGER.info(f"array generation time: {next1 - start}")
        self.simple_3d = opensimplex.noise3array(x_array, y_array, z_array)
        next2 = timeit.default_timer()
        _LOGGER.info(f"simple noise time: {next2 - next1}")
        self.simple_squeezed_3d = np.squeeze(self.simple_3d)
        self.simple_stretch_3d = self.simple_squeezed_3d * self.stretch
        self.simple_normalised_3d = ( self.simple_stretch_3d + 1 ) / 2
        next3 = timeit.default_timer()
        _LOGGER.info(f"simple squeeze time: {next3 - next2}")

        # _LOGGER.info(f"x_array: {x_array}")
        # _LOGGER.info(f"y_array: {y_array}")
        # _LOGGER.info(f"z_array: {z_array}")
        # _LOGGER.info(f"simple_noise3d: {self.simple_n3d}")
        # _LOGGER.info(f"shape: {self.simple_n3d.shape}")
        # _LOGGER.info(f"min {np.min(self.simple_n3d)}, max {np.max(self.simple_n3d)}")

        self.color_array = self.get_gradient_color_vectorized2d(self.simple_normalised_3d).astype(np.uint8)
        next4 = timeit.default_timer()
        _LOGGER.info(f"color array time: {next4 - next3}")

        # _LOGGER.info(f"color_array: {self.color_array}")

        self.matrix = Image.fromarray(self.color_array, "RGB")
        next5 = timeit.default_timer()
        _LOGGER.info(f"image from array time: {next5 - next4}")


        # for i in range(cols):
        #     ioffset = self.scale_x * i
        #     for j in range(rows):
        #         joffset = self.scale_y * j
        #         if log:
        #             _LOGGER.info(f"i: {i}, j: {j}")
        #             _LOGGER.info(f"ioffset: {ioffset}, joffset: {joffset}")
        #             _LOGGER.info(f"noise32_x: {self.noise_x}, noise32_y: {self.noise_y}, noise32_z: {self.noise_z}")
        #
        #         noise_val = noise.pnoise3(self.noise_x + ioffset,
        #                                   self.noise_y + joffset,
        #                                   self.noise_z)
        #         # scale -1 to 0 into 0 to 255
        #         data = self.stretch * noise_val
        #         data = min(1.0, max(-1.0, data))
        #         data = (data + 1) / 2
        #
        #         self.noise3d[i,j] = data
        #         # WE ARE CURRENLY IGNORING SMOOTHNESS DURING CURRENT DEVELOPMENT
        #
        #         # scale8(self.noise3d[i,j], self.smoothness) + scale8(data, 255 - self.smoothness)
        #         if log:
        #             _LOGGER.info(f"noise_val: {noise_val}, data: {data} noise3d: {self.noise3d[i,j]}")
        #         if True:
        #             index = self.noise3d[i,j]
        #             if log:
        #                 _LOGGER.info(f"index: {index}")
        #             color = self.get_gradient_color(index).astype(np.uint8)
        #             if log:
        #                 _LOGGER.info(f"color: {color}")
        #             pixels[i, j] = (color[0], color[1], color[2])
        #     #_LOGGER.info(f"min {np.min(self.noise3d)}, max {np.max(self.noise3d)}")
        # self.seed_matrix = False
        #
        # self.matrix.paste(self.seed_image, (0, 0))


        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate
