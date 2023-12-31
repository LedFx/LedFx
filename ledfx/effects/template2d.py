import logging
import timeit

import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# Anywhere you see template, replace it with your own class reference / name

class Template2d(Twod, GradientEffect):
    NAME = "Template2d"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    start_time = timeit.default_timer()

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "A switch",
                description="Does a boolean thing",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["A switch"]

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known
        # this is probably important for most 2d matrix where you want
        # things to be initialized to the space

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        # all rotation abstraction is done for you
        # self.matrix.height
        # self.matrix.width

        # look in this function for basic lines etc, use pillow primitives
        # for regular shapes
        if self.test:
            self.draw_test(self.m_draw)

        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate

