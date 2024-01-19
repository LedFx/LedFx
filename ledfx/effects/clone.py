import logging

import mss
import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Clone(Twod):
    NAME = "Clone"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test"]

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
        self.fails = 0
        self.giveup = False

    def draw(self):
        # if we hit 5 in a row, lets just give up and stop impacting the system
        if self.fails >= 5:
            self.giveup = True
            _LOGGER.warning(f"Clone giving up after {self.fails} failures")
            self.fails = 0

        if self.giveup:
            return

        if self.sct is None:
            try:
                self.sct = mss.mss()
                # set up a grab dict to be used in the grab call
                mon = self.sct.monitors[self.screen]
                self.grab = {
                    "top": mon["top"] + self.x,
                    "left": mon["left"] + self.y,
                    "width": self.width,
                    "height": self.height,
                    "mon": self.screen,
                }
            except Exception as e:
                self.fails += 1
                _LOGGER.warning(
                    f"Clone Error setting up grab: {self.fails} {e}"
                )
                self.sct = None
                return

        try:
            frame = self.sct.grab(self.grab)
        except Exception as e:
            self.fails += 1
            _LOGGER.warning(f"Clone Error grabbing frame :{self.fails}: {e}")
            self.sct = None
            return

        rgb_image = Image.frombytes(
            "RGB", frame.size, frame.bgra, "raw", "BGRX"
        )

        self.matrix = rgb_image.resize(
            (self.r_width, self.r_height), Image.BILINEAR
        )

        self.fails = 0
