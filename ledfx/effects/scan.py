import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.modulate import ModulateEffect


class ScanAudioEffect(AudioReactiveEffect, GradientEffect, ModulateEffect):
    NAME = "Scan"
    CATEGORY = "Classic"
    ADVANCED_KEYS = [
        "count",
        "gradient_roll",
        "modulation_speed",
        "modulate",
        "modulation_effect",
        "full_grad",
    ]

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

    clear = np.array([0.0, 0.0, 0.0])

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
            vol.Optional(
                "full_grad",
                description="spread the gradient colors across the scan",
                default=False,
            ): bool,
            vol.Optional(
                "advanced",
                description="enable advanced options",
                default=False,
            ): bool,
            vol.Optional(
                "count", description="Number of scan to render", default=1
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
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

        count = self._config["count"]
        block = self.pixel_count / count

        scan_width_pixels = int(
            max(
                1,
                int(self.pixel_count / 100.0 * self._config["scan_width"])
                / count,
            )
        )
        if self.returning:
            self.scan_pos -= step_size
        else:
            self.scan_pos += step_size

        if self._config["bounce"]:
            if self.scan_pos > self.pixel_count - scan_width_pixels:
                self.returning = True
                self.scan_pos = self.pixel_count - scan_width_pixels
            if self.scan_pos < 0:
                self.returning = False
                self.scan_pos = 0
        else:
            if self.scan_pos > self.pixel_count:
                self.scan_pos %= self.pixel_count
            if self.scan_pos < 0:
                self.returning = False

        if self._config["full_grad"]:
            pixels = self.apply_gradient(1)
            self.pixels = self.modulate(pixels)
        else:
            self.pixels = np.zeros(np.shape(self.pixels))

        for idx in range(count):
            if self._config["full_grad"]:
                pixel_pos = max(
                    0, int(self.scan_pos + (block * idx)) % self.pixel_count
                )
                mid_pos = pixel_pos + scan_width_pixels
                end_pos = pixel_pos + int(block)
                self.pixels[
                    min(mid_pos, self.pixel_count) : min(
                        end_pos, self.pixel_count
                    )
                ] = self.clear

                end_flow = end_pos - self.pixel_count
                if end_flow > 0:
                    mid_flow = max(0, mid_pos - self.pixel_count)
                    self.pixels[mid_flow:end_flow] = self.clear
            else:
                pixel_pos = max(
                    0, int(self.scan_pos + (block * idx)) % self.pixel_count
                )

                self.pixels[
                    pixel_pos : min(
                        pixel_pos + scan_width_pixels, self.pixel_count
                    )
                ] = self.color_scan

                overflow = (pixel_pos + scan_width_pixels) - self.pixel_count
                if overflow > 0:
                    self.pixels[:overflow] = self.color_scan
