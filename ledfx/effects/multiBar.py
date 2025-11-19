import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class MultiBarAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Multicolor Bar"
    CATEGORY = "BPM"
    HIDDEN_KEYS = ["gradient_roll"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mode",
                description="Choose from different animations",
                default="wipe",
            ): vol.In(list(["cascade", "wipe"])),
            vol.Optional(
                "ease_method",
                description="Acceleration profile of bar",
                default="linear",
            ): vol.In(list(["ease_in_out", "ease_in", "ease_out", "linear"])),
            vol.Optional(
                "color_step",
                description="Amount of color change per beat",
                default=0.125,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0625, max=0.5)),
        }
    )

    def on_activate(self, pixel_count):
        self.beat_oscillator = 0
        self.beat_now = 0
        self.phase = 0
        self.color_idx = 0
        self.beat_timestamps = []  # Rolling window of beat timestamps
        self.last_teleplot_time = 0  # Track last time we sent to teleplot

    def audio_data_updated(self, data):
        # Run linear beat oscillator through easing method
        self.beat_oscillator, self.beat_now = (
            data.beat_oscillator(),
            data.bpm_beat_now(),
        )

        # Track beats in 1-second rolling window
        import time
        from ledfx.utils import Teleplot 
        current_time = time.time()
        
        if self.beat_now:
            self.beat_timestamps.append(current_time)
        
        # Remove beats older than 10 seconds (list is in chronological order)
        cutoff_time = current_time - 10.0
        while self.beat_timestamps and self.beat_timestamps[0] < cutoff_time:
            self.beat_timestamps.pop(0)
        
        # Calculate beats per minute from 10-second window
        # (beats in 10 seconds) * 6 = beats per minute
        self.beats_per_minute = len(self.beat_timestamps) * 6
        
        # Send to teleplot at 10 Hz (every 0.1 seconds)
        if current_time - self.last_teleplot_time >= 0.1:
            Teleplot.send(f"bpm:{self.beats_per_minute}")
            self.last_teleplot_time = current_time

        # color change and phase
        if self.beat_now:
            self.phase = 1 - self.phase  # flip flop 0->1, 1->0
            # 8 colors, 4 beats to a bar
            self.color_idx += self._config["color_step"]
            self.color_idx = self.color_idx % 1  # loop back to zero

    def render(self):
        # Run linear beat oscillator through easing method
        if self._config["ease_method"] == "ease_in_out":
            x = 0.5 * np.sin(np.pi * (self.beat_oscillator - 0.5)) + 0.5
        elif self._config["ease_method"] == "ease_in":
            x = self.beat_oscillator**2
        elif self._config["ease_method"] == "ease_out":
            x = -((self.beat_oscillator - 1) ** 2) + 1
        elif self._config["ease_method"] == "linear":
            x = self.beat_oscillator

        color_fg = self.get_gradient_color(self.color_idx)
        color_bkg = self.get_gradient_color(
            (self.color_idx + self._config["color_step"]) % 1
        )

        # Compute position of bar start and stop
        if self._config["mode"] == "wipe":
            if self.phase == 0:
                idx = x
            elif self.phase == 1:
                idx = 1 - x
                color_fg, color_bkg = color_bkg, color_fg

        elif self._config["mode"] == "cascade":
            idx = x

        # Construct the array
        self.pixels[: int(self.pixel_count * idx), :] = color_bkg
        self.pixels[int(self.pixel_count * idx) :, :] = color_fg
