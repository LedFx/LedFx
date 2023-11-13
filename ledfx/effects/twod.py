import logging
import timeit
import urllib.request

import numpy as np
import voluptuous as vol

from PIL import Image, ImageDraw

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.utils import get_icon_path

_LOGGER = logging.getLogger(__name__)


class twod(AudioReactiveEffect):
    NAME = "twod"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS = ["speed", "background_brightness", "mirror", "flip", "blur"]

    start_time = timeit.default_timer()

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

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
                "test",
                description="trigger stuff",
                default=False,
            ): bool,
            vol.Optional(
                "rotate",
                description="90 Degree rotations",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "multiplier",
                description="Make the reactive bar bigger/smaller",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "spin",
                description="spin image according to filter impulse",
                default=False,
            ): bool,
            vol.Optional(
                "clip",
                description="When spinning the image, force fit to frame, or allow clipping",
                default=False,
            ): bool,
            vol.Optional(
                "url source", description="Load image from",
                default=""
            ): str,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.lasttime = 0
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.last_dump = self._config["dump"]
        self.spin = 0
        self.t_height = -1

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20

        self.bar = 0

    def config_updated(self, config):
        self.diag = self._config["diag"]
        self.t_width = self._config["LED width"]
        # if we have an attibute for pixel_count the use it in calc, otherwise guess
        if hasattr(self, "pixel_count"):
            temp_height = int(self.pixel_count / self.t_width)
        else:
            temp_height = self.t_width

        # cannot get t_height here, pixel_count is not set yet on first call :-(
        self.flip = self._config["flip vertical"]
        self.mirror = self._config["flip horizontal"]
        self.clip = self._config["clip"]
        self.test = self._config["test"]
        self.rotate = 0
        if self._config["rotate"] == 1:
            self.rotate = Image.Transpose.ROTATE_90
        if self._config["rotate"] == 2:
            self.rotate = Image.Transpose.ROTATE_180
        if self._config["rotate"] == 3:
            self.rotate = Image.Transpose.ROTATE_270

        if self.test:
            url_path = "https://images.squarespace-cdn.com/content/v1/60cc480d9290423b888eb94a/1624780092100-4FLILMIV0YHHU45GB7XZ/Test+Pattern+t.png"
        else:
            url_path = self._config["url source"]

        if url_path != "":
            try:
                with urllib.request.urlopen(url_path) as url:
                    self.bass_image = Image.open(url)
                    self.bass_image.thumbnail((self.t_width * 4, temp_height * 4))
                _LOGGER.info(f"pre scaled {self.bass_image.size}")

                if self.bass_image.mode != "RGBA":
                    # If it doesn't have an alpha channel, create a new image with an alpha channel
                    image_with_alpha = Image.new("RGBA", self.bass_image.size, (255, 255, 255, 255))  # Create a white image with an alpha channel
                    image_with_alpha.paste(self.bass_image, (0, 0))  # Paste the original image onto the new one
                    self.bass_image = image_with_alpha
            except Exception as e:
                _LOGGER.error(f"Failed to load image from {self._config['url source']}: {e}")
                self.bass_image = Image.open(get_icon_path("tray.png"))
        else:
            self.bass_image = Image.open(get_icon_path("tray.png"))

        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = (
            getattr(data, self.power_func)() * self._config["multiplier"] * 2
        )

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
        if self.t_height == -1:
            self.t_height = int(self.pixel_count / self.t_width)

        rgb_image = Image.new("RGB", (self.t_width, self.t_height))
        rgb_draw = ImageDraw.Draw(rgb_image)
        if self.test:
            rgb_draw.rectangle(
                [(0, 0), (self.t_width - 1, self.t_height - 1)],
                fill=None,
                outline="white",
            )
            mid_w, mid_h = int(self.t_width / 2), int(self.t_height / 2)
            rgb_draw.line([(0, 0), (mid_w, mid_h)], fill="red", width=1)
            rgb_draw.line(
                [(self.t_width - 1, 0), (mid_w-1, mid_h)], fill="blue", width=1
            )
            rgb_draw.line(
                [(0, self.t_height - 1), (mid_w-1, mid_h)], fill="green", width=1
            )
            rgb_draw.line(
                [(self.t_width - 1, self.t_height - 1), (mid_w, mid_h)],
                fill="white",
                width=1,
            )

        if self.test:
            self.bar = 1.0

        image_w = int(self.t_width * self.bar)
        image_h = int(self.t_height * self.bar)

        if image_w > 0 and image_h > 0:

            # make a copy of the original that we will manipulate
            bass_sized_img = self.bass_image.copy()

            if self._config["spin"]:
                self.spin += self.bar
                if self.spin > 360:
                    self.spin = 0
                bass_sized_img = bass_sized_img.rotate(self.spin, expand = self.clip)

            # resize bass_image to fit in the target
            bass_sized_img.thumbnail(
                (image_w, image_h),
                Image.BILINEAR,
            )

            # render bass_sized_img into rgb_image centered with alpha
            rgb_image.paste(
                bass_sized_img,
                (
                    int((self.t_width - bass_sized_img.width) / 2),
                    int((self.t_height - bass_sized_img.height) / 2),
                ),
                bass_sized_img,
            )
        return rgb_image

    def render(self):
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
                f"cyc: {(end - self.last):0.4f} sleep: {(now - self.last):0.4f} draw {(draw_end - now):0.4f} stuff {(end - draw_end):0.4f}"
            )

        self.last = end

        if self.last_dump != self._config["dump"]:
            self.last_dump = self._config["dump"]
            # show image on screen
            rgb_image.show()
            _LOGGER.info(
                f"dump {self.t_width}x{self.t_height} R: {self.rotate} F: {self.flip} M: {self.mirror}"
            )
