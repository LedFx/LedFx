import logging
from typing import Annotated, ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect

_LOGGER = logging.getLogger(__name__)


def is_alive(thing):
    return thing.alive


class Sparkle:
    def __init__(self, now, pos, width, speed, die_off):
        self.pos = int(pos)
        self.width = int(width)
        self.speed = speed
        self.die_off = die_off
        self.born = now
        self.alive = True
        self.health = 1.0
        self.white = np.array(parse_color("white"), dtype=float)

    def age(self, now, frame_time, pixel_count):
        if now - self.born > self.die_off:
            self.alive = False
        self.health = 1 - ((now - self.born) / self.die_off)
        self.pos += self.speed * frame_time * self.health
        self.pos = self.pos % pixel_count
        self.pos = int(self.pos)

    def render(self, pixels, pixel_count):
        color = self.white * self.health
        pixels[self.pos : min(self.pos + self.width, pixel_count)] += color
        overflow = (self.pos + self.width) - pixel_count
        if overflow > 0:
            pixels[:overflow] += color


class ScanAndFlareAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Scan and Flare"
    CATEGORY = "Classic"
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]

    class Config(GradientEffect.Config):
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
        sparkles_max: CoercedInt = Field(
            10, description="max number of sparkles", ge=1, le=20
        )
        sparkles_size: CoercedFloat = Field(
            0.1, description="of scan size ", ge=0.01, le=0.3
        )
        sparkles_time: CoercedFloat = Field(
            1.0, description="secs to die off", ge=0.01, le=2
        )
        sparkles_threshold: CoercedFloat = Field(
            0.6, description="level to trigger", ge=0.1, le=0.9
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

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.scan_pos = 0.0
        self.returning = False
        self.bar = 0
        self.power = 0
        self.sparkles = []
        self.last_sparkle = 0

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self.config.background_color), dtype=float
        )
        self.power_func = self.POWER_FUNCS_MAPPING[self.config.frequency_range]
        self.color_scan_cache = np.array(
            parse_color(self.config.color_scan), dtype=float
        )
        self.color_scan = self.color_scan_cache

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.bar = self.power * self.config.multiplier

    def render(self):
        # setup colors
        if self.config.use_grad:
            gradient_pos = (self.scan_pos / self.pixel_count) % 1
            self.color_scan = self.get_gradient_color(gradient_pos)
        else:
            self.color_scan = self.color_scan_cache

        if self.config.color_intensity:
            self.color_scan = self.color_scan * min(1.0, self.power)

        step_per_sec = self.pixel_count / 100.0 * self.config.speed
        step_size = self.passed * step_per_sec

        step_size = step_size * self.bar

        scan_width_pixels = int(
            max(1, int(self.pixel_count / 100.0 * self.config.scan_width))
        )
        if self.returning:
            self.scan_pos -= step_size
        else:
            self.scan_pos += step_size

        if self.config.bounce:
            if self.scan_pos > self.pixel_count - scan_width_pixels:
                self.returning = True
            if self.scan_pos < 0:
                self.returning = False
        else:
            if self.scan_pos > self.pixel_count:
                self.scan_pos = 0.0
            if self.scan_pos < 0:
                self.returning = False

        # move and age any sparkles
        for sparkle in self.sparkles:
            sparkle.age(self.now, self.passed, self.pixel_count)

        self.sparkles = list(filter(is_alive, self.sparkles))

        pixel_pos = max(0, min(int(self.scan_pos), self.pixel_count))

        # add any new sparkles
        if (
            len(self.sparkles) < self.config.sparkles_max
            and self.power > self.config.sparkles_threshold * 2
        ):
            # cannot convince myself to limit sparkles per second
            # if now - self.last_sparkle > (1 / self.config.sparkles_max):
            sparkle_width = scan_width_pixels * self.config.sparkles_size
            if not self.returning:
                sparkle_pos = (pixel_pos - sparkle_width) % self.pixel_count
            else:
                sparkle_pos = (pixel_pos + scan_width_pixels) % self.pixel_count

            sparkle = Sparkle(
                self.now,
                sparkle_pos,
                sparkle_width,
                (0 - step_per_sec) if self.returning else step_per_sec,
                self.config.sparkles_time,
            )
            self.sparkles.append(sparkle)
            self.last_sparkle = self.now

        # this is the real render pass
        self.pixels[0 : self.pixel_count] = (
            self.background_color * self.config.background_brightness
        )
        self.pixels[
            pixel_pos : min(pixel_pos + scan_width_pixels, self.pixel_count)
        ] = self.color_scan

        if not self.config.bounce:
            overflow = (pixel_pos + scan_width_pixels) - self.pixel_count
            if overflow > 0:
                self.pixels[:overflow] = self.color_scan

        # render any sparkles
        for sparkles in self.sparkles:
            sparkles.render(self.pixels, self.pixel_count)
