import logging

import voluptuous as vol
import random
import numpy as np

from ledfx.effects.twod import Twod
from ledfx.effects.gradient import GradientEffect
from ledfx.color import validate_gradient

_LOGGER = logging.getLogger(__name__)

class Line():
    def __init__(self, nx, color, offset, speed):
        self.nx = nx
        self.ny = 0
        self.color = color
        # per line modifyer on speed, norm 1.0
        self.speed = speed
        self.tail = 0.5
        self.offset = offset
        self.impulse_index = int(offset * 3)

    def update(self, run_seconds, passed, tail, impulse):
        # calculate how much to move
        movement = passed / run_seconds * (1 + impulse[self.impulse_index])
        self.tail = tail
        # adjust for the code lines own speed
        self.ny += movement * self.speed
        if self.ny > (1 + self.tail):
            return False
        return True

    def draw(self, draw, image, width, beat_osc):
        x = int(self.nx * image.width)
        y = int(self.ny * image.height)
        line_width = max(1, int(image.width * (width / 100.0)))
        tail_length = int(image.height * self.tail)

        segment = (tail_length - line_width) / 10.0
        for i in range(10):
            y_start = y - (line_width - 1) - segment * i
            y_end = y_start - segment

            draw.line(
                (
                    x, y_start,
                    x, y_end
                ),
                width=line_width,
                fill= tuple((self.color * (1.0 - i * 0.09)).astype(int))
            )

        beat_roll = beat_osc + self.offset
        beat_roll = beat_roll - np.floor(beat_roll)

        draw.line(
            (
                x, y,
                x, y - (line_width - 1)
            ),
            width=line_width,
            fill=tuple((np.array([255, 255, 255]) * (0.5 + beat_roll * 0.5)).astype(int))
        )

class Matrix2d(Twod, GradientEffect):
    NAME = "Digital Rain"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["background_color", "gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

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
                default = 67,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
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
        self.impulse = [self.lows_impulse, self.mids_impulse, self.high_impulse]

    def add_line(self):
        # let off screen deal with line removal
        # only add here
        if len(self.lines) < self.count:
            line_random = random.random()
            color = self.get_gradient_color(line_random)
            self.lines.append(Line(random.random(),
                                   color,
                                   line_random,
                                   0.1 + line_random * 0.9))

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        self.last_added += self.passed
        while self.last_added >= 1.0 / self.add_speed:
            self.last_added -= 1.0 / self.add_speed
            self.add_line()

        # olderst lines are first which suits z order
        for line in self.lines[:]:
            if not line.update(self.run_seconds, self.passed, self.tail, self.impulse):
                self.lines.remove(line)
            line.draw(self.m_draw, self.matrix, self.width, self.beat_osc)

