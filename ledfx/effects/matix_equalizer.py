import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Matrix_eq(Twod, GradientEffect):
    NAME = "Equalizer2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = ["speed", "background_brightness", "mirror", "flip", "blur"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    start_time = timeit.default_timer()

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "test",
                description="ignore audio input",
                default=False,
            ): bool,
            vol.Optional(
                "pattern",
                description="use a test pattern",
                default=False,
            ): bool,
            vol.Optional(
                "align",
                description="Alignment of bands",
                default="left",
            ): vol.In(list(["left", "right", "invert", "center"])),
            vol.Optional(
                "bands",
                description="Number of freq bands",
                default=16,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def config_updated(self, config):
        super().config_updated(config)
        # if we have an attibute for pixel_count the use it in calc, otherwise guess
        self.test = self._config["test"]
        self.pattern = self._config["pattern"]
        self.bands = self._config["bands"]
        self.init = False

    def do_once(self):
        # defer things that can't be done when pixel_count is not known
        self.max_dim = max(self.t_width, self.t_height)
        self.bands = min(self.bands, self.pixel_count)
        self.colors = []
        self.bandsx = []
        for i in range(self.bands):
            self.colors.append(
                self.get_gradient_color(1 / self.bands * i).astype(int)
            )
            self.bandsx.append(
                [
                    int(self.max_dim / self.bands * i),
                    int(self.max_dim / self.bands * (i + 1) - 1),
                ]
            )
        self.init = True

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)
        np.clip(self.r, 0, 1, out=self.r)

    def draw(self):
        if not self.init:
            self.do_once()

        rgb_image = Image.new(
            "RGB",
            (
                max(self.t_width, self.t_height),
                max(self.t_width, self.t_height),
            ),
        )
        rgb_draw = ImageDraw.Draw(rgb_image)

        if self.test:
            self.draw_test(rgb_draw)

        r_split = np.array_split(self.r, self.bands)

        for i in range(self.bands):
            volume = r_split[i].mean()
            rgb_draw.rectangle(
                (
                    self.bandsx[i][0],
                    0,
                    self.bandsx[i][1],
                    int(self.t_height * volume),
                ),
                fill=tuple(self.colors[i]),
            )

        self.roll_gradient()
        return rgb_image
