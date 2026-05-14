import logging
from random import randrange

import numpy as np
import voluptuous as vol

from ledfx.effects import Effect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Multitronic(Twod):
    NAME = "Multitronic"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "gradient_steps",
                description="How many color steps to pull from the gradient",
                default=6,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Optional(
                "bar_width",
                description="Bar width ratio to display axis",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "bar_gap_ratio",
                description="ratio of the bar to gap rendered according to BAR WIDTH",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=0.9)),
            vol.Optional(
                "speed",
                description="speed multipleir to audio impulse",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "anger",
                description="minimum speed for idle audio",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "static_layout",
                description="Precompute the layout and then only allow selection from it",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        # set any default values first, as config_updated will be called
        # from the super().__init__() which may depend on them
        self.bar = 0
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.static = self._config["static_layout"]
        self.speed = self._config["speed"]
        self.anger = self._config["anger"]
        self.bar_width = self._config["bar_width"]
        self.bar_gap_ratio = self._config["bar_gap_ratio"]
        self.gradient_steps = self._config["gradient_steps"]
        self.gradient_bins = self.gradient.get_gradient_colors_vectorized1d(
            np.linspace(0, 1, self.gradient_steps)
        )

    def get_rand_color(self):
        # get a random gradient color from the gradient using gradent steps as resolution of extraction.
        return self.gradient_bins[randrange(self.gradient_steps)]

    def do_once(self):
        super().do_once()

        self.bar_w = max(1, int(self.matrix.width * self.bar_width))
        self.bar_h = max(1, int(self.matrix.height * self.bar_width))

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
        # Measure time passed per frame from the self.now and self.passed vars
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

        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate
