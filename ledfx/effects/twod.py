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
    EFFECT_START_TIME = timeit.default_timer()
    # hiding dump by default, a dev can turn it on explicitily via removal
    HIDDEN_KEYS = ["background_brightness", "mirror", "flip", "blur", "dump"]
    ADVANCED_KEYS = [
        "dump",
        "diag",
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
        self.r_total = 0.0
        self.last_dump = self._config["dump"]

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20
        self.bar = 0
        self.t_height = self._virtual.config["rows"]
        self.t_width = self.pixel_count // self.t_height
        # initialise here so inherited can assume it exists
        self.current_time = timeit.default_timer()
        self.init = True

    def config_updated(self, config):
        self.diag = self._config["diag"]
        self.test = self._config["test"]

        # We will render in to native image size of the matrix on rotation
        # This saves us from having to do ugly resizing and aliasing effects
        # as well as a small performance boost
        # we need to accout for swapping vertical and horizotal for 90 / 270

        self.flip = self._config["flip_vertical"]
        self.mirror = self._config["flip_horizontal"]

        self.rotate = self._config["rotate"]
        self.rotate_t = 0
        if self.rotate == 1:
            self.rotate_t = Image.Transpose.ROTATE_90
            self.flip, self.mirror = self.mirror, self.flip
        if self.rotate == 2:
            self.rotate_t = Image.Transpose.ROTATE_180
        if self.rotate == 3:
            self.rotate_t = Image.Transpose.ROTATE_270
            self.flip, self.mirror = self.mirror, self.flip

        self.init = True

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

        self.t_height = self._virtual.config["rows"]
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
        if self.flip:
            self.matrix = self.matrix.transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
            )
        if self.mirror:
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

    def log_sec(self):
        result = False
        if self.diag:
            nowint = int(self.current_time)
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
        r_time = end - self.current_time
        self.r_total += r_time
        if self.log is True:
            if self.fps > 0:
                r_avg = self.r_total / self.fps
            else:
                r_avg = 0.0
            _LOGGER.info(
                f"FPS {self.fps} Render:{r_avg:0.6f} Cycle: {(end - self.last):0.6f} Sleep: {(self.current_time - self.last):0.6f}"
            )
            self.r_total = 0.0
        self.last = end
        return self.log

    def try_dump(self):
        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            self.matrix.show()
            _LOGGER.info(
                f"dump {self.t_width}x{self.t_height} R: {self.rotate_t} F: {self.flip} M: {self.mirror}"
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
        self.current_time = timeit.default_timer()
        if self.init:
            self.do_once()
        # Update the time every frame

        self.log_sec()

        self.matrix = Image.new("RGB", (self.r_width, self.r_height))
        self.m_draw = ImageDraw.Draw(self.matrix)

        self.draw()
        self.image_to_pixels()

        self.try_log()
        self.try_dump()
