import queue
import time

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color, validate_gradient
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.utils import empty_queue


class Strobe(AudioReactiveEffect, GradientEffect):
    NAME = "Strobe"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "gradient",
                description="Color scheme for bass strobe to cycle through",
                default="Dancefloor",
            ): validate_gradient,
            vol.Optional(
                "color_step",
                description="Amount of color change per bass strobe",
                default=0.0625,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=0.25)),
            vol.Optional(
                "bass_strobe_decay_rate",
                description="Bass strobe decay rate. Higher -> decays faster.",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "strobe_color",
                description="color for percussive strobes",
                default="#FFFFFF",
            ): validate_color,
            vol.Optional(
                "strobe_width",
                description="Percussive strobe width, in pixels",
                default=10,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000)),
            vol.Optional(
                "strobe_decay_rate",
                description="Percussive strobe decay rate. Higher -> decays faster.",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "color_shift_delay",
                description="color shift delay for percussive strobes. Lower -> more shifts",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        }
    )

    def on_activate(self, pixel_count):
        self.strobe_overlay = np.zeros(np.shape(self.pixels))
        self.bass_strobe_overlay = np.zeros(np.shape(self.pixels))
        self.onsets_queue = queue.Queue()

    def deactivate(self):
        empty_queue(self.onsets_queue)
        self.onsets_queue = None
        return super().deactivate()

    def config_updated(self, config):
        self.color_shift_step = self._config["color_step"]

        self.strobe_color = np.array(
            parse_color(self._config["strobe_color"]), dtype=float
        )
        self.last_color_shift_time = 0
        self.strobe_width = self._config["strobe_width"]
        self.color_shift_delay_in_seconds = self._config["color_shift_delay"]
        self.color_idx = 0

        self.last_strobe_time = 0
        self.strobe_wait_time = 0
        self.strobe_decay_rate = 1 - self._config["strobe_decay_rate"]

        self.last_bass_strobe_time = 0
        self.bass_strobe_wait_time = 0.2
        self.bass_strobe_decay_rate = (
            1 - self._config["bass_strobe_decay_rate"]
        )

    def render(self):
        pixels = np.copy(self.bass_strobe_overlay)

        # Sometimes we lose the queue? No idea why. This should ensure it doesn't happen
        if self.onsets_queue is None:
            self.onsets_queue = queue.Queue()

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

    def audio_data_updated(self, data):
        currentTime = time.time()

        if (
            currentTime - self.last_color_shift_time
            > self.color_shift_delay_in_seconds
        ):
            self.color_idx += self.color_shift_step
            self.color_idx = self.color_idx % 1
            self.bass_strobe_color = self.get_gradient_color(self.color_idx)
            self.last_color_shift_time = currentTime

        if (
            data.volume_beat_now()
            and currentTime - self.last_bass_strobe_time
            > self.bass_strobe_wait_time
            and self.bass_strobe_decay_rate
        ):
            self.bass_strobe_overlay = np.tile(
                self.bass_strobe_color, (self.pixel_count, 1)
            )
            self.last_bass_strobe_time = currentTime

        if (
            data.onset()
            and currentTime - self.last_strobe_time > self.strobe_wait_time
        ):
            self.onsets_queue.put(True)
            self.last_strobe_time = currentTime
