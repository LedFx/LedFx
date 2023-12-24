import logging
import urllib.request

import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod
from ledfx.utils import get_icon_path

_LOGGER = logging.getLogger(__name__)


class Imagespin(Twod):
    NAME = "Image"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = ["speed", "background_brightness", "mirror", "flip", "blur"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + ["pattern"]

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
                "pattern",
                description="use a test pattern",
                default=False,
            ): bool,
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "multiplier",
                description="Applied to the audio input to amplify effect",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "Min Size",
                description="The minimum size multiplier for the image",
                default=0.3,
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
                "url source", description="Load image from", default=""
            ): str,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.spin = 0.0

    def config_updated(self, config):
        super().config_updated(config)

        self.clip = self._config["clip"]
        self.min_size = self._config["Min Size"]
        self.power_func = self._power_funcs[self._config["frequency_range"]]
        self.do_spin = self._config["spin"]
        self.init = True

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = (
            getattr(data, self.power_func)() * self._config["multiplier"] * 2
        )

    def open_image(self, image_path):
        try:
            if image_path.startswith("http://") or image_path.startswith(
                "https://" or image_path.startswith("file://")
            ):
                with urllib.request.urlopen(image_path) as url:
                    return Image.open(url)
            else:
                return Image.open(image_path)  # Directly open for local files
        except Exception as e:
            _LOGGER.error("Failed to open iamge: %s", e)
            return None

    def do_once(self):
        super().do_once()
        if self._config["pattern"]:
            url_path = "https://images.squarespace-cdn.com/content/v1/60cc480d9290423b888eb94a/1624780092100-4FLILMIV0YHHU45GB7XZ/Test+Pattern+t.png"
        else:
            url_path = self._config["url source"]

        if url_path != "":
            self.bass_image = self.open_image(url_path)
            if self.bass_image:
                self.bass_image.thumbnail(
                    (self.r_width * 4, self.r_height * 4)
                )
                _LOGGER.info(f"pre scaled {self.bass_image.size}")

                if self.bass_image.mode != "RGBA":
                    # If it doesn't have an alpha channel, create a new image with an alpha channel
                    image_with_alpha = Image.new(
                        "RGBA", self.bass_image.size, (255, 255, 255, 255)
                    )  # Create a white image with an alpha channel
                    image_with_alpha.paste(
                        self.bass_image, (0, 0)
                    )  # Paste the original image onto the new one
                    self.bass_image = image_with_alpha
            else:
                self.bass_image = Image.open(get_icon_path("tray.png"))
        else:
            self.bass_image = Image.open(get_icon_path("tray.png"))
        self.init = False

    def draw(self):
        if self.init:
            self.do_once()

        if self.test:
            self.draw_test(self.m_draw)
            size = 1.0
            spin = 1.0
        else:
            size = self.bar + self.min_size
            spin = self.bar

        image_w = int(self.r_width * size)
        image_h = int(self.r_height * size)

        if image_w > 0 and image_h > 0:
            # make a copy of the original that we will manipulate
            bass_sized_img = self.bass_image.copy()

            if self.do_spin:
                self.spin = (self.spin + spin) % 360.0
                bass_sized_img = bass_sized_img.rotate(
                    self.spin, expand=self.clip
                )

            # resize bass_image to fit in the target
            bass_sized_img.thumbnail(
                (image_w, image_h),
                Image.BILINEAR,
            )

            # render bass_sized_img into self.matrix centered with alpha
            self.matrix.paste(
                bass_sized_img,
                (
                    int((self.r_width - bass_sized_img.width) / 2),
                    int((self.r_height - bass_sized_img.height) / 2),
                ),
                bass_sized_img,
            )
