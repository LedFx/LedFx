import logging
import random

import numpy as np
import voluptuous as vol

from ledfx.color import validate_gradient
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Line:
    """
    The Line class represents a line in the digital rain effect.

    Attributes:
        nx (float): The normalized x-coordinate of the line.
        ny (float): The normalized y-coordinate of the line.
        color (nparray): The color of the line in RGB format
        speed (float): speed modifier from normal
        tail (float): The length of the line's tail.
        offset (float): The offset of the beat pulse
        impulse_index (int): The index into the bass, mid, high array.

    Methods:
        update(run_seconds: float, passed: float, tail: float, impulse: list): Updates the line's position.
        draw(draw, image, width, beat_osc): Draws the line on the image.
    """

    def __init__(
        self, nx, color, offset, speed, fade_multipliers, line_width, segment
    ):
        self.nx = nx
        self.ny = 0
        self.color = color
        # per line modifyer on speed, norm 1.0
        self.speed = speed
        self.tail = 0.5
        self.offset = offset
        self.impulse_index = int(offset * 3)
        self.fade_multipliers = fade_multipliers
        self.num_segments = len(fade_multipliers)
        self.line_width = line_width
        self.segment = segment

    def update(self, run_seconds, passed, tail, impulse):
        ###
        # Update the line's position
        #
        # Args:
        #   run_seconds (float): The number of seconds for a line to run from top to bottom.
        #   passed (float): The number of seconds since the last update.
        #   tail (float): The length of the line's tail.
        #   impulse (list): The impulse array from the audio data.
        #
        # Returns:
        #   bool: True if the line is still visible, False otherwise.
        ###

        # calculate how much to move
        movement = passed / run_seconds * (1 + impulse[self.impulse_index])
        self.tail = tail
        # adjust for the code lines own speed
        self.ny += movement * self.speed
        if self.ny > (1 + self.tail):
            return False
        return True

    def draw(self, draw, image, beat_osc):
        ###
        # Draw the line on the image
        #
        # Args:
        #   draw: The ImageDraw object to draw on.
        #   image: The image to draw on.
        #   beat_osc: The beat oscillator value.
        ###

        x = int(self.nx * image.width)
        y = int(self.ny * image.height)

        # Only render tail if segment > 0 (guards against degenerate geometry)
        if self.segment > 0:
            for i in range(self.num_segments):
                y_start = int(y - (self.line_width - 1) - self.segment * i)
                y_end = int(y_start - self.segment)

                # Use pre-calculated fade and convert once
                faded_color = (self.color * self.fade_multipliers[i]).astype(
                    np.uint8
                )

                draw.line(
                    (x, y_start, x, y_end),
                    width=self.line_width,
                    fill=tuple(faded_color),
                )

        beat_roll = beat_osc + self.offset
        beat_roll = beat_roll - np.floor(beat_roll)

        # Pre-calculate white color with beat
        head_color = (
            np.array([255, 255, 255], dtype=np.float32)
            * (0.5 + beat_roll * 0.5)
        ).astype(np.uint8)

        draw.line(
            (x, int(y), x, int(y - (self.line_width - 1))),
            width=self.line_width,
            fill=tuple(head_color),
        )


class DigitalRain2d(Twod, GradientEffect):
    NAME = "Digital Rain"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + ["tail_segments", "impulse_decay"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "gradient",
                description="Color gradient to display",
                default="linear-gradient(90deg, rgb(0, 199, 140) 0%, rgb(0, 255, 50) 100%)",
            ): validate_gradient,
            vol.Optional(
                "count",
                description="Number of code lines in the matrix as a multiplier of matrix pixel width",
                default=1.9,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=4.0)),
            vol.Optional(
                "add_speed",
                description="Number of code lines to add per second",
                default=30.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=30.0)),
            vol.Optional(
                "width",
                description="Width of code lines as % of matrix",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Optional(
                "run_seconds",
                description="Minimum number of seconds for a code line to run from top to bottom",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=1, max=10.0)),
            vol.Optional(
                "tail",
                description="Code line tail length as a % of the matrix",
                default=67,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional(
                "tail_segments",
                description="Number of tail segments",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=30)),
            vol.Optional(
                "impulse_decay",
                description="Decay filter applied to the impulse for development",
                default=0.01,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "multiplier",
                description="audio injection multiplier, 0 is none",
                default=10,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0
        self.lines = []
        self.beat_osc = 0.0
        self.impulse = [0, 0, 0]

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.add_speed = self._config["add_speed"]
        self.last_added = 0.0
        self.width = self._config["width"]
        self.run_seconds = self._config["run_seconds"]
        self.tail = self._config["tail"] / 100.0
        self.multiplier = self._config["multiplier"]

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

    def do_once(self):
        super().do_once()
        self.count = max(1, int(self._config["count"] * self.r_width))
        # Pre-calculate fade multipliers for line tail segments based on config
        num_segments = max(2, self._config["tail_segments"])
        self.fade_multipliers = np.array(
            [1.0 - i / (num_segments - 1) for i in range(num_segments)]
        )

        # Pre-calculate line geometry based on current dimensions
        self.line_width = max(
            1, int(self.r_width * (self._config["width"] / 100.0))
        )
        tail_length = int(self.r_height * (self._config["tail"] / 100.0))
        self.tail_pixels = tail_length - self.line_width

        # Calculate segment size for tail rendering (guard against degenerate geometry)
        if self.tail_pixels > 0:
            self.segment = self.tail_pixels / num_segments
        else:
            self.segment = 0  # Skip tail rendering when tail is too short

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.beat_osc = data.beat_oscillator()

        self.lows_impulse = self.lows_impulse_filter.update(
            data.lows_power(filtered=False) * self.multiplier
        )
        self.mids_impulse = self.mids_impulse_filter.update(
            data.mids_power(filtered=False) * self.multiplier
        )
        self.high_impulse = self.high_impulse_filter.update(
            data.high_power(filtered=False) * self.multiplier
        )
        self.impulse = [
            self.lows_impulse,
            self.mids_impulse,
            self.high_impulse,
        ]

    def add_line(self):
        ###
        # Add a new code line to the matrix
        # let off screen deal with line removal
        ###

        if len(self.lines) < self.count:
            line_random = random.random()
            color = self.get_gradient_color(line_random)
            self.lines.append(
                Line(
                    random.random(),
                    color,
                    line_random,
                    0.1 + line_random * 0.9,
                    self.fade_multipliers,
                    self.line_width,
                    self.segment,
                )
            )

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        self.last_added += self.passed
        while self.last_added >= 1.0 / self.add_speed:
            self.last_added -= 1.0 / self.add_speed
            self.add_line()

        # Filter out dead lines in one pass instead of removing during iteration
        self.lines = [
            line
            for line in self.lines
            if line.update(
                self.run_seconds, self.passed, self.tail, self.impulse
            )
        ]

        # Draw all remaining lines
        for line in self.lines:
            line.draw(self.m_draw, self.matrix, self.beat_osc)
