import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

from ledfx.effects.temporal import TemporalEffect

_LOGGER = logging.getLogger(__name__)


class twod(TemporalEffect):
    NAME = "twod"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS = ["speed", "background_brightness", "blur", "mirror", "flip"]

    start_time = timeit.default_timer()

    CONFIG_SCHEMA = vol.Schema(
        {
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
        self.last = 0
        self.last_dump = self._config["dump"]

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20

    def config_updated(self, config):
        self.diag = self._config["diag"]
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

    def image_to_pixels(self, rgb_image):
        if self.flip:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if self.mirror:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if self.rotate != 0:
            rgb_image = rgb_image.transpose(self.rotate)
        rgb_bytes = rgb_image.tobytes()
        rgb_array = np.frombuffer(rgb_bytes, dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)
        self.pixels = rgb_array
        return rgb_image

    def log_sec(self, now):
        result = False
        if self.diag:
            nowint = int(now)
            # if now just rolled over a second boundary
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                result = True
            else:
                self.frame += 1
            self.lasttime = nowint
        return result

    def draw(self):
        # this should be an empty function with pass
        self.t_height = int(self.pixel_count / self.t_width)
        rgb_image = Image.new("RGB", (self.t_width, self.t_height))
        rgb_draw = ImageDraw.Draw(rgb_image)
        rgb_draw.rectangle(
            [(0, 0), (self.t_width - 1, self.t_height - 1)],
            fill=None,
            outline="white",
        )
        mid_w, mid_h = self.t_width / 2, self.t_height / 2
        rgb_draw.line([(0, 0), (mid_w, mid_h)], fill="red", width=1)
        rgb_draw.line(
            [(self.t_width - 1, 0), (mid_w, mid_h)], fill="blue", width=1
        )
        rgb_draw.line(
            [(0, self.t_height - 1), (mid_w, mid_h)], fill="green", width=1
        )
        rgb_draw.line(
            [(self.t_width - 1, self.t_height - 1), (mid_w, mid_h)],
            fill="white",
            width=1,
        )
        return rgb_image

    def effect_loop(self):
        now = timeit.default_timer()
        log = self.log_sec(now)
        rgb_image = self.draw()
        draw_end = timeit.default_timer()
        rgb_image = self.image_to_pixels(rgb_image)
        end = timeit.default_timer()

        if log is True:
            render_time = timeit.default_timer() - now
            _LOGGER.info(f"twod FPS {self.fps} Full render:{render_time:.6f}")
            _LOGGER.info(
                f"cyc: {(end - self.last):0.4f} sleep: {(now - self.last):0.4f} draw{(draw_end - now):0.4f} stuff {(end - draw_end):0.4f}"
            )

        self.last = end

        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            rgb_image.show()
            _LOGGER.info(
                f"dump {self.t_width}x{self.t_height} R: {self.rotate} F: {self.flip} M: {self.mirror}"
            )

        return 0.05  # 0.1 64 fps, 0.2 32 fps don't know why
