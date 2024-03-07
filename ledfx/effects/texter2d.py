import logging
import os
from enum import Enum

import voluptuous as vol
import math
import numpy as np

from ledfx.effects.twod import Twod
from ledfx.effects.gradient import GradientEffect
from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.color import parse_color, validate_color
from ledfx.effects.utils.pose import Pose, interpolate_to_length
from ledfx.effects.utils.overlay import Overlay
from collections import deque

from PIL import Image, ImageDraw, ImageFont

_LOGGER = logging.getLogger(__name__)

DEBUG = False

FONT_MAPPINGS = {
    "Roboto Regular": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Regular.ttf"),
    "Roboto Bold": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Bold.ttf"),
    "Roboto Black": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Black.ttf"),
    "Stop": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Stop.ttf"),
    "04b_30": os.path.join(LEDFX_ASSETS_PATH, "fonts", "04b_30__.ttf"),
    "8bitOperatorPlus8": os.path.join(LEDFX_ASSETS_PATH, "fonts", "8bitOperatorPlus8-Regular.ttf")}


# These are different from gif resize methods, LANCZOS is not supported
class ResizeMethods(Enum):
    # https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters-comparison-table
    NEAREST = "Fastest"
    BILINEAR = "Fast"
    BICUBIC = "Slow"

RESIZE_METHOD_MAPPING = {
    ResizeMethods.NEAREST.value: Image.NEAREST,
    ResizeMethods.BILINEAR.value: Image.BILINEAR,
    ResizeMethods.BICUBIC.value: Image.BICUBIC,
}


class Textblock():
    # this class is intended to establish a pillow image object with rendered text within it
    # text will be created from the passed font at the requested size
    # the pillow image will have an alpha channel, and will always be transparent
    # the text will be rendered in the color requested
    # the text will be centered in the image which is only big enough to contain the text
    # the Textblock instance will be merged into the main display image outside of this class
    # so TextBlock has no idea of position which will be handled externally to this class

    def __init__(self, text, font, color='white'):
        self.text = text
        # open the font file
        self.color = color
        self.ascent, self.descent = font.getmetrics()
        dummy_image = Image.new('L', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_image)
        left, top, right, bottom = dummy_draw.textbbox((0,0), text, font=font)
        self.width = right - left
        self.height = self.descent + self.ascent
        # word images are greyscale masks only
        self.image = Image.new('L', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((0, 0), self.text, font=font, fill=color)
        self.pose = Pose(0, 0, 0, 1, 0, 1)

    def update(self, passed_time):
        active = self.pose.update(passed_time)
        return active

    def render(self, target, resize_method, color=None, values=None, values2=None):
        if self.pose.life > 0:
            # TODO: add a fast clipping algorithm to avoid rendering off screen

            # first we will rotate and then size the image
            # ang is a rotation from 0 to 1 float to represent 0 to 360 degrees
            # size is a float from 0 to 1 to represent 0 to 100% size, clip to min 1 pixel
            resized = self.image.rotate(self.pose.ang * 360, expand=True, resample=resize_method)
            resized = resized.resize((max(1, math.floor(resized.width * self.pose.size)),
                                       max(1, math.floor(resized.height * self.pose.size))),
                                     resample=resize_method)

            # self.pos is a scalar for x and y in the range -1 to 1
            # the pos position is for the center of the image
            # here we will convert it to a pixel position within target which is a PIL image object
            x = math.floor(((self.pose.x + 1) * target.width / 2) - (resized.width / 2))
            y = math.floor(((self.pose.y + 1) * target.height / 2) - (resized.height / 2))
            # _LOGGER.info(
            #     f"Textblock {self.text} x: {self.pose.x:3.3f} y: {self.pose.y:3.3f} {x} {y} ang: {self.pose.ang:3.3f} size: {self.pose.size:3.3f}")
            if self.pose.alpha < 1.0:
                img_array = np.array(resized)
                modified_array = np.clip(img_array * self.pose.alpha, 0, 255).astype(np.uint8)
                resized = Image.fromarray(modified_array, mode='L')

            if color is not None:
                color_img = Image.new("RGBA", resized.size, color)
                r, g, b, a = color_img.split()
                resized = Image.merge("RGBA", (r, g, b, resized))

            target.paste(resized, (x, y), resized)


class Sentence():
    # this class will construct and maintain a set of words,
    # spaces and animated dynamics for a sentence

    ANIMATIONS = {
        "SIDE_SCROLL"
    }

    def __init__(self, text, font_name, points):
        self.text = text
        self.font_path = FONT_MAPPINGS[font_name]
        self.points = points
        self.start_color = parse_color('white')
        self.font = ImageFont.truetype(self.font_path, self.points)
        self.wordblocks = []

        for word in self.text.split():
            wordblock = Textblock(word,
                             self.font)
            self.wordblocks.append(wordblock)
            _LOGGER.info(f"Wordblock {word} created")
            if DEBUG:
                wordblock.image.show()
        space_block = Textblock(" ",
                                self.font)
        self.space_width = space_block.width
        self.wordcount = len(self.wordblocks)
        _LOGGER.info(f"Space width is {self.space_width}")
        self.color_points = np.array([idx / max(1, self.wordcount-1) for idx in range(self.wordcount)])

        # the following block of code is hacking positions and other and should be replaced in due course
        offset = 2 / (self.wordcount + 5)
        for idx, word in enumerate(self.wordblocks):
            word.pose.set_vectors(-1 + (idx+3) * offset, -1 + (idx+3) * offset,
                                  0, 1, 10)
            word.pose.d_pos = (0.2, 1 / self.wordcount * idx)

    def update(self, passed_time):
        for word in self.wordblocks:
            word.update(passed_time)
            # TODO: the following is hack code, and needs to go
            # TODO: investigate concept of callbacks on limit reached in modifiers to allow chaining of behaviors
            if word.pose.life <= 0:
                word.pose.life = 10
                word.pose.d_pos = (-word.pose.d_pos[0], word.pose.d_pos[1])


    def render(self, target, resize_method, color, values=None, values2=None):
        color_len = len(color)
        for i, word in enumerate(self.wordblocks):
            word.render(target, resize_method,
                        tuple(color[i % color_len]), values, values2)


class Texter2d(Twod, GradientEffect):
    NAME = "Texter"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "alpha",
                description="apply alpha effect to text",
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
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=150)),
            vol.Optional(
                "text_color",
                description="Color of text",
                default="#FFFFFF",
            ): validate_color,
            vol.Optional(
                "resize_method",
                description="What aliasing strategy to use when manipulating text elements",
                default=ResizeMethods.BILINEAR.value,
            ): vol.In(
                [resize_method.value for resize_method in ResizeMethods]
            ),
            vol.Optional(
                "deep_diag",
                description="Diagnostic overlayed on matrix",
                default=False,
            ): bool,
            vol.Optional(
                "use_gradient",
                description="Use gradient for word colors",
                default=False,
            ): bool,
            vol.Optional(
                "impulse_decay",
                description="Decay filter applied to the impulse for development",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "multiplier",
                description="general multiplier slider for development",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
        },
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.alpha = self._config["alpha"]
        self.deep_diag = self._config["deep_diag"]
        self.use_gradient = self._config["use_gradient"]
        # putting text_color into a list so that it can be treated the same as a gradient list
        self.text_color = [parse_color(self._config["text_color"])]
        self.resize_method = RESIZE_METHOD_MAPPING[self._config["resize_method"]]
        self.multiplier = self._config["multiplier"]

        self.lows_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99)

        self.mids_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99)

        self.high_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99)

        self.lows_impulse = 0
        self.mids_impulse = 0
        self.high_impulse = 0

        self.values = deque(maxlen=1024)
        self.values2 = deque(maxlen=1024)

    def do_once(self):
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        self.sentence = Sentence(self.config["text"],
                                 self.config["font"],
                                 math.floor(self.r_height * self.config["height_percent"] / 100))
        if self.deep_diag:
            self.overlay = Overlay(self.r_height, self.r_width)

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

        self.lows_impulse = self.lows_impulse_filter.update(data.lows_power(filtered=False))
        self.mids_impulse = self.mids_impulse_filter.update(data.mids_power(filtered=False))
        self.high_impulse = self.high_impulse_filter.update(data.high_power(filtered=False))
#        _LOGGER.info(f"lows: {self.lows_impulse:3.3f} mids: {self.mids_impulse:3.3f} high: {self.high_impulse:3.3f}")

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)


        impulses = interpolate_to_length([self.lows_impulse, self.mids_impulse, self.high_impulse], self.sentence.wordcount)
#        _LOGGER.info(f"impulses: {impulses}")
        for idx, word in enumerate(self.sentence.wordblocks):
            word.pose.d_rotation = impulses[idx] * self.multiplier
            word.pose.size = 0.3 + impulses[idx] * self.multiplier
            if self.alpha:
                word.pose.alpha = min(1.0, 0.1 + impulses[idx] * self.multiplier)

        # TODO: Lets work clipping, then on a movement vector next

        if self.use_gradient:
            color = self.get_gradient_color_vectorized1d(self.sentence.color_points).astype(np.uint8)
        else:
            color = self.text_color

        self.sentence.update(self.passed)

        self.sentence.render(self.matrix, self.resize_method, color,
                             values=self.values, values2=self.values2)

        self.roll_gradient()

        if self.deep_diag:
            self.overlay.render(self.matrix, self.m_draw, values=self.values, values2=self.values2)
