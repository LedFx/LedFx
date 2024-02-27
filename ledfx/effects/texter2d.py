import logging
import os

import voluptuous as vol

from ledfx.effects import Effect
from ledfx.effects.twod import Twod
from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.color import parse_color, validate_color

from PIL import Image, ImageDraw, ImageFont

_LOGGER = logging.getLogger(__name__)

# copy this file and rename it into the effects folder
# Anywhere you see template, replace it with your own class reference / name

# create a dict of font name strings and file locations for opening from pillow

# Replace Robot Crush
# Find better fonts
# Work out why value validation is going pop

FONT_MAPPINGS = {"Robot Crush": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Robot Crush.ttf"),
                 "Robot Crush Italic": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Robot Crush Italic.ttf"),
                 "04b_30": os.path.join(LEDFX_ASSETS_PATH, "fonts", "04b_30__.ttf"),
                 "8bitOperatorPlus8": os.path.join(LEDFX_ASSETS_PATH, "fonts", "8bitOperatorPlus8-Regular.ttf")}

class Textblock():
    # this class is intended to establish a pillow image object with rendered text within it
    # text will be created from the passed font at the requested size
    # the pillow image will have an alpha channel, and will always be transparent
    # the text will be rendered in the color requested
    # the text will be centered in the image which is only big enough to contain the text
    # the Textblock instance will be merged into the main display image outside of this class
    # so TextBlock has no idea of position which will be handled externally to this class

    def __init__(self, text, font, size, color):
        self.text = text
        # open the font file
        self.font_path = FONT_MAPPINGS[font]
        self.size = size
        self.color = color
        self.font = ImageFont.truetype(self.font_path, size)
        self.ascent, self.descent = self.font.getmetrics()

        dummy_image = Image.new('RGB', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_image)
        left, top, right, bottom = dummy_draw.textbbox((0,0), text, font=self.font)
        self.width = right - left
        self.height = bottom - top + self.descent
        self.image = Image.new('RGBA', (self.width, self.height), "blue")
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((0, 0), self.text, font=self.font, fill=color)
        self.image.show()


class Texter2d(Twod):
    NAME = "Texter"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "a_switch",
                description="Does a boolean thing",
                default=False,
            ): bool,
            vol.Optional(
                "font",
                description="Font to render text with",
                default="8bitOperatorPlus8",
            ): vol.In(list(FONT_MAPPINGS.keys())),
            vol.Optional(
                "text",
                description="Your text to display",
                default="Your text here",
            ): str,
            vol.Optional(
                "height_percent",
                description="Font size as a percentage of the display height",
                default=75,
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
            vol.Optional(
                "text_color",
                description="Color of text",
                default="#FFFFFF",
            ): validate_color,
        },
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["a_switch"]

    def do_once(self):
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        self.text1 = Textblock(self.config["text"],
                               self.config["font"],
                               int(self.r_height * self.config["height_percent"] / 100),
                               parse_color(self.config["text_color"]))

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        # all rotation abstraction is done for you
        # you can use image dimensions now
        # self.matrix.height
        # self.matrix.width

        # look in this function for basic lines etc, use pillow primitives
        # for regular shapes
        if self.test:
            self.draw_test(self.m_draw)

        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate
