import logging
import timeit

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect

_LOGGER = logging.getLogger(__name__)


def is_alive(thing):
    return thing.alive


class Sparkle:
    def __init__(self, pos, width, speed, die_off):
        self.pos = int(pos)
        self.width = int(width)
        self.speed = speed
        self.die_off = die_off
        self.born = timeit.default_timer()
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
                "sparkles_max",
                description="max number of sparkles",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Optional(
                "sparkles_size", description="of scan size ", default=0.1
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "sparkles_time", description="secs to die off", default=1.0
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=2)),
            vol.Optional(
                "sparkles_threshold",
                description="level to trigger",
                default=0.6,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=0.9)),
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
        self.power = 0
        self.sparkles = []
        self.last_sparkle = 0

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

    def render(self):
        # setup colors
        if self._config["use_grad"]:
            gradient_pos = (self.scan_pos / self.pixel_count) % 1
            self.color_scan = self.get_gradient_color(gradient_pos)
        else:
            self.color_scan = self.color_scan_cache

        if self._config["color_intensity"]:
            self.color_scan = self.color_scan * min(1.0, self.power)

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

        # move and age any sparkles
        for sparkle in self.sparkles:
            sparkle.age(now, time_passed, self.pixel_count)

        self.sparkles = list(filter(is_alive, self.sparkles))

        pixel_pos = max(0, min(int(self.scan_pos), self.pixel_count))

        # add any new sparkles
        if len(self.sparkles) < self._config["sparkles_max"]:
            if self.power > self._config["sparkles_threshold"] * 2:
                # cannot convince myself to limit sparkles per second
                # if now - self.last_sparkle > (1 / self._config["sparkles_max"]):
                sparkle_width = (
                    scan_width_pixels * self._config["sparkles_size"]
                )
                if not self.returning:
                    sparkle_pos = (
                        pixel_pos - sparkle_width
                    ) % self.pixel_count
                else:
                    sparkle_pos = (
                        pixel_pos + scan_width_pixels
                    ) % self.pixel_count

                sparkle = Sparkle(
                    sparkle_pos,
                    sparkle_width,
                    (0 - step_per_sec) if self.returning else step_per_sec,
                    self._config["sparkles_time"],
                )
                self.sparkles.append(sparkle)
                self.last_sparkle = now

        # this is the real render pass
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

        # render any sparkles
        for sparkles in self.sparkles:
            sparkles.render(self.pixels, self.pixel_count)
