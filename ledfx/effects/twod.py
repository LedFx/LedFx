import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw, ImageEnhance

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.utils.logsec import LogSec

_LOGGER = logging.getLogger(__name__)


@Effect.no_registration
class Twod(AudioReactiveEffect, LogSec):
    EFFECT_START_TIME = timeit.default_timer()
    # hiding dump by default, a dev can turn it on explicitily via removal
    HIDDEN_KEYS = ["background_brightness", "mirror", "flip", "blur", "dump"]
    ADVANCED_KEYS = LogSec.ADVANCED_KEYS + [
        "dump",
        "test",
        "flip_horizontal",
        "flip_vertical",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "flip_horizontal",
                description="flip the image horizontally",
                default=False,
            ): bool,
            vol.Optional(
                "flip_vertical",
                description="flip the image vertically",
                default=False,
            ): bool,
            vol.Optional(
                "rotate",
                description="90 Degree rotations",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
            vol.Optional(
                "test",
                description="ignore audio input",
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
        self.last_dump = self._config["dump"]

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20
        self.bar = 0
        self.t_height = max(1, self._virtual.config["rows"])
        self.t_width = self.pixel_count // self.t_height
        self.init = True

    def config_updated(self, config):
        self.test = self._config["test"]

        # We will render in to native image size of the matrix on rotation
        # This saves us from having to do ugly resizing and aliasing effects
        # as well as a small performance boost
        # we need to accout for swapping vertical and horizotal for 90 / 270

        self.flip2d = self._config["flip_vertical"]
        self.mirror2d = self._config["flip_horizontal"]

        self.rotate = self._config["rotate"]
        self.rotate_t = 0
        if self.rotate == 1:
            self.rotate_t = Image.Transpose.ROTATE_90
            self.flip2d, self.mirror2d = self.mirror2d, self.flip2d
        if self.rotate == 2:
            self.rotate_t = Image.Transpose.ROTATE_180
        if self.rotate == 3:
            self.rotate_t = Image.Transpose.ROTATE_270
            self.flip2d, self.mirror2d = self.mirror2d, self.flip2d

        self.init = True

        # the walker will not call config_updated for multiple inherited classes
        # so if you a making a sub class you have to call this yourself
        LogSec.config_updated(self, config)

    def set_init(self):
        """
        Kick the init flag to True so that an effect can reconfigure itself
        when running in its own context if it has a dependancy on the virtual
        setting this flag keeps things atomic and ensures that the effect is not
        reconfigured while it is being rendered or otherwise in use
        """
        self.init = True

    def do_once(self):
        # defer things that can't be done when pixel_count is not known
        # so therefore cannot be addressed in config_updated
        # also triggered by config change in parent virtual
        # presently only on row change

        self.t_height = max(1, self._virtual.config["rows"])
        self.t_width = self.pixel_count // self.t_height

        if self.rotate == 1 or self.rotate == 3:
            # swap width and height for render
            self.r_width = self.t_height
            self.r_height = self.t_width
        else:
            self.r_width = self.t_width
            self.r_height = self.t_height

        self.init = False

    def image_to_pixels(self):
        # image should be the right size to map in, at this point
        if self.flip2d:
            self.matrix = self.matrix.transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
            )
        if self.mirror2d:
            self.matrix = self.matrix.transpose(
                Image.Transpose.FLIP_LEFT_RIGHT
            )
        if self.rotate_t != 0:
            self.matrix = self.matrix.transpose(self.rotate_t)
        if self.matrix.size != (self.t_width, self.t_height):
            _LOGGER.error(
                f"Matrix is wrong size {self.matrix.size} vs r {(self.r_width, self.r_height)} vs t {(self.t_width, self.t_height)}"
            )

        rgb_array = np.frombuffer(self.matrix.tobytes(), dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)

        copy_length = min(self.pixels.shape[0], rgb_array.shape[0])
        self.pixels[:copy_length, :] = rgb_array[:copy_length, :]

    def try_dump(self):
        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            self.matrix.show()
            _LOGGER.info(
                f"dump {self.t_width}x{self.t_height} R: {self.rotate_t} F: {self.flip2d} M: {self.mirror2d}"
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

    def get_matrix(self, brightness=True):
        with self.lock:
            result = self.matrix.copy()
            if brightness and self.brightness != 1.0:
                result = ImageEnhance.Brightness(result).enhance(
                    self.brightness
                )
            return result

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
