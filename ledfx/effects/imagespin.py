import logging
import os
from typing import Annotated, ClassVar

from PIL import Image
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.twod import Twod
from ledfx.utils import get_icon_path, open_gif

_LOGGER = logging.getLogger(__name__)


class Imagespin(Twod):
    NAME = "Image"
    CATEGORY = "Matrix"
    # image spin supports alpha so allow background color
    HIDDEN_KEYS: ClassVar[list[str]] = ["speed", "mirror", "flip", "blur", "album_art"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + ["pattern", "bilinear"]

    class Config(Twod.Config):
        pattern: bool = Field(False, description="use a test pattern")
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for the beat detection"
        )
        multiplier: CoercedFloat = Field(
            0.5,
            description="Applied to the audio input to amplify effect",
            ge=0.0,
            le=1.0,
        )
        min_size: CoercedFloat = Field(
            0.3, description="The minimum size multiplier for the image", ge=0.0, le=1.0
        )
        bilinear: bool = Field(
            False,
            description="default NEAREST, use BILINEAR for smoother scaling, expensive on runtime takes a few ms",
        )
        spin: bool = Field(False, description="spin image according to filter impulse")
        clip: bool = Field(
            False,
            description="When spinning the image, force fit to frame, or allow clipping",
        )
        image_source: str = Field("", description="Load image from")
        album_art: bool = Field(
            False, description="Configuration for Album art display"
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.spin = 0.0

    def config_updated(self, config):
        super().config_updated(config)

        self.clip = self.config.clip
        self.min_size = self.config.min_size
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]
        self.do_spin = self.config.spin
        self.resize = (
            Image.Resampling.BILINEAR
            if self.config.bilinear
            else Image.Resampling.NEAREST
        )
        self.album_art = self.config.album_art
        self.init = True

    def audio_data_updated(self, data):
        # Get filtered bar power
        self.bar = getattr(data, self.power_func)() * self.config.multiplier * 2

    def do_once(self):
        super().do_once()
        if self.config.pattern:
            url_path = (
                f"{os.path.join(LEDFX_ASSETS_PATH, 'test_images', 'TVTestPattern.png')}"
            )
        else:
            url_path = self.config.image_source

        if url_path != "":
            self.bass_image = open_gif(url_path, config_dir=self._ledfx.config_dir)
            if self.bass_image:
                _LOGGER.info("pre scaled %s", self.bass_image.size)

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

        # preserve image resolution for manipulation, but don't expand it
        self.bass_image.thumbnail(
            (
                min(self.r_width * 4, self.bass_image.width),
                min(self.r_height * 4, self.bass_image.height),
            )
        )

        self.init = False

    def draw(self):
        if self.init:
            self.do_once()

        if self.album_art:
            size = 1.0
            spin = 1.0
        elif self.test:
            size = 1.0
            spin = 1.0
            self.draw_test(self.m_draw)
        else:
            size = self.bar + self.min_size
            spin = self.bar

        image_w = int(self.r_width * size)
        image_h = int(self.r_height * size)

        if image_w > 0 and image_h > 0:
            # make a copy of the original that we will manipulate
            spin_img = self.bass_image

            if self.do_spin:
                self.spin = (self.spin + spin) % 360.0
                spin_img = spin_img.rotate(self.spin, expand=self.clip)

            # resize bass_image to fit in the target
            spin_img.thumbnail(
                (image_w, image_h),
                self.resize,
            )

            # render bass_sized_img into self.matrix centered with alpha
            self.matrix.paste(
                spin_img,
                (
                    int((self.r_width - spin_img.width) / 2),
                    int((self.r_height - spin_img.height) / 2),
                ),
                spin_img,
            )
