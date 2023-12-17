import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)


@Effect.no_registration
class Twod(AudioReactiveEffect):
    start_time = timeit.default_timer()
    HIDDEN_KEYS = ["background_brightness", "mirror", "flip", "blur"]
    ADVANCED_KEYS = ["dump", "diag", "test"]

    CONFIG_SCHEMA = vol.Schema(
        {
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
                "rotate",
                description="90 Degree rotations",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
            vol.Optional(
                "advanced",
                description="enable advanced options",
                default=False,
            ): bool,
            vol.Optional(
                "test",
                description="ignore audio input",
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
        self.bar = 0
        # TODO: Changes to this value from virtual config are only picked up
        # on change of effect
        self.t_height = self._virtual.config["rows"]
        self.t_width = self.pixel_count // self.t_height
        self.init = True

    def config_updated(self, config):
        self.diag = self._config["diag"]
        self.test = self._config["test"]

        # We will render in to native image size of the matrix on rotation
        # This saves us from having to do ugly resizing and aliasing effects
        # as well as a small performance boost
        # we need to accout for swapping vertical and horizotal for 90 / 270

        self.flip = self._config["flip vertical"]
        self.mirror = self._config["flip horizontal"]

        self.rotate = 0
        if self._config["rotate"] == 1:
            self.rotate = Image.Transpose.ROTATE_90
            self.flip, self.mirror = self.mirror, self.flip
        if self._config["rotate"] == 2:
            self.rotate = Image.Transpose.ROTATE_180
        if self._config["rotate"] == 3:
            self.rotate = Image.Transpose.ROTATE_270
            self.flip, self.mirror = self.mirror, self.flip
        self.init = True

    def do_once(self):
        # defer things that can't be done when pixel_count is not known
        # so therefore cannot be addressed in config_updated
        self.init = False

        if self._config["rotate"] == 1 or self._config["rotate"] == 3:
            # swap width and height for render
            self.r_width = self.t_height
            self.r_height = self.t_width
        else:
            self.r_width = self.t_width
            self.r_height = self.t_height

    def image_to_pixels(self):
        # image should be the right size to map in, at this point
        if self.flip:
            self.matrix = self.matrix.transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
            )
        if self.mirror:
            self.matrix = self.matrix.transpose(
                Image.Transpose.FLIP_LEFT_RIGHT
            )
        if self.rotate != 0:
            self.matrix = self.matrix.transpose(self.rotate)
        if self.matrix.size != (self.t_width, self.t_height):
            _LOGGER.error(
                f"Matrix is wrong size {self.matrix.size} vs r {(self.r_width, self.r_height)} vs t {(self.t_width, self.t_height)}"
            )

        rgb_array = np.frombuffer(self.matrix.tobytes(), dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)

        copy_length = min(self.pixels.shape[0], rgb_array.shape[0])
        self.pixels[:copy_length, :] = rgb_array[:copy_length, :]

    def log_sec(self):
        self.start = timeit.default_timer()
        result = False
        if self.diag:
            nowint = int(self.start)
            # if now just rolled over a second boundary
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                result = True
            else:
                self.frame += 1
            self.lasttime = nowint
        self.log = result

    def try_log(self):
        end = timeit.default_timer()
        if self.log is True:
            _LOGGER.info(
                f"FPS {self.fps} Render:{(end - self.start):0.6f} Cycle: {(end - self.last):0.6f} Sleep: {(self.start - self.last):0.6f}"
            )
        self.last = end
        return self.log

    def try_dump(self):
        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            self.matrix.show()
            _LOGGER.info(
                f"dump {self.t_width}x{self.t_height} R: {self.rotate} F: {self.flip} M: {self.mirror}"
            )

    def draw_test(self, rgb_draw):
        width, height = rgb_draw._image.size
        rgb_draw.rectangle(
            [(0, 0), (width - 1, height - 1)],
            fill=None,
            outline="white",
        )
        mid_w, mid_h = int(width / 2), int(height / 2)
        rgb_draw.line([(0, 0), (mid_w, mid_h)], fill="red", width=1)
        rgb_draw.line(
            [(width - 1, 0), (mid_w - 1, mid_h)],
            fill="blue",
            width=1,
        )
        rgb_draw.line(
            [(0, height - 1), (mid_w - 1, mid_h)],
            fill="green",
            width=1,
        )
        rgb_draw.line(
            [(width - 1, height - 1), (mid_w, mid_h)],
            fill="white",
            width=1,
        )

    def draw(self):
        # this should be implemented in the child class
        # should render into self.matrix at the final size
        # for display using self.m_draw
        pass

    def render(self):
        if self.init:
            self.do_once()

        self.log_sec()

        self.matrix = Image.new("RGB", (self.r_width, self.r_height))
        self.m_draw = ImageDraw.Draw(self.matrix)

        self.draw()
        self.image_to_pixels()

        self.try_log()
        self.try_dump()
