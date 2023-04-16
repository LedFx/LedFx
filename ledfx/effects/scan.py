import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class ScanAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Scan"
    CATEGORY = "Classic"
    HIDDEN_KEYS = ["gradient_roll"]

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
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
                "color_scan",
                description="Color of scan",
                default="#FF0000",
            ): validate_color,
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
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

    def on_activate(self, pixel_count):
        self.scan_pos = 0.0
        self.returning = False
        self.last_time = timeit.default_timer()
        self.bar = 0

    def config_updated(self, config):
        self.background_color = np.array(
            parse_color(self._config["background_color"]), dtype=float
        )
        self.power_func = self._power_funcs[self._config["frequency_range"]]
        self.color_scan_cache = np.array(
            parse_color(self._config["color_scan"]), dtype=float
        )
        self.color_scan = self.color_scan_cache

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.bar = self.power * self._config["multiplier"]

        if self._config["use_grad"]:
            gradient_pos = (self.scan_pos / self.pixel_count) % 1
            self.color_scan = self.get_gradient_color(gradient_pos)
        else:
            self.color_scan = self.color_scan_cache

        if self._config["color_intensity"]:
            self.color_scan = self.color_scan * min(1.0, self.power)

    def render(self):
        now = timeit.default_timer()
        time_passed = now - self.last_time
        self.last_time = now

        step_per_sec = self.pixel_count / 100.0 * self._config["speed"]
        step_size = time_passed * step_per_sec

        step_size = step_size * self.bar

        scan_width_pixels = int(
            max(1, int(self.pixel_count / 100.0 * self._config["scan_width"]))
        )
        if self.returning:
            self.scan_pos -= step_size
        else:
            self.scan_pos += step_size

        if self._config["bounce"]:
            if self.scan_pos > self.pixel_count - scan_width_pixels:
                self.returning = True
            if self.scan_pos < 0:
                self.returning = False
        else:
            if self.scan_pos > self.pixel_count:
                self.scan_pos = 0.0
            if self.scan_pos < 0:
                self.returning = False

        pixel_pos = max(0, min(int(self.scan_pos), self.pixel_count))

        self.pixels[0 : self.pixel_count] = (
            self.background_color * self.config["background_brightness"]
        )
        self.pixels[
            pixel_pos : min(pixel_pos + scan_width_pixels, self.pixel_count)
        ] = self.color_scan

        if not self._config["bounce"]:
            overflow = (pixel_pos + scan_width_pixels) - self.pixel_count
            if overflow > 0:
                self.pixels[:overflow] = self.color_scan
