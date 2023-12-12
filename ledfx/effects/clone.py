import logging
import timeit

import mss
import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Clone(Twod):
    NAME = "Clone"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test"]

    start_time = timeit.default_timer()

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "screen",
                description="Source screen for grab",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=4)),
            vol.Optional(
                "down",
                description="pixels down offset of grab",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1080)),
            vol.Optional(
                "across",
                description="pixels across offset of grab",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1920)),
            vol.Optional(
                "width",
                description="width of grab",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1920)),
            vol.Optional(
                "height",
                description="height of grab",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1080)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.grab = None
        self.sct = None

    def config_updated(self, config):
        super().config_updated(config)

        self.screen = self._config["screen"]
        self.x = self._config["down"]
        self.y = self._config["across"]
        self.width = self._config["width"]
        self.height = self._config["height"]
        self.grab = None
        self.sct = None

    def draw(self):
        if self.sct is None:
            self.sct = mss.mss()
        else:
            # this is a deep sniff to see if the sct object is still valid
            # Don't like it, but some cases _handles is empty!
            if not hasattr(self.sct._handles, "srcdc"):
                self.sct = mss.mss()
                _LOGGER.warning("Recreated sct")

        if self.grab is None:
            # grab a screen clip from screen x at x,y of width, height
            mon = self.sct.monitors[self.screen]
            self.grab = {
                "top": mon["top"] + self.x,
                "left": mon["left"] + self.y,
                "width": self.width,
                "height": self.height,
                "mon": self.screen,
            }

        pre = timeit.default_timer()
        frame = self.sct.grab(self.grab)
        grab = timeit.default_timer()

        rgb_image = Image.frombytes(
            "RGB", frame.size, frame.bgra, "raw", "BGRX"
        )

        rgb_image = rgb_image.resize(
            (self.t_width, self.t_height), Image.BILINEAR
        )

        return rgb_image
