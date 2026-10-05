import logging

import mss
from PIL import Image
from pydantic import Field

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Clone(Twod):
    NAME = "Clone"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "test",
        "background_color",
        "background_brightness",
        "background_mode",
    ]

    class Config(Twod.Config):
        screen: CoercedInt = Field(0, description="Source screen for grab", ge=0, le=4)
        down: CoercedInt = Field(
            0, description="pixels down offset of grab", ge=0, le=1080
        )
        across: CoercedInt = Field(
            0, description="pixels across offset of grab", ge=0, le=1920
        )
        width: CoercedInt = Field(128, description="width of grab", ge=1, le=1920)
        height: CoercedInt = Field(128, description="height of grab", ge=1, le=1080)

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        self.grab = None
        self.sct = None
        super().__init__(ledfx, config)

    def _close_capture(self) -> None:
        capture, self.sct = self.sct, None
        self.grab = None
        if capture is not None:
            try:
                capture.close()
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Clone Error closing capture: %s", e)

    def deactivate(self) -> None:
        self._close_capture()
        super().deactivate()

    def config_updated(self, config):
        super().config_updated(config)

        self.screen = self.config.screen
        self.x = self.config.down
        self.y = self.config.across
        self.width = self.config.width
        self.height = self.config.height
        self._close_capture()
        self.fails = 0
        self.giveup = False

    def draw(self):
        # if we hit 5 in a row, lets just give up and stop impacting the system
        if self.fails >= 5:
            self.giveup = True
            _LOGGER.warning("Clone giving up after %s failures", self.fails)
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
            except Exception as e:  # noqa: BLE001
                self.fails += 1
                _LOGGER.warning("Clone Error setting up grab: %s %s", self.fails, e)
                self._close_capture()
                return

        try:
            frame = self.sct.grab(self.grab)
        except Exception as e:  # noqa: BLE001
            self.fails += 1
            _LOGGER.warning("Clone Error grabbing frame :%s: %s", self.fails, e)
            self._close_capture()
            return

        rgb_image = Image.frombytes("RGB", frame.size, frame.bgra, "raw", "BGRX")

        self.matrix = rgb_image.resize((self.r_width, self.r_height), Image.BILINEAR)

        self.fails = 0
