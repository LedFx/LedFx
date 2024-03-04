import logging
import os
from enum import Enum

import voluptuous as vol

from ledfx.utils import get_mono_font
from ledfx.effects.twod import Twod
from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.color import parse_color, validate_color
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

class Mode(Enum):
    HOLD = 1
    BOUNCE = 2
    HARD_ZERO = 3
    DECELERATE = 4


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

class Scalar():
    def __init__(self, val, delta, target, target_2, mode):
        self.val = val
        self.delta = delta
        self.target = target
        self.target_2 = target_2
        self.mode = mode

    def update(self, passed_time):
        self.val += self.delta * passed_time
        if self.delta > 0:
            self.val = min(self.val, self.target)
        else:
            self.val = max(self.val, self.target)
        if self.val == self.target:
            if self.mode == Mode.HOLD:
                self.delta = 0
            elif self.mode == Mode.BOUNCE:
                self.delta = -self.delta
                self.target, self.target_2 = self.target_2, self.target
            elif self.mode == Mode.HARD_ZERO:
                self.delta = 0
                self.val = 0
            elif self.mode == Mode.DECELERATE:
                self.delta = self.delta * 0.5

class Pose():
    # we need a class to represent a 2d pose and all of its dynamics
    # this class will be used to represent
    #  life of the active render and manipulation of the pose in seconds
    # vector values all of the range -1 to 1
    #  pos (x,y), ang and size
    # vector values of the range of 0 to 1\
    #  alpha the blend alpha of the related object
    # delta values of increase in vector values over time on a second unit
    #  d_pos in a vector of direction and value per sec
    #  d_rotation as a value per sec
    #  d_size as a value per sec
    #  d_alpha as a value per sec
    # limit values of vector values and what happens when they ge there
    #  position, rotation and size, alpha
    # modifiers to the delta values over time
    #  m_pos accel dec linear and angular
    #  m_rotation rate of change of d_rotation
    #  m_size rate of change of d_size
    #  m_alpha rate of change of d_alpha

    # we will start with an init class that just create the vector values
    # all other deltas and modifiers will be added later, this will allow incremental implementation

    def __init__(self, x, y, ang, size, life, alpha = 1.0):
        self.x = x
        self.y = y
        self.ang = ang
        self.size = size
        self.life = life
        self.alpha = alpha

        self.d_pos = None
        self.d_rotation = 0
        self.d_size = None
        self.m_pos = None
        self.m_rotation = None
        self.m_size = None
        self.limit_pos = None
        self.limit_rotation = None
        self.limit_size = None

    def set_vectors(self, x, y, ang, size, life, alpha = 1.0):
        self.x = x
        self.y = y
        self.ang = ang
        self.size = size
        self.life = life
        self.alpha = alpha

    def set_deltas(self, d_pos, d_rotation, d_size):
        self.d_pos = d_pos
        self.d_rotation = d_rotation
        self.d_size = d_size

    def update(self, passed_time):
        self.life -= passed_time
        if self.life <= 0.0:
            return False

        self.ang = (((self.ang + 1 )+ self.d_rotation * passed_time ) % 2 ) - 1
        return True

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
        dummy_image = Image.new('RGB', (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_image)
        left, top, right, bottom = dummy_draw.textbbox((0,0), text, font=font)
        self.width = right - left
        self.height = self.descent + self.ascent
        self.image = Image.new('RGBA', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((0, 0), self.text, font=font, fill=color)
        self.pose = Pose(0, 0, 0, 1, 0, 1)
        # self.image.show()


    def update(self, passed_time):
        active = self.pose.update(passed_time)
        return active

    def render(self, target, resize_method, values, values2):
        if self.pose.life > 0 and self.pose.x == 0.0:
            # first we will rotate and then size the image
            # ang is a rotation from 0 to 1 float to represent 0 to 360 degrees
            # size is a float from 0 to 1 to represent 0 to 100% size
            resized = self.image.rotate(self.pose.ang * 360, expand=True, resample=resize_method)
            resized = resized.resize((int(resized.width * self.pose.size), int(resized.height * self.pose.size)), resample=resize_method)
            # self.pos is a scalar for x and y in the range -1 to 1
            # the pos position is for the center of the image
            # here we will convert it to a pixel position within target which is a PIL image object
            x = int(((self.pose.x + 1) * target.width / 2) - (resized.width / 2))
            y = int(((self.pose.y + 1) * target.height / 2) - (resized.height / 2))
            if self.pose.x == 0.0:
                _LOGGER.info(
                    f"Textblock {self.text} x: {self.pose.x:3.3f} y: {self.pose.y:3.3f} {x} {y} ang: {self.pose.ang:3.3f} size: {self.pose.size:3.3f}")
                values.append(x)
                values2.append(y)

            target.paste(resized, (x, y), resized)


class Sentence():
    # this class will construct and maintain a set of words,
    # spaces and animated dynamics for a sentence

    ANIMATIONS = {
        "SIDE_SCROLL"
    }

    def __init__(self, text, font_name, points, start_color='white'):
        self.text = text
        self.font_path = FONT_MAPPINGS[font_name]
        self.points = points
        self.start_color = parse_color(start_color)
        self.font = ImageFont.truetype(self.font_path, self.points)
        self.wordblocks = []

        for word in self.text.split():
            wordblock = Textblock(word,
                             self.font,
                             self.start_color)
            self.wordblocks.append(wordblock)
            _LOGGER.info(f"Wordblock {word} created")
            if DEBUG:
                wordblock.image.show()
        space_block = Textblock(" ",
                                self.font)
        self.space_width = space_block.width
        _LOGGER.info(f"Space width is {self.space_width}")

        offset = 2 / len(self.wordblocks)
        for idx, word in enumerate(self.wordblocks):
            word.pose.set_vectors(-1 + idx * offset, -1 + idx * offset,
                                  -1 + idx * offset, 1, 10000 )
            word.pose.d_rotation = 0.1

    def update(self, passed_time):
        for word in self.wordblocks:
            word.update(passed_time)

    def render(self, target, resize_method, values, values2):
        for word in self.wordblocks:
            word.render(target, resize_method, values, values2)

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
        },
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["a_switch"]
        self.deep_diag = self._config["deep_diag"]
        self.resize_method = RESIZE_METHOD_MAPPING[self._config["resize_method"]]

        if self.deep_diag:
            self.diag_font = get_mono_font(10)
            self.values = deque(maxlen=1024)
            self.values2 = deque(maxlen=1024)

    def do_once(self):
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        self.sentence = Sentence(self.config["text"],
                                 self.config["font"],
                                 int(self.r_height * self.config["height_percent"] / 100),
                                 self.config["text_color"])

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

    def plot_range(self, values, color):
        diag_string = "None"
        if len(values) > 1:

            graph_s = 9  # start pixel height under the diag text
            graph_h = max(1, self.r_height - 9 - 1 ) # height of graph
            v_min = min(values)
            v_max = max(values)
            if v_max == v_min:
                v_min = min(0, v_min)
                v_max = max(0, v_max)
            v_range = v_max - v_min
            x = 0
            pixels = self.matrix.load()
            for value in reversed(self.values):
                value_norm = (value - v_min) / v_range
                y = graph_s + graph_h - (value_norm * graph_h)
                if y < self.matrix.height:
                    if value == 0:
                        pixels[x, y] = (0,0, 255)
                    else:
                        pixels[x, y] = color
                x += 1
                if x >= self.matrix.width:
                    break

            diag_string = f"{values[-1]} {v_min} {v_max} {v_range}"
        return diag_string


    def overlay(self, values, values2=None):
        diag_string = self.plot_range(values, (0, 255, 0))
        self.plot_range(values2, (255, 0, 0))
        self.m_draw.text((0, 0), diag_string, fill='yellow', font=self.diag_font)

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        self.sentence.update(self.passed)
        self.sentence.render(self.matrix, self.resize_method, self.values, self.values2)

        if self.deep_diag:
            self.overlay(self.values, self.values2)
