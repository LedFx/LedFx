import queue
import time
from typing import ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color, Gradient
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class Strobe(AudioReactiveEffect, GradientEffect):
    NAME = "Strobe"
    CATEGORY = "Classic"
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]

    class Config(GradientEffect.Config):
        gradient: Gradient = Field(
            "Dancefloor", description="Color scheme for bass strobe to cycle through"
        )
        color_step: CoercedFloat = Field(
            0.0625, description="Amount of color change per bass strobe", ge=0, le=0.25
        )
        bass_strobe_decay_rate: CoercedFloat = Field(
            0.5,
            description="Bass strobe decay rate. Higher -> decays faster.",
            ge=0,
            le=1,
        )
        strobe_color: Color = Field(
            "#FFFFFF", description="color for percussive strobes"
        )
        strobe_width: CoercedInt = Field(
            10, description="Percussive strobe width, in pixels", ge=0, le=1000
        )
        strobe_decay_rate: CoercedFloat = Field(
            0.5,
            description="Percussive strobe decay rate. Higher -> decays faster.",
            ge=0,
            le=1,
        )
        color_shift_delay: CoercedFloat = Field(
            1,
            description="color shift delay for percussive strobes. Lower -> more shifts",
            ge=0,
            le=1,
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.onsets_queue = queue.Queue()

    def on_activate(self, pixel_count):
        self.strobe_overlay = np.zeros(np.shape(self.pixels))
        self.bass_strobe_overlay = np.zeros(np.shape(self.pixels))
        self.onsets_queue = queue.Queue()

    def config_updated(self, config):
        self.color_shift_step = self.config.color_step

        self.strobe_color = np.array(parse_color(self.config.strobe_color), dtype=float)
        self.last_color_shift_time = 0
        self.strobe_width = self.config.strobe_width
        self.color_shift_delay_in_seconds = self.config.color_shift_delay
        self.color_idx = 0

        self.last_strobe_time = 0
        self.strobe_wait_time = 0
        self.strobe_decay_rate = 1 - self.config.strobe_decay_rate

        self.last_bass_strobe_time = 0
        self.bass_strobe_wait_time = 0.2
        self.bass_strobe_decay_rate = 1 - self.config.bass_strobe_decay_rate

    def render(self):
        pixels = np.copy(self.bass_strobe_overlay)

        # Sometimes we lose the queue? No idea why. This should ensure it doesn't happen
        if self.onsets_queue is None:
            self.onsets_queue = queue.Queue()

        if not self.onsets_queue.empty():
            self.onsets_queue.get()
            strobe_width = min(self.strobe_width, self.pixel_count)
            length_diff = self.pixel_count - strobe_width
            position = (
                0
                if length_diff == 0
                else np.random.randint(self.pixel_count - strobe_width)
            )
            self.strobe_overlay[position : position + strobe_width] = self.strobe_color

        pixels += self.strobe_overlay

        self.strobe_overlay *= self.strobe_decay_rate
        self.bass_strobe_overlay *= self.bass_strobe_decay_rate
        self.pixels = pixels

    def audio_data_updated(self, data):
        currentTime = time.time()

        if currentTime - self.last_color_shift_time > self.color_shift_delay_in_seconds:
            self.color_idx += self.color_shift_step
            self.color_idx = self.color_idx % 1
            self.bass_strobe_color = self.get_gradient_color(self.color_idx)
            self.last_color_shift_time = currentTime

        if (
            data.volume_beat_now()
            and currentTime - self.last_bass_strobe_time > self.bass_strobe_wait_time
            and self.bass_strobe_decay_rate
        ):
            self.bass_strobe_overlay = np.tile(
                self.bass_strobe_color, (self.pixel_count, 1)
            )
            self.last_bass_strobe_time = currentTime

        if data.onset() and currentTime - self.last_strobe_time > self.strobe_wait_time:
            self.onsets_queue.put(True)
            self.last_strobe_time = currentTime
