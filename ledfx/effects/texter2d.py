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

FONT_MAPPINGS = {
    "Roboto Regular": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Regular.ttf"),
    "Roboto Bold": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Bold.ttf"),
    "Roboto Black": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Black.ttf"),
    "Stop": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Stop.ttf"),
    "04b_30": os.path.join(LEDFX_ASSETS_PATH, "fonts", "04b_30__.ttf"),
    "8bitOperatorPlus8": os.path.join(LEDFX_ASSETS_PATH, "fonts", "8bitOperatorPlus8-Regular.ttf"),
    "Wayfarers Toy Box": os.path.join(LEDFX_ASSETS_PATH, "fonts", "WayfarersToyBoxRegular.ttf"),
    "Press Start 2P": os.path.join(LEDFX_ASSETS_PATH, "fonts", "PressStart2P.ttf"),}


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

    def __init__(self, text, font, disp_size, color='white'):
        self.text = text
        self.color = color
        self.ascent, self.descent = font.getmetrics()
        dummy_image = Image.new('L', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_image)
        left, top, right, bottom = dummy_draw.textbbox((0,0), text, font=font)
        self.width = right - left
        self.height = self.descent + self.ascent
        self.w_width = self.width / (disp_size[0] / 2)
        self.w_height = self.height / (disp_size[0] / 2)
        self.h_width = self.width / (disp_size[1] / 2)
        self.h_height = self.height / (disp_size[1] / 2)

        # word images are greyscale masks only
        self.image = Image.new('L', (self.width, self.height)) #, "grey")
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((0, 0), self.text, font=font, fill=color)
        self.pose = Pose(0, 0, 0, 1, 0, 1)

    def update(self, passed_time):
        active = self.pose.update(passed_time)
        return active

    def calculate_final_size(self):
        # angle_rad = math.radians(self.pose.ang * 360)
        angle_rad = self.pose.ang * 2 * math.pi

        cos_angle = abs(math.cos(angle_rad))
        sin_angle = abs(math.sin(angle_rad))

        rotated_width = self.image.height * sin_angle + self.image.width * cos_angle
        rotated_height = self.image.height * cos_angle + self.image.width * sin_angle

        final_width = max(1, round(rotated_width * self.pose.size))
        final_height = max(1, round(rotated_height * self.pose.size))

        return final_width, final_height

    def render(self, target, resize_method, color=None, values=None, values2=None):
        if self.pose.life > 0 and self.pose.alpha > 0.0 and self.pose.size > 0.0:
            # pretty rambling calculation to get the rotated size of the image
            # and clip it out if off the display
            pose_x = self.pose.x
            pose_y = self.pose.y
            c_width, c_height = self.calculate_final_size()
            half_width = target.width / 2
            half_height = target.height / 2
            e_x = round(abs(pose_x) * half_width) - c_width / 2
            e_y = round(abs(pose_y) * half_height) - c_height / 2
            if e_x < half_width and e_y < half_height:
                resized = self.image.rotate(self.pose.ang * 360, expand=True, resample=resize_method)
                resized = resized.resize((max(1, round(resized.width * self.pose.size)),
                                           max(1, round(resized.height * self.pose.size))),
                                         resample=resize_method)
                # self.pos is a scalar for x and y in the range -1 to 1
                # the pos position is for the center of the image
                # here we will convert it to a pixel position within target which is a PIL image object
                x = round(((pose_x + 1) * half_width) - (resized.width / 2))
                y = round(((pose_y + 1) * half_height) - (resized.height / 2))

                # _LOGGER.info(
                #     f"Textblock {self.text} x: {self.pose.x:3.3f} y: {self.pose.y:3.3f} {x} {y} ang: {self.pose.ang:3.3f} size: {self.pose.size:3.3f}")

                capped_alpha = min(1.0, max(0.0, self.pose.alpha))
                if capped_alpha < 1.0:
                    img_array = np.array(resized)
                    modified_array = np.clip(img_array * capped_alpha, 0, 255).astype(np.uint8)
                    resized = Image.fromarray(modified_array, mode='L')

                if color is not None:
                    color_img = Image.new("RGBA", resized.size, color)
                    r, g, b, a = color_img.split()
                    resized = Image.merge("RGBA", (r, g, b, resized))
                target.paste(resized, (x, y), resized)


class Sentence():
    # this class will construct and maintain a set of words,
    # spaces and animated dynamics for a sentence

    def __init__(self, text, font_name, points, disp_size):
        self.text = text
        self.font_path = FONT_MAPPINGS[font_name]
        self.points = points
        self.start_color = parse_color('white')
        self.font = ImageFont.truetype(self.font_path, self.points)
        self.wordblocks = []

        for word in self.text.split():
            wordblock = Textblock(word,
                             self.font, disp_size)
            self.wordblocks.append(wordblock)
            _LOGGER.info(f"Wordblock {word} created")
        self.space_block = Textblock(" ",
                                self.font, disp_size)
        self.wordcount = len(self.wordblocks)
        self.color_points = np.array([idx / max(1, self.wordcount-1) for idx in range(self.wordcount)])

        self.word_focus_active = False
        self.word_focus = -1
        self.d_word_focus = 0
        self.word_focus_callback = None

    def update(self, dt):
        if self.word_focus_active:
            # allow this to go out of range for theshold testing elsewhere
            # clip at point of application
            self.word_focus += self.d_word_focus * dt
            # TODO: where should this callback be called?
            # at word or sentence level, what should we allow it to do?
            # update or render level?

        for word in self.wordblocks:
            word.update(dt)

    def render(self, target, resize_method, color, values=None, values2=None):
        color_len = len(color)
        for i, word in enumerate(self.wordblocks):
            word.render(target, resize_method,
                        tuple(color[i % color_len]), values, values2)


TEXT_EFFECT_MAPPING = {
    "Side Scroll": {"init":"side_scroll_init", "func":"side_scroll_func"},
    "Carousel": {"init":"carousel_init", "func":"carousel_func"},
    "Wave": {"init":"wave_init", "func":"wave_func"},
    "Pulse": {"init":"pulse_init", "func":"pulse_func"},
    "Fade": {"init":"fade_init", "func":"fade_func"},
}

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
                "option_1",
                description="Text effect specific option switch",
                default=False,
            ): bool,
            vol.Optional(
                "option_2",
                description="Text effect specific option switch",
                default=False,
            ): bool,
            vol.Optional(
                "font",
                description="Font to render text with",
                default="Press Start 2P",
            ): vol.In(list(FONT_MAPPINGS.keys())),
            vol.Optional(
                "text",
                description="Your text to display",
                default="Your text here",
            ): str,
            vol.Optional(
                "height_percent",
                description="Font size as a percentage of the display height",
                default=100,
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
                "text_effect",
                description="Text effect to apply to configuration",
                default="Side Scroll",
            ): vol.In(list(TEXT_EFFECT_MAPPING.keys())),
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
            vol.Optional(
                "speed_option_1",
                description="general speed slider for text effects",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2)),
        },
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.alpha = self._config["alpha"]
        self.option_1 = self._config["option_1"]
        self.option_2 = self._config["option_2"]
        self.speed_option_1 = self._config["speed_option_1"]
        self.deep_diag = self._config["deep_diag"]
        self.use_gradient = self._config["use_gradient"]
        # putting text_color into a list so that it can be treated the same as a gradient list
        self.text_color = [parse_color(self._config["text_color"])]
        self.resize_method = RESIZE_METHOD_MAPPING[self._config["resize_method"]]
        self.multiplier = self._config["multiplier"]
        self.text_effect_funcs = TEXT_EFFECT_MAPPING[self._config["text_effect"]]

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
                                 round(self.r_height * self.config["height_percent"] / 100),
                                 (self.r_width, self.r_height))
        if self.deep_diag:
            self.overlay = Overlay(self.r_height, self.r_width)

        getattr(self, self.text_effect_funcs["init"])()

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

        if self.use_gradient:
            color_array = self.get_gradient_color_vectorized1d(self.sentence.color_points).astype(np.uint8)
        else:
            color_array = self.text_color

        self.impulses = interpolate_to_length(
            [self.lows_impulse, self.mids_impulse, self.high_impulse],
            self.sentence.wordcount)

        getattr(self, self.text_effect_funcs["func"])()

        self.sentence.update(self.passed)

        self.sentence.render(self.matrix, self.resize_method, color_array,
                             values=self.values, values2=self.values2)

        self.roll_gradient()

        if self.deep_diag:
            self.overlay.render(self.matrix, self.m_draw, values=self.values, values2=self.values2)


    ############################################################################
    # side_scroll
    ############################################################################

    def side_scroll_init(self):
        # first we need to set every word to be in a position off screen
        # each word will be offset by the word before and a space
        # first we need the first word width in screen units

        offset = 1
        self.base_speed = self.speed_option_1

        for idx, word in enumerate(self.sentence.wordblocks):
            offset += word.w_width / 2
            word.pose.set_vectors(offset, 0,
                                  0, 1, 10000)
            word.pose.d_pos = (self.base_speed, 0.5)
            offset += word.w_width / 2
            offset += self.sentence.space_block.w_width

    def side_scroll_func(self):
        if self.sentence.wordblocks[-1].pose.x + self.sentence.wordblocks[-1].w_width / 2 < -1:
            self.side_scroll_init()
        for word in self.sentence.wordblocks:
            if self.option_1:
                word.pose.d_pos = (self.base_speed + (self.lows_impulse * self.multiplier * self.base_speed), 0.5)
            if self.alpha:
                word.pose.alpha = min(1.0,
                                      0.1 + self.lows_impulse * self.multiplier)

        # _LOGGER.info(f"{self.sentence.wordblocks[0].pose.y:3.3f})")

    ############################################################################
    # carousel
    ############################################################################

    def carousel_init(self):
        self.wave_init()

    def carousel_func(self):
        self.wave_func()

    ############################################################################
    # wave
    ############################################################################

    def wave_init(self):
        # _LOGGER.info(f"wave_init: {self.sentence.text} {self.passed}")
        # wave is the temp home for any old spam effect
        offset = 2 / (self.sentence.wordcount + 5)
        for idx, word in enumerate(self.sentence.wordblocks):
            word.pose.set_vectors(-1 + (idx+3) * offset, -1 + (idx+3) * offset,
                                  0, 1, 10)
            word.pose.d_pos = (0.2, 1 / self.sentence.wordcount * idx)

    def wave_func(self):
        # _LOGGER.info(f"wave_func: {self.sentence.text} {self.passed}")
        for idx, word in enumerate(self.sentence.wordblocks):
            word.pose.d_rotation = self.impulses[idx] * self.multiplier
            word.pose.size = 0.3 + self.impulses[idx] * self.multiplier
            if self.alpha:
                word.pose.alpha = min(1.0,
                                      0.1 + self.impulses[idx] * self.multiplier)
            if word.pose.life <= 0:
                word.pose.life = 10
                word.pose.d_pos = (-word.pose.d_pos[0], word.pose.d_pos[1])

    ############################################################################
    # pulse
    ############################################################################

    def pulse_init(self):
        self.wave_init()

    def pulse_func(self):
        self.wave_func()

    ############################################################################
    # fade
    ############################################################################

    def fade_init(self):
        self.wave_init()

    def fade_func(self):
        self.wave_func()
