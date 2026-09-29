import logging
import time
from typing import ClassVar

import numpy as np
import psutil
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.temporal import TemporalEffect
from ledfx.utils import Teleplot

_LOGGER = logging.getLogger(__name__)

# Pixels is a diagnositc effect to allow the confirmation of order of addressing
# of pixels in a strip.
# For very large displays set pixels to a higher value so more pixels are lit
# and progressed each step


class PixelsEffect(TemporalEffect):
    NAME = "Pixels"
    CATEGORY = "Diagnostic"
    HIDDEN_KEYS: ClassVar[list[str]] = [
        "speed",
        "background_brightness",
        "blur",
        "mirror",
    ]

    class Config(TemporalEffect.Config):
        speed: CoercedFloat = Field(20.0, description="Locked to 20 fps", ge=20, le=20)
        step_period: CoercedFloat = Field(
            1.0, description="Time between each pixel step to light up", ge=0.01, le=5.0
        )
        pixels: CoercedInt = Field(
            1, description="Number of pixels each step", ge=1, le=32
        )
        background_color: Color = Field("#000000", description="Background color")
        pixel_color: Color = Field("#FFFFFF", description="Pixel color to light up")
        build_up: bool = Field(False, description="Single or building pixels")
        color_blend: bool = Field(
            False, description="Restart effect on color change, for transitions"
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.last_cycle_time: float = 20
        self.current_pixel = 0
        self.start_time = self.now
        self.last_memory_log_time = 0

    def on_activate(self, pixel_count):
        self.current_pixel = 0
        self.last_cycle_time = 20

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self.config.background_color), dtype=float
        )
        self.pixel_color = np.array(parse_color(self.config.pixel_color), dtype=float)

    def effect_loop(self):
        pass_time = self.now - self.start_time
        cycle_time = pass_time % self.config.step_period

        if cycle_time < self.last_cycle_time:
            if self.current_pixel == 0 or not self.config.build_up:
                self.pixels[0 : self.pixel_count] = self.background_color

            self.pixels[
                self.current_pixel : min(
                    self.current_pixel + self.config.pixels,
                    self.pixel_count,
                )
            ] = self.pixel_color

            self.current_pixel += self.config.pixels

            if self.current_pixel >= self.pixel_count:
                self.current_pixel = 0

        self.last_cycle_time = cycle_time

        # Memory tracking for diagnostic - log every 1 second for runtime analysis
        if self.logsec.diag:
            current_time = time.time()
            if current_time - self.last_memory_log_time >= 1.0:
                process = psutil.Process()
                mem_mb = process.memory_info().rss / (1024 * 1024)

                _LOGGER.warning(
                    "[MEMORY] %s render loop: %.1f MB",
                    self._virtual.id,
                    mem_mb,
                )
                Teleplot.send(f"{self._virtual.id}_MB:{mem_mb}")
                self.last_memory_log_time = current_time
