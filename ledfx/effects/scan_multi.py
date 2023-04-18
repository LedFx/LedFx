import timeit
from enum import IntEnum

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
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
        self.bar = 0
        self.power_func = power_func
        self.power = 0.0
        if graph_dump:
            self.graph = Graph(
                f"Scan Filter {power_func}", ["p_in", "p_out"], y_title="Power"
            )

    def set_color_scan_cache(self, color):
        self.color_scan_cache = np.array(parse_color(color), dtype=float)
        self.color_scan = self.color_scan_cache


class ScanMultiAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Scan Multi"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["gradient_roll"]
    ADVANCED_KEYS = ["input_source", "attack", "decay", "filter"]

    _sources = {
        "Power": "power",
        "Melbank": "melbank",
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=False,
            ): bool,
            vol.Optional(
                "bounce",
                description="bounce the scan",
                default=True,
            ): bool,
            vol.Optional(
                "scan_width", description="Width of scan eye in %", default=30
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional(
                "speed", description="Scan base % per second", default=50
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                "color_low",
                description="Color of low power scan",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "color_mid",
                description="Color of mid power scan",
                default="#00FF00",
            ): validate_color,
            vol.Optional(
                "color_high",
                description="Color of high power scan",
                default="#0000FF",
            ): validate_color,
            vol.Optional(
                "multiplier",
                description="Speed impact multiplier",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
            vol.Optional(
                "color_intensity",
                description="Adjust color intensity based on audio power",
                default=True,
            ): bool,
            vol.Optional(
                "use_grad",
                description="Use colors from gradient selector",
                default=False,
            ): bool,
            vol.Optional(
                "advanced",
                description="enable advanced options",
                default=True,
            ): bool,
            vol.Optional(
                "input_source",
                description="Audio processing source for low, mid, high",
                default="Power",
            ): vol.In(list(_sources.keys())),
            vol.Optional(
                "attack",
                description="Filter damping on attack, lower number is more",
                default=0.9,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.99999)),
            vol.Optional(
                "decay",
                description="Filter damping on decay, lower number is more",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.99999)),
            vol.Optional(
                "filter",
                description="Enable damping filters on attack and decay",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        self.scans = [
            Scan("lows_power"),
            Scan("mids_power"),
            Scan("high_power"),
        ]
        self.flip_was = config["flip"]
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.last_time = timeit.default_timer()

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self._config["background_color"]), dtype=float
        )
        self.scans[Power.LOWS].set_color_scan_cache(self._config["color_low"])
        self.scans[Power.MIDS].set_color_scan_cache(self._config["color_mid"])
        self.scans[Power.HIGH].set_color_scan_cache(self._config["color_high"])

        for scan in self.scans:
            scan._p_filter = self.create_filter(
                alpha_decay=self._config["decay"],
                alpha_rise=self._config["attack"],
            )

        if graph_dump:
            for scan in self.scans:
                if self._config["flip"] != self.flip_was:
                    scan.graph.dump_graph("Flip")
                scan.graph.append_tag(
                    "Config changed", scan.power, color="red"
                )
            self.flip_was = self._config["flip"]

    def audio_data_updated(self, data):
        if self._config["input_source"] == "Melbank":
            self.scans[0].power, self.scans[1].power, self.scans[2].power = (
                2 * np.mean(i) for i in self.melbank_thirds(filtered=False)
            )
        else:
            for scan in self.scans:
                scan.power = getattr(data, scan.power_func)() * 2

        for scan in self.scans:
            if graph_dump:
                scan.graph.append_by_key("p_in", scan.power)
            if self._config["filter"]:
                scan.power = scan._p_filter.update(scan.power)
            if graph_dump:
                scan.graph.append_by_key("p_out", scan.power)

            scan.bar = scan.power * self._config["multiplier"]

            if self._config["use_grad"]:
                gradient_pos = (scan.scan_pos / self.pixel_count) % 1
                scan.color_scan = self.get_gradient_color(gradient_pos)
            else:
                scan.color_scan = scan.color_scan_cache

            if self._config["color_intensity"]:
                scan.color_scan = scan.color_scan * min(1.0, scan.power)

    def render(self):
        now = timeit.default_timer()
        time_passed = now - self.last_time
        self.last_time = now

        step_per_sec = self.pixel_count / 100.0 * self._config["speed"]
        step_size = time_passed * step_per_sec

        scan_width_pixels = int(
            max(1, int(self.pixel_count / 100.0 * self._config["scan_width"]))
        )

        self.pixels[0 : self.pixel_count] = (
            self.background_color * self.config["background_brightness"]
        )

        for scan in self.scans:
            step_size = step_size * scan.bar

            if scan.returning:
                scan.scan_pos -= step_size
            else:
                scan.scan_pos += step_size

            if self._config["bounce"]:
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
                pixel_pos : min(
                    pixel_pos + scan_width_pixels, self.pixel_count
                )
            ] += scan.color_scan

            if not self._config["bounce"]:
                overflow = (pixel_pos + scan_width_pixels) - self.pixel_count
                if overflow > 0:
                    self.pixels[:overflow] += scan.color_scan
