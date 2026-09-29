from typing import Annotated

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.modulate import ModulateEffect


class ScanAudioEffect(AudioReactiveEffect, GradientEffect, ModulateEffect):
    NAME = "Scan"
    CATEGORY = "Classic"
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + [
        "count",
        "gradient_roll",
        "modulation_speed",
        "modulate",
        "modulation_effect",
        "full_grad",
    ]

    clear = np.array([0.0, 0.0, 0.0])

    class Config(GradientEffect.Config, ModulateEffect.Config):
        blur: CoercedFloat = Field(
            3.0, description="Amount to blur the effect", ge=0.0, le=10
        )
        mirror: bool = Field(False, description="Mirror the effect")
        bounce: bool = Field(True, description="bounce the scan")
        scan_width: CoercedInt = Field(
            30, description="Width of scan eye in %", ge=1, le=100
        )
        speed: CoercedInt = Field(
            50, description="Scan base % per second", ge=0, le=100
        )
        color_scan: Color = Field("#FF0000", description="Color of scan")
        frequency_range: Annotated[
            str, OneOf(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys()))
        ] = Field(
            "Lows (beat+bass)", description="Frequency range for the beat detection"
        )
        multiplier: CoercedFloat = Field(
            3.0, description="Speed impact multiplier", ge=0.0, le=5.0
        )
        color_intensity: bool = Field(
            True, description="Adjust color intensity based on audio power"
        )
        use_grad: bool = Field(False, description="Use colors from gradient selector")
        full_grad: bool = Field(
            False, description="spread the gradient colors across the scan"
        )
        count: CoercedInt = Field(
            1, description="Number of scan to render", ge=1, le=10
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.scan_pos = 0.0
        self.returning = False
        self.bar = 0
        self.set_values()
        self.power = 0

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self.config.background_color), dtype=float
        )
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]
        self.color_scan_cache = np.array(
            parse_color(self.config.color_scan), dtype=float
        )
        self.color_scan = self.color_scan_cache
        self.set_values()
        self.color_intensity = self.config.color_intensity
        self.use_grad = self.config.use_grad
        self.multiplier = self.config.multiplier

    def set_values(self):
        if hasattr(self, "pixels"):  # protect against calling too early
            self.block = self.pixel_count / self.config.count
            self.step_per_sec = self.pixel_count / 100.0 * self.config.speed

            self.scan_width_pixels = int(
                max(1, int(self.block / 100.0 * self.config.scan_width))
            )

            self.bounce = self.config.bounce
            self.full_grad = self.config.full_grad
            self.blocks = []

            for idx in range(self.config.count):
                # a block is start, mid, end index
                self.blocks.append(
                    [
                        int(self.block * idx),
                        int(self.block * idx + self.scan_width_pixels),
                        int(self.block * idx + self.block),
                    ]
                )

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.bar = self.power * self.multiplier

        if self.use_grad:
            gradient_pos = (self.scan_pos / self.pixel_count) % 1
            self.color_scan = self.get_gradient_color(gradient_pos)
        else:
            self.color_scan = self.color_scan_cache

        if self.color_intensity:
            self.color_scan = self.color_scan * min(1.0, self.power)

    def render(self):
        # handle step offset for frame
        step_size = self.passed * self.step_per_sec * self.bar
        if self.returning:
            self.scan_pos -= step_size
        else:
            self.scan_pos += step_size

        # handle scroll modes and looping
        if self.bounce:
            if self.scan_pos > self.pixel_count - self.scan_width_pixels:
                self.returning = True
                self.scan_pos = self.pixel_count - self.scan_width_pixels
            if self.scan_pos < 0:
                self.returning = False
                self.scan_pos = 0
        else:
            if self.scan_pos > self.pixel_count:
                self.scan_pos %= self.pixel_count
            if self.scan_pos < 0:
                self.returning = False

        # Fill pixels to baseline
        if self.full_grad:
            pixels = self.apply_gradient(1)
            self.pixels = self.modulate(pixels)
        else:
            self.pixels = np.zeros(np.shape(self.pixels))

        # render blocks accordingly
        for block in self.blocks:
            if self.full_grad:
                mid_pos = int(block[1] + self.scan_pos)
                end_pos = int(block[2] + self.scan_pos)
                self.pixels[
                    min(mid_pos, self.pixel_count) : min(end_pos, self.pixel_count)
                ] = self.clear

                end_flow = end_pos - self.pixel_count
                if end_flow > 0:
                    mid_flow = max(0, mid_pos - self.pixel_count)
                    self.pixels[mid_flow:end_flow] = self.clear
            else:
                start_pos = int(block[0] + self.scan_pos)
                mid_pos = int(block[1] + self.scan_pos)

                self.pixels[
                    min(start_pos, self.pixel_count) : min(mid_pos, self.pixel_count)
                ] = self.color_scan

                mid_flow = mid_pos - self.pixel_count
                if mid_flow > 0:
                    start_flow = max(0, start_pos - self.pixel_count)
                    self.pixels[start_flow:mid_flow] = self.color_scan

        if self.full_grad and self.color_intensity:
            self.pixels *= min(1.0, self.power)
