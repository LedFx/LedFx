import logging
import math
import random
from collections import deque
from enum import Enum

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.color import parse_color, validate_color
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod
from ledfx.effects.utils.overlay import Overlay
from ledfx.effects.utils.pose import interpolate_to_length, tween
from ledfx.effects.utils.words import FONT_MAPPINGS, Sentence

_LOGGER = logging.getLogger(__name__)


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


# TODO: currently only Side Scroll, Spokes and Wave are unique effects
# all other are copy of wave
TEXT_EFFECT_MAPPING = {
    "Side Scroll": {"init": "side_scroll_init", "func": "side_scroll_func"},
    "Spokes": {"init": "spokes_init", "func": "spokes_func"},
    "Carousel": {"init": "carousel_init", "func": "carousel_func"},
    "Wave": {"init": "wave_init", "func": "wave_func"},
    "Pulse": {"init": "pulse_init", "func": "pulse_func"},
    "Fade": {"init": "fade_init", "func": "fade_func"},
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
                "value_option_1",
                description="general value slider for text effects",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
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
                description="Font size as a percentage of the display height, fonts are unpredictable!",
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
        self.value_option_1 = self._config["value_option_1"]
        self.deep_diag = self._config["deep_diag"]
        self.use_gradient = self._config["use_gradient"]
        # putting text_color into a list so that it can be treated the same as a gradient list
        self.text_color = [parse_color(self._config["text_color"])]
        self.resize_method = RESIZE_METHOD_MAPPING[
            self._config["resize_method"]
        ]
        self.multiplier = self._config["multiplier"]
        self.text_effect_funcs = TEXT_EFFECT_MAPPING[
            self._config["text_effect"]
        ]

        self.lows_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99
        )

        self.mids_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99
        )

        self.high_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99
        )

        self.lows_impulse = 0
        self.mids_impulse = 0
        self.high_impulse = 0

        self.values = deque(maxlen=1024)
        self.values2 = deque(maxlen=1024)

    def del_words(self, count):
        _LOGGER.info(f"del words: count {count}")
        _LOGGER.info(f"existing wordblocks: {self.sentence.wordcount}")

    def add_words(self, words, clear=False):
        _LOGGER.info(f"add words: {words}")
        _LOGGER.info(f"clear: {clear}")
        _LOGGER.info(f"existing wordblocks: {self.sentence.wordcount}")

    def focus_words(self, index):
        _LOGGER.info(f"focus words: {index}")
        _LOGGER.info(f"existing wordblocks: {self.sentence.wordcount}")
        if index > self.sentence.wordcount:
            error = f"focus index {index} out of range {self.sentence.wordcount}"
            _LOGGER.warning(error)
            return error
        if not self.sentence.word_focus_active:
            error = f"word focus not active in {self._config["text_effect"]}"
            return error
        self.sentence.word_focused_on = index
        self.sentence.word_focus = 0

    def do_once(self):
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        self.sentence = Sentence(
            self.config["text"],
            self.config["font"],
            round(self.r_height * self.config["height_percent"] / 100),
            (self.r_width, self.r_height),
        )
        if self.deep_diag:
            self.overlay = Overlay(self.r_height, self.r_width)

        getattr(self, self.text_effect_funcs["init"])()

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

        self.lows_impulse = self.lows_impulse_filter.update(
            data.lows_power(filtered=False)
        )
        self.mids_impulse = self.mids_impulse_filter.update(
            data.mids_power(filtered=False)
        )
        self.high_impulse = self.high_impulse_filter.update(
            data.high_power(filtered=False)
        )

    #        _LOGGER.info(f"lows: {self.lows_impulse:3.3f} mids: {self.mids_impulse:3.3f} high: {self.high_impulse:3.3f}")

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        if self.use_gradient:
            color_array = self.get_gradient_color_vectorized1d(
                self.sentence.color_points
            ).astype(np.uint8)
        else:
            color_array = self.text_color

        self.impulses3 = [
            self.lows_impulse,
            self.mids_impulse,
            self.high_impulse,
        ]
        self.impulses = interpolate_to_length(
            self.impulses3,
            self.sentence.wordcount,
        )

        getattr(self, self.text_effect_funcs["func"])()

        self.sentence.update(self.passed)

        self.sentence.render(
            self.matrix,
            self.resize_method,
            color_array,
            values=self.values,
            values2=self.values2,
        )

        self.roll_gradient()

        if self.deep_diag:
            self.overlay.render(
                self.matrix,
                self.m_draw,
                values=self.values,
                values2=self.values2,
            )

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
            word.pose.set_vectors(offset, 0, 0, 1, 10000)
            word.pose.d_pos = (self.base_speed, 0.5)
            offset += word.w_width / 2
            offset += self.sentence.space_block.w_width

    def side_scroll_func(self):
        if (
            self.sentence.wordblocks[-1].pose.x
            + self.sentence.wordblocks[-1].w_width / 2
            < -1
        ):
            self.side_scroll_init()
        for word in self.sentence.wordblocks:
            if self.option_1:
                word.pose.d_pos = (
                    self.base_speed
                    + (self.lows_impulse * self.multiplier * self.base_speed),
                    0.5,
                )
            if self.alpha:
                word.pose.alpha = min(
                    1.0, 0.1 + self.lows_impulse * self.multiplier
                )

        # _LOGGER.info(f"{self.sentence.wordblocks[0].pose.y:3.3f})")

    ############################################################################
    # carousel
    #
    # this will be the sentence distributed around a circle that can be tilted
    # The circle size will be based on the sentence length and text size and
    # often significantly off screen.
    # The word in focus will be at size 1.0 all others will be at some reduced factor
    # The word in focus will be drawn last to attempt to preserve some z order,
    # this might need a new machinsim in render
    # Value slider will allow the tilting of the carosel
    #
    ############################################################################

    def carousel_init(self):
        self.wave_init()

    def carousel_func(self):
        self.wave_func()

    ############################################################################
    # wave
    #
    # this is more of a default effect for testing primitives at this point
    ############################################################################

    def wave_init(self):
        # _LOGGER.info(f"wave_init: {self.sentence.text} {self.passed}")
        # wave is the temp home for any old spam effect
        offset = 2 / (self.sentence.wordcount + 5)
        for idx, word in enumerate(self.sentence.wordblocks):
            word.pose.set_vectors(
                -1 + (idx + 3) * offset, -1 + (idx + 3) * offset, 0, 1, 10
            )
            word.pose.d_pos = (0.2, 1 / self.sentence.wordcount * idx)
            word.pose.lefty_righty = 1 if idx % 2 == 0 else -1

    def wave_func(self):
        # _LOGGER.info(f"wave_func: {self.sentence.text} {self.passed}")
        for idx, word in enumerate(self.sentence.wordblocks):
            word.pose.d_rotation = (
                self.impulses[idx] * self.multiplier * word.pose.lefty_righty
            )

            word.pose.size = 0.3 + self.impulses[idx] * self.multiplier
            if self.alpha:
                word.pose.alpha = min(
                    1.0, 0.1 + self.impulses[idx] * self.multiplier
                )
            if word.pose.life <= 0:
                word.pose.life = 10
                word.pose.d_pos = (-word.pose.d_pos[0], word.pose.d_pos[1])

    ############################################################################
    # spokes
    ############################################################################

    # A spoke based effect with the word index dictacting how far
    # round the circle to calculate base positions
    # each base posiiton will be calculated from scratch every frame allowing
    # rotation of the overall spokes to be applied, its an alternative way to
    # deal with animation of positions other than deltas
    # work rotation will still be delta based
    # base positions will be mapped every third to lows, mids, highs, for word
    # size and radius

    # option 1 switch, flip flop rotation directions
    # value option 1, will be used to set the number of seconds a words stays in focus until we have a mechanic for that

    def spokes_init(self):
        self.spoke_spin = 0
        self.spokes = np.linspace(0, 2 * math.pi, self.sentence.wordcount + 1)[
            :-1
        ]

        for idx, word in enumerate(self.sentence.wordblocks):
            # random seed angle between 0 and 1 so words dan't artificially line up in spin space
            word.pose.ang = random.random()

        # set up word focus basics
        self.sentence.word_focus_active = True
        self.sentence.word_focused_on = 0
        self.sentence.word_focus = 0
        # this should set how long it takes word_focus to get from 0 to 1
        self.sentence.d_word_focus = 1 / (max(0.01, self.value_option_1) * 5)

    def spokes_func(self):
        self.spoke_spin += self.lows_impulse * self.multiplier * 0.01
        self.spoke_spin %= 2 * np.pi
        for idx, word in enumerate(self.sentence.wordblocks):
            impulse = self.impulses3[idx % 3] * self.multiplier
            if self.option_1 and idx % 2 == 0:
                spoke_spin = -self.spoke_spin
                word.pose.d_rotation = -impulse
            else:
                spoke_spin = self.spoke_spin
                word.pose.d_rotation = impulse
            angle = self.spokes[idx] + spoke_spin
            word.pose.x = math.cos(angle) * (1 * impulse + 0.3)
            word.pose.y = math.sin(angle) * (1 * impulse + 0.3)
            word.pose.life = 1
            word.pose.size = 0.3 + impulse
            if self.alpha:
                word.pose.alpha = min(1.0, 0.1 + impulse)

        # when a word goes into focus we can use the life counter to control its migration in and out of the center
        # twean the new calculated value to the center values in some manner
        # TODO: consider overriding color for word in focus, expensive

        focus_word = self.sentence.wordblocks[self.sentence.word_focused_on]
        if self.sentence.word_focus < 0.2:
            transition = 5 * self.sentence.word_focus
        elif self.sentence.word_focus > 0.8:
            transition = 5 * (1 - self.sentence.word_focus)
        else:
            transition = 1

        # _LOGGER.info(f"focus_word: {self.sentence.word_focused_on} text ({focus_word.text}) {self.sentence.word_focus:3.3f} transition: {transition:3.3f}")

        focus_word.pose.size = tween(
            focus_word.pose.size,
            0.8 + (self.lows_impulse * self.multiplier / 2),
            transition,
        )
        focus_word.pose.x = tween(focus_word.pose.x, 0, transition)
        focus_word.pose.y = tween(focus_word.pose.y, 0, transition)
        focus_word.pose.ang = tween(focus_word.pose.ang, 0, transition)
        focus_word.pose.d_rotation = tween(
            focus_word.pose.d_rotation, 0, transition
        )
        focus_word.pose.alpha = tween(focus_word.pose.alpha, 1.0, transition)

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
