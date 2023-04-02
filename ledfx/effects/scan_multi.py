import timeit
from enum import IntEnum

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


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

    def set_color_scan_cache(self, color):
        self.color_scan_cache = np.array(parse_color(color), dtype=float)
        self.color_scan = self.color_scan_cache


class ScanMultiAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Scan Multi"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["gradient_roll"]

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
        }
    )

    def __init__(self, ledfx, config):
        self.scans = [
            Scan("lows_power"),
            Scan("mids_power"),
            Scan("high_power"),
        ]
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

    def audio_data_updated(self, data):
        for scan in self.scans:
            scan.power = getattr(data, scan.power_func)() * 2
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

        self.pixels[0 : self.pixel_count] = self.background_color

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
