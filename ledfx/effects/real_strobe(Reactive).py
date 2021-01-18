import queue
import time

import numpy as np
import voluptuous as vol

from ledfx.color import COLORS, GRADIENTS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class Strobe(AudioReactiveEffect, GradientEffect):

    NAME = "Real Strobe"
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "gradient_name",
                description="Color scheme for bass strobe to cycle through",
                default="Dancefloor",
            ): vol.In(list(GRADIENTS.keys())),
            vol.Optional(
                "color_step",
                description="Amount of color change per bass strobe",
                default=0.0625,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=0.25)),
            vol.Optional(
                "bass_threshold",
                description="Cutoff for quiet sounds. Higher -> only loud sounds are detected",
                default=0.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "bass_strobe_decay_rate",
                description="Bass strobe decay rate. Higher -> decays faster.",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "strobe_color",
                description="Colour for note strobes",
                default="white",
            ): vol.In(list(COLORS.keys())),
            vol.Optional(
                "strobe_width",
                description="Note strobe width, in pixels",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000)),
            vol.Optional(
                "strobe_decay_rate",
                description="Note strobe decay rate. Higher -> decays faster.",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        }
    )

    def activate(self, pixel_count):
        super().activate(pixel_count)
        self.strobe_overlay = np.zeros(np.shape(self.pixels))
        self.bass_strobe_overlay = np.zeros(np.shape(self.pixels))
        self.onsets_queue = queue.Queue()

    def config_updated(self, config):
        self.bass_threshold = self._config["bass_threshold"]
        self.color_shift_step = self._config["color_step"]

        self.strobe_color = np.array(
            COLORS[self._config["strobe_color"]], dtype=float
        )
        self.last_color_shift_time = 0
        self.strobe_width = self._config["strobe_width"]
        self.color_shift_delay_in_seconds = 1
        self.color_idx = 0

        self.last_strobe_time = 0
        self.strobe_wait_time = 0
        self.strobe_decay_rate = 1 - self._config["strobe_decay_rate"]

        self.last_bass_strobe_time = 0
        self.bass_strobe_wait_time = 0
        self.bass_strobe_decay_rate = (
            1 - self._config["bass_strobe_decay_rate"]
        )

    def get_pixels(self):
        pixels = np.copy(self.bass_strobe_overlay)

        if not self.onsets_queue.empty():
            self.onsets_queue.get()
            strobe_width = min(self.strobe_width, self.pixel_count)
            length_diff = self.pixel_count - strobe_width
            position = (
                0
                if length_diff == 0
                else np.random.randint(self.pixel_count - strobe_width)
            )
            self.strobe_overlay[
                position : position + strobe_width
            ] = self.strobe_color

        pixels += self.strobe_overlay

        self.strobe_overlay *= self.strobe_decay_rate
        self.bass_strobe_overlay *= self.bass_strobe_decay_rate
        self.pixels = pixels
        return self.pixels

    def audio_data_updated(self, data):
        self._dirty = True

        currentTime = time.time()

        if (
            currentTime - self.last_color_shift_time
            > self.color_shift_delay_in_seconds
        ):
            self.color_idx += self.color_shift_step
            self.color_idx = self.color_idx % 1
            self.bass_strobe_color = self.get_gradient_color(self.color_idx)
            self.last_color_shift_time = currentTime

        lows_intensity = np.mean(data.melbank_lows())
        if (
            lows_intensity > self.bass_threshold
            and currentTime - self.last_bass_strobe_time
            > self.bass_strobe_wait_time
        ):
            self.bass_strobe_overlay = np.tile(
                self.bass_strobe_color, (self.pixel_count, 1)
            )
            self.last_bass_strobe_time = currentTime

        onsets = data.onset()
        if (
            onsets["high"]
            and currentTime - self.last_strobe_time > self.strobe_wait_time
        ):
            self.onsets_queue.put(True)
            self.last_strobe_time = currentTime
