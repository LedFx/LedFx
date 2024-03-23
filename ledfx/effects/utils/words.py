import logging
import os
import math
import numpy as np

from PIL import Image, ImageDraw, ImageFont
from ledfx.color import parse_color
from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.effects.utils.pose import (
    Pose,
    biased_round,
)

_LOGGER = logging.getLogger(__name__)

FONT_MAPPINGS = {
    "Roboto Regular": os.path.join(
        LEDFX_ASSETS_PATH, "fonts", "Roboto-Regular.ttf"
    ),
    "Roboto Bold": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Roboto-Bold.ttf"),
    "Roboto Black": os.path.join(
        LEDFX_ASSETS_PATH, "fonts", "Roboto-Black.ttf"
    ),
    "Stop": os.path.join(LEDFX_ASSETS_PATH, "fonts", "Stop.ttf"),
    "Technique": os.path.join(LEDFX_ASSETS_PATH, "fonts", "technique.ttf"),
    "8bitOperatorPlus8": os.path.join(
        LEDFX_ASSETS_PATH, "fonts", "8bitOperatorPlus8-Regular.ttf"
    ),
    "Press Start 2P": os.path.join(
        LEDFX_ASSETS_PATH, "fonts", "PressStart2P.ttf"
    ),
}


class Textblock:
    # this class is intended to establish a pillow image object with rendered text within it
    # text will be created from the passed font at the requested size
    # the pillow image will have an alpha channel, and will always be transparent
    # the text will be rendered in the color requested
    # the text will be centered in the image which is only big enough to contain the text
    # the Textblock instance will be merged into the main display image outside of this class
    # so TextBlock has no idea of position which will be handled externally to this class

    def __init__(self, text, font, disp_size, color="white"):
        self.text = text
        self.color = color
        self.ascent, self.descent = font.getmetrics()
        dummy_image = Image.new("L", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_image)
        left, top, right, bottom = dummy_draw.textbbox((0, 0), text, font=font)
        self.width = right - left
        self.height = self.descent + self.ascent
        self.w_width = self.width / (disp_size[0] / 2)
        self.w_height = self.height / (disp_size[0] / 2)
        self.h_width = self.width / (disp_size[1] / 2)
        self.h_height = self.height / (disp_size[1] / 2)

        # word images are greyscale masks only
        self.image = Image.new("L", (self.width, self.height))  # , "grey")
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

        rotated_width = (
            self.image.height * sin_angle + self.image.width * cos_angle
        )
        rotated_height = (
            self.image.height * cos_angle + self.image.width * sin_angle
        )

        final_width = max(1, round(rotated_width * self.pose.size))
        final_height = max(1, round(rotated_height * self.pose.size))

        return final_width, final_height

    def render(
        self, target, resize_method, color=None, values=None, values2=None
    ):
        if (
            self.pose.life > 0
            and self.pose.alpha > 0.0
            and self.pose.size > 0.0
        ):
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
                resized = self.image.rotate(
                    self.pose.ang * 360, expand=True, resample=resize_method
                )
                resized = resized.resize(
                    (
                        max(1, round(resized.width * self.pose.size)),
                        max(1, round(resized.height * self.pose.size)),
                    ),
                    resample=resize_method,
                )
                # self.pos is a scalar for x and y in the range -1 to 1
                # the pos position is for the center of the image
                # here we will convert it to a pixel position within target which is a PIL image object

                # biased rounding is an accepted technique to bump values off
                # the rounding cusp and to avoid unwanted glitches visible to
                # the end user this prevents text jumping up a line
                # unexpoectedly it does just move the issue, but FAR less likely
                # to express
                x = biased_round(
                    ((pose_x + 1) * half_width) - (resized.width / 2)
                )
                y = biased_round(
                    ((pose_y + 1) * half_height) - (resized.height / 2)
                )

                # _LOGGER.info(
                #     f"Textblock {self.text} x: {self.pose.x:3.3f} y: {self.pose.y:3.3f} {x} {y} ang: {self.pose.ang:3.3f} size: {self.pose.size:3.3f}")

                capped_alpha = min(1.0, max(0.0, self.pose.alpha))
                if capped_alpha < 1.0:
                    img_array = np.array(resized)
                    modified_array = np.clip(
                        img_array * capped_alpha, 0, 255
                    ).astype(np.uint8)
                    resized = Image.fromarray(modified_array, mode="L")

                if color is not None:
                    color_img = Image.new("RGBA", resized.size, color)
                    r, g, b, a = color_img.split()
                    resized = Image.merge("RGBA", (r, g, b, resized))
                target.paste(resized, (x, y), resized)


class Sentence:
    # this class will construct and maintain a set of words,
    # spaces and animated dynamics for a sentence

    def __init__(self, text, font_name, points, disp_size):
        self.text = text
        self.font_path = FONT_MAPPINGS[font_name]
        self.points = points
        self.start_color = parse_color("white")
        self.font = ImageFont.truetype(self.font_path, self.points)
        self.wordblocks = []

        for word in self.text.split():
            wordblock = Textblock(word, self.font, disp_size)
            self.wordblocks.append(wordblock)
            _LOGGER.debug(f"Wordblock {word} created")
        self.space_block = Textblock(" ", self.font, disp_size)
        self.wordcount = len(self.wordblocks)
        self.color_points = np.array(
            [idx / max(1, self.wordcount - 1) for idx in range(self.wordcount)]
        )

        self.word_focus_active = False
        self.word_focus = -1
        self.word_focused_on = -1
        self.d_word_focus = 1
        self.word_focus_callback = None

    def update(self, dt):
        if self.word_focus_active:
            # allow this to go out of range for theshold testing elsewhere
            # clip at point of application
            self.word_focus += self.d_word_focus * dt
            # TODO: where should this callback be called?
            # at word or sentence level, what should we allow it to do?
            # update or render level?
            if self.word_focus >= 1.0:
                # move onto next word and restart counters
                self.word_focused_on = (
                    self.word_focused_on + 1
                ) % self.wordcount
                self.word_focus %= 1.0

        for word in self.wordblocks:
            word.update(dt)

    def render(self, target, resize_method, color, values=None, values2=None):
        color_len = len(color)

        # TODO: allow focus color override

        for i, word in enumerate(self.wordblocks):
            if self.word_focus_active and i == self.word_focused_on:
                focus_color = tuple(color[i % color_len])
            else:
                word.render(
                    target,
                    resize_method,
                    tuple(color[i % color_len]),
                    values,
                    values2,
                )

        # draw the focus word last
        if self.word_focus_active:
            self.wordblocks[self.word_focused_on].render(
                target,
                resize_method,
                focus_color,
                values,
                values2,
            )
