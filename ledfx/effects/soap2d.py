import logging
import noise
import random
import voluptuous as vol

from ledfx.effects import Effect
from ledfx.effects.twod import Twod
import numpy as np

_LOGGER = logging.getLogger(__name__)

# this effect is inspired by the WLED soap effect found at
# https://github.com/Aircoookie/WLED/blob/f513cae66eecb2c9b4e8198bd0eb52d209ee281f/wled00/FX.cpp#L7472


def random16():
    return random.randint(0, 65535)


class Soap2d(Twod):
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

    def do_once(self):
        super().do_once()
        cols = self.r_width
        rows = self.r_height
        self.noise3d = np.zeros((rows, cols), dtype=np.uint8)
        self.noise32_x = np.uint32(random16())
        self.noise32_y = np.uint32(random16())
        self.noise32_z = np.uint32(random16())
        self.scale32_x = np.uint32(160000 // cols)
        self.scale32_y = np.uint32(160000 // rows)
        self.mov = min(cols, rows)*(self.speed + 2)/2
        self.smoothness = min(250, self.intensity)

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

        self.noise32_x += self.mov
        self.noise32_y += self.mov
        self.noise32_z += self.mov

        cols = self.r_width
        rows = self.r_height
        self.noise3d = np.zeros((rows, cols), dtype=np.uint8)

        for i in range(cols):
            ioffset = np.int32(self.scale32_x * (i - cols // 2))
            for j in range(rows):
                joffset = np.int32(self.scale32_y * (j - rows // 2))
                noise_val = noise.pnoise3(self.noise32_x + ioffset,
                                          self.noise32_y + joffset,
                                          self.noise32_z )
                data = np.uint8((noise_val + 1) * 127.5)
                _LOGGER.info(f"noise_val: {noise_val}, data: {data}")


        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate
