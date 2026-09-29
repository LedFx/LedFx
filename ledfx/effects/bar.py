from typing import ClassVar, Literal

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BarAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Bar"
    CATEGORY = "BPM"
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]

    class Config(GradientEffect.Config):
        mode: Literal["bounce", "wipe", "in-out"] = Field(
            "wipe", description="Choose from different animations"
        )
        ease_method: Literal["ease_in_out", "ease_in", "ease_out", "linear"] = Field(
            "ease_out", description="Acceleration profile of bar"
        )
        color_step: CoercedFloat = Field(
            0.125, description="Amount of color change per beat", ge=0.0625, le=0.5
        )
        beat_skip: Literal["none", "odds", "even"] = Field(
            "none", description="Skips odd or even beats"
        )
        beat_offset: CoercedFloat = Field(
            0, description="Offset the beat", ge=0.0, le=1.0
        )
        # if add 4, to skip every bar, a bit of extra work is required in audio.py
        skip_every: Literal[1, 2] = Field(
            1, description="If skipping beats, skip every"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.beat_oscillator = 0
        self.phase = 0
        self.color_idx = 0
        self.bar_len = 0.3
        self.beat_count = 0
        self.last_beat = 0.0

    def audio_data_updated(self, data):
        # Run linear beat oscillator through easing method
        self.beat_oscillator = data.beat_oscillator()
        self.beat_oscillator = (self.beat_oscillator + self.config.beat_offset) % 1.0
        self.beat_count = data.beat_counter

        # color change and phase
        if self.last_beat > 0.2 and self.beat_oscillator < 0.1:
            self.phase = 1 - self.phase  # flip flop 0->1, 1->0
            if self.phase == 0:
                # 8 colors, 4 beats to a bar
                self.color_idx += self.config.color_step
                self.color_idx = self.color_idx % 1  # loop back to zero

        self.last_beat = self.beat_oscillator

    def render(self):
        if self.config.ease_method == "ease_in_out":
            x = 0.5 * np.sin(np.pi * (self.beat_oscillator - 0.5)) + 0.5
        elif self.config.ease_method == "ease_in":
            x = self.beat_oscillator**2
        elif self.config.ease_method == "ease_out":
            x = -((self.beat_oscillator - 1) ** 2) + 1
        elif self.config.ease_method == "linear":
            x = self.beat_oscillator

        # Compute position of bar start and stop
        if self.config.mode == "wipe":
            if self.phase == 0:
                bar_end = x
                bar_start = 0
            elif self.phase == 1:
                bar_end = 1
                bar_start = x

        elif self.config.mode == "bounce":
            x = x * (1 - self.bar_len)
            if self.phase == 0:
                bar_end = x + self.bar_len
                bar_start = x
            elif self.phase == 1:
                bar_end = 1 - x
                bar_start = 1 - (x + self.bar_len)

        elif self.config.mode == "in-out":
            if self.phase == 0:
                bar_end = x
                bar_start = 0
            elif self.phase == 1:
                bar_end = 1 - x
                bar_start = 0

        # Construct the bar
        color = self.get_gradient_color(self.color_idx)
        if self.config.beat_skip != "none" and (
            (
                (self.beat_count == 0 or self.beat_count == 1)
                if (self.config.skip_every == 2)
                else not self.beat_count % 2
            )
            == (self.config.beat_skip == "even")
        ):
            color = np.array([0, 0, 0])

        self.pixels = np.zeros(np.shape(self.pixels))
        self.pixels[
            int(self.pixel_count * bar_start) : int(self.pixel_count * bar_end),
            :,
        ] = color
