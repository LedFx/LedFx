import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)


@Effect.no_registration
class Twod(AudioReactiveEffect):
    start_time = timeit.default_timer()
    ADVANCED_KEYS = ["dump", "diag"]

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
                "dump",
                description="dump image",
                default=False,
            ): bool,
            vol.Optional(
                "diag",
                description="diagnostic enable",
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
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lasttime = 0
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.last_dump = self._config["dump"]
        self.t_height = -1

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20

        self.bar = 0

    def config_updated(self, config):
        self.diag = self._config["diag"]
        self.t_width = self._config["LED width"]
        temp_height = self.t_width

        # cannot get t_height here, pixel_count is not set yet on first call :-(
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
        # image should be the right size to map in, at this point
        if self.flip:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if self.mirror:
            rgb_image = rgb_image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if self.rotate != 0:
            rgb_image = rgb_image.transpose(self.rotate)

        # rgb_image should be the matching size to the display
        # TODO: Add speculative resize
        rgb_resized = rgb_image.resize(
            (self.t_width, self.t_height), Image.BICUBIC
        )
        rgb_bytes = rgb_resized.tobytes()
        rgb_array = np.frombuffer(rgb_bytes, dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)

        copy_length = min(self.pixels.shape[0], rgb_array.shape[0])
        self.pixels[:copy_length, :] = rgb_array[:copy_length, :]

        # self.pixels = rgb_array

        return rgb_image

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

    def try_dump(self, rgb_image):
        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            rgb_image.show()
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
        # should render into a PIL image at the final size for display
        # and return it!
        pass

    def render(self):
        # TODO: Move this and rgb_image into do_once function
        # also protect against insane width setting at first config
        self.t_height = max(1, int(self.pixel_count / self.t_width))

        self.log_sec()

        rgb_image = self.draw()
        rgb_image = self.image_to_pixels(rgb_image)

        self.try_log()
        self.try_dump(rgb_image)
