from enum import IntEnum
from typing import Annotated, ClassVar

import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, CoercedInt, Color, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.utils import Graph

# this is kept as an example of how to use the graph util
# set to True to test, hit flip to trigger graph spawning in browser
# any config change will add a text annotation to the graph
graph_dump = False


class Power(IntEnum):
    LOWS = 0
    MIDS = 1
    HIGH = 2


class Scan:
    def __init__(self, power_func):
        self.scan_pos = 0.0
        self.returning = False
        self.bar: float = 0
        self.power_func = power_func
        self.power = 0.0
        if graph_dump:
            self.graph = Graph(
                f"Scan Filter {power_func}", ["p_in", "p_out"], y_title="Power"
            )

    def set_color_scan_cache(self, color):
        self.color_scan_cache = np.array(parse_color(color), dtype=float)
        self.color_scan = self.color_scan_cache


SCAN_MULTI_SOURCES: dict[str, str] = {
    "Power": "power",
    "Melbank": "melbank",
}


class ScanMultiAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Scan Multi"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]
    ADVANCED_KEYS = AudioReactiveEffect.ADVANCED_KEYS + [
        "input_source",
        "attack",
        "decay",
        "filter",
    ]

    _sources: ClassVar[dict[str, str]] = SCAN_MULTI_SOURCES

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
        color_low: Color = Field("#FF0000", description="Color of low power scan")
        color_mid: Color = Field("#00FF00", description="Color of mid power scan")
        color_high: Color = Field("#0000FF", description="Color of high power scan")
        multiplier: CoercedFloat = Field(
            3.0, description="Speed impact multiplier", ge=0.0, le=5.0
        )
        color_intensity: bool = Field(
            True, description="Adjust color intensity based on audio power"
        )
        use_grad: bool = Field(False, description="Use colors from gradient selector")
        input_source: Annotated[str, OneOf(list(SCAN_MULTI_SOURCES.keys()))] = Field(
            "Power", description="Audio processing source for low, mid, high"
        )
        attack: CoercedFloat = Field(
            0.9,
            description="Filter damping on attack, lower number is more",
            ge=0.01,
            le=0.99999,
        )
        decay: CoercedFloat = Field(
            0.7,
            description="Filter damping on decay, lower number is more",
            ge=0.01,
            le=0.99999,
        )
        filter: bool = Field(
            False, description="Enable damping filters on attack and decay"
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        self.scans = [
            Scan("lows_power"),
            Scan("mids_power"),
            Scan("high_power"),
        ]
        self.flip_was = config.flip
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.last_time = self.now

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self.config.background_color), dtype=float
        )
        self.scans[Power.LOWS].set_color_scan_cache(self.config.color_low)
        self.scans[Power.MIDS].set_color_scan_cache(self.config.color_mid)
        self.scans[Power.HIGH].set_color_scan_cache(self.config.color_high)

        for scan in self.scans:
            scan._p_filter = self.create_filter(
                alpha_decay=self.config.decay,
                alpha_rise=self.config.attack,
            )

        if graph_dump:
            for scan in self.scans:
                if self.config.flip != self.flip_was:
                    scan.graph.dump_graph("Flip")
                scan.graph.append_tag("Config changed", scan.power, color="red")
            self.flip_was = self.config.flip

    def audio_data_updated(self, data):
        if self.config.input_source == "Melbank":
            self.scans[0].power, self.scans[1].power, self.scans[2].power = (
                2 * np.mean(i) for i in self.melbank_thirds(filtered=False)
            )
        else:
            for scan in self.scans:
                scan.power = getattr(data, scan.power_func)() * 2

        for scan in self.scans:
            if graph_dump:
                scan.graph.append_by_key("p_in", scan.power)
            if self.config.filter:
                scan.power = scan._p_filter.update(scan.power)
            if graph_dump:
                scan.graph.append_by_key("p_out", scan.power)

            scan.bar = scan.power * self.config.multiplier

            if self.config.use_grad:
                gradient_pos = (scan.scan_pos / self.pixel_count) % 1
                scan.color_scan = self.get_gradient_color(gradient_pos)
            else:
                scan.color_scan = scan.color_scan_cache

            if self.config.color_intensity:
                scan.color_scan = scan.color_scan * min(1.0, scan.power)

    def render(self):
        step_per_sec = self.pixel_count / 100.0 * self.config.speed
        step_size = self.passed * step_per_sec

        scan_width_pixels = int(
            max(1, int(self.pixel_count / 100.0 * self.config.scan_width))
        )

        self.pixels[0 : self.pixel_count] = (
            self.background_color * self.config.background_brightness
        )

        for scan in self.scans:
            step_size = step_size * scan.bar

            if scan.returning:
                scan.scan_pos -= step_size
            else:
                scan.scan_pos += step_size

            if self.config.bounce:
                if scan.scan_pos > self.pixel_count - scan_width_pixels:
                    scan.returning = True
                if scan.scan_pos < 0:
                    scan.returning = False
            else:
                if scan.scan_pos > self.pixel_count:
                    scan.scan_pos = 0.0
                if scan.scan_pos < 0:
                    scan.returning = False

            pixel_pos = max(0, min(int(scan.scan_pos), self.pixel_count))

            # actually render
            self.pixels[
                pixel_pos : min(pixel_pos + scan_width_pixels, self.pixel_count)
            ] += scan.color_scan

            if not self.config.bounce:
                overflow = (pixel_pos + scan_width_pixels) - self.pixel_count
                if overflow > 0:
                    self.pixels[:overflow] += scan.color_scan
