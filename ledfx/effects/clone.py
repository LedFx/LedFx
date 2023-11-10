import logging
import timeit

import mss
import numpy as np
import voluptuous as vol
from PIL import Image, ImageGrab

from ledfx.effects.temporal import TemporalEffect

_LOGGER = logging.getLogger(__name__)


class PixelsEffect(TemporalEffect):
    NAME = "Clone"
    CATEGORY = "Non-Reactive"
    HIDDEN_KEYS = ["speed", "background_brightness", "blur", "mirror", "flip"]

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
            vol.Optional(
                "LED width",
                description="Row width of target",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=128)),
            vol.Optional(
                "flip horizontal",
                description="flip the image horizontally",
                default=False,
            ): bool,
            vol.Optional(
                "flip vertical",
                description="flip the image vertically",
                default=False,
            ): bool,
            vol.Optional(
                "diag",
                description="diagnostic enable",
                default=False,
            ): bool,
            vol.Optional(
                "dump",
                description="dump image",
                default=False,
            ): bool,
            vol.Optional(
                "rotate",
                description="90 Degree rotations",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lasttime = 0
        self.frame = 0
        self.fps = 0
        self.sct = None
        self.last = 0
        self.with_mss = True
        self.last_dump = self._config["dump"]

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20

    def config_updated(self, config):
        self.diag = self._config["diag"]
        self.screen = self._config["screen"]
        self.x = self._config["down"]
        self.y = self._config["across"]
        self.width = self._config["width"]
        self.height = self._config["height"]
        self.t_width = self._config["LED width"]

        self.flip = self._config["flip vertical"]
        self.mirror = self._config["flip horizontal"]
        self.rotate = 0
        if self._config["rotate"] == 1:
            self.rotate = Image.Transpose.ROTATE_90
        if self._config["rotate"] == 2:
            self.rotate = Image.Transpose.ROTATE_180
        if self._config["rotate"] == 3:
            self.rotate = Image.Transpose.ROTATE_270

        self.sct = None

    def effect_loop(self):
        log = False
        now = timeit.default_timer()
        if self.diag:
            nowint = int(now)
            # if now just rolled over a second boundary
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                log = True
            else:
                self.frame += 1
            self.lasttime = nowint

        if self.with_mss is True:
            if self.sct is None:
                self.sct = mss.mss()
                self.t_height = int(self.pixel_count / self.t_width)

                # grab a screen clip from screen x at x,y of width, height
                mon = self.sct.monitors[self.screen]
                self.grab = {
                    "top": mon["top"] + self.x,
                    "left": mon["left"] + self.y,
                    "width": self.width,
                    "height": self.height,
                    "mon": self.screen,
                }

            pre_end = timeit.default_timer()
            frame = self.sct.grab(self.grab)
            part1_start = timeit.default_timer()
            rgb_image = Image.frombytes(
                "RGB", frame.size, frame.bgra, "raw", "BGRX"
            )
            part2_start = timeit.default_timer()
        else:  # with pillow
            self.t_height = int(self.pixel_count / self.t_width)
            # Define the coordinates of the screen area you want to capture
            box = (self.y, self.x, self.y + self.width, self.x + self.height)
            pre_end = timeit.default_timer()
            # Capture the screen area using Pillow-SIMD (ImageGrab)
            screenshot = ImageGrab.grab(bbox=box)
            part1_start = timeit.default_timer()
            # Convert the screenshot to an RGB image
            rgb_image = screenshot.convert("RGB")
            part2_start = timeit.default_timer()

        rgb_image = rgb_image.resize(
            (self.t_width, self.t_height), Image.BILINEAR
        )
        part3_start = timeit.default_timer()
        if self.flip:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if self.mirror:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if self.rotate != 0:
            rgb_image = rgb_image.transpose(self.rotate)
        part4_start = timeit.default_timer()
        rgb_bytes = rgb_image.tobytes()
        rgb_array = np.frombuffer(rgb_bytes, dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)
        part5_start = timeit.default_timer()

        self.pixels = rgb_array

        end = timeit.default_timer()
        if log is True:
            render_time = timeit.default_timer() - now
            _LOGGER.info(
                f"screen:{self.screen} x,y: {self.x},{self.y} w,h: {self.width},{self.height} to: {self.t_width}x{self.t_height} trans: {self.transpose}"
            )
            _LOGGER.info(f"clone FPS {self.fps} Full render:{render_time:.6f}")
            _LOGGER.info(
                f"cyc: {(end - self.last):0.4f} sleep: {(now - self.last):0.4f} pre: {(pre_end - now):0.4f} grab: {(part1_start - pre_end):0.4f} RGB: {(part2_start - part1_start):0.4f} size: {(part3_start - part2_start):0.4f} trans {(part4_start - part3_start):0.4f} mash: {(part5_start - part4_start):0.4f}"
            )

        self.last = end

        if self.last_dump != self._config["dump"]:
            _LOGGER.info("DUMP DUMP DUMP!!!!")
            self.last_dump = self._config["dump"]
            # show image on screen
            rgb_image.show()
            _LOGGER.info(
                f"screen:{self.screen} x,y: {self.x},{self.y} w,h: {self.width},{self.height} to: {self.t_width}x{self.t_height} R: {self.rotate} F: {self.flip} M: {self.mirror}"
            )

        return 0.05  # 0.1 64 fps, 0.2 32 fps don't know why
