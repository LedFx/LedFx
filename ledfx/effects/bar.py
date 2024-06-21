import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BarAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Bar"
    CATEGORY = "BPM"
    HIDDEN_KEYS = ["gradient_roll"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mode",
                description="Choose from different animations",
                default="wipe",
            ): vol.In(list(["bounce", "wipe", "in-out"])),
            vol.Optional(
                "ease_method",
                description="Acceleration profile of bar",
                default="ease_out",
            ): vol.In(list(["ease_in_out", "ease_in", "ease_out", "linear"])),
            vol.Optional(
                "color_step",
                description="Amount of color change per beat",
                default=0.125,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0625, max=0.5)),
            vol.Optional(
                "beat_skip",
                description="Skips odd or even beats",
                default="none",
            ): vol.In(list(["none", "odds", "even"])),
            vol.Optional(
                "skip_every",
                description="If skipping beats, skip every",
                default=1,
            ): vol.In(
                list([1, 2])
            ),
            vol.Optional(
                "delay_beats",
                description="Delay effect by x amount of beats",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
        }
    )

    def on_activate(self, pixel_count):
        self.beat_oscillator = 0
        self.beat_now = False
        self.phase = 0
        self.color_idx = 0
        self.bar_len = 0.3
        self.beat_count = 0
        self.beat_count_before = 0
        self.delayed = False
        self.first_beat = True
        self.has_beat_once = False
        self.beats_since_active = 0
        self.last_beat = 0.0



    def audio_data_updated(self, data):
        # Run linear beat oscillator through easing method
        self.beat_oscillator = data.beat_oscillator()
        self.beat_now = data.bpm_beat_now()

        # Skips first beat after activation to sync up all segments
        if self.first_beat:
            self.beat_count_before = data.beat_counter
            self.beat_count = data.beat_counter
            self.first_beat = False
        else:
            self.beat_count_before = self.beat_count
            self.beat_count = data.beat_counter

        # Fixes a bug where delay would be out of sync when music is not playing on effect activation
        if not self.has_beat_once:
            if self.beat_count_before != self.beat_count:
                self.has_beat_once = True
                return
            else:
                return
            
        # Counts the beats since activation of effect; Unblocks render function when specified amount of beats is reached
        if self._config["delay_beats"] > 0 and not self.delayed:
            print(str(self.beat_count_before) + " " + str(self.beat_count) + " " + str(self.beats_since_active))
            if self.beat_count_before == 3 and self.beat_count == 0:
                self.beats_since_active += 1
            else:
                self.beats_since_active += (self.beat_count - self.beat_count_before)

            if self.beats_since_active >= self._config["delay_beats"]:
                self.delayed = True
            else:
                return

        # color change and phase
        if self.last_beat > 0.2 and self.beat_oscillator < 0.1:
            self.phase = 1 - self.phase  # flip flop 0->1, 1->0
            if self.phase == 0:
                # 8 colors, 4 beats to a bar
                self.color_idx += self._config["color_step"]
                self.color_idx = self.color_idx % 1  # loop back to zero

        self.last_beat = self.beat_oscillator

    def render(self):
        # Blocks render function until specified amount of beats since activation is reached
        if self._config["delay_beats"] > 0 and not self.delayed:
            return
        
        if self._config["ease_method"] == "ease_in_out":
            x = 0.5 * np.sin(np.pi * (self.beat_oscillator - 0.5)) + 0.5
        elif self._config["ease_method"] == "ease_in":
            x = self.beat_oscillator**2
        elif self._config["ease_method"] == "ease_out":
            x = -((self.beat_oscillator - 1) ** 2) + 1
        elif self._config["ease_method"] == "linear":
            x = self.beat_oscillator

        # Compute position of bar start and stop
        if self._config["mode"] == "wipe":
            if self.phase == 0:
                bar_end = x
                bar_start = 0
            elif self.phase == 1:
                bar_end = 1
                bar_start = x

        elif self._config["mode"] == "bounce":
            x = x * (1 - self.bar_len)
            if self.phase == 0:
                bar_end = x + self.bar_len
                bar_start = x
            elif self.phase == 1:
                bar_end = 1 - x
                bar_start = 1 - (x + self.bar_len)

        elif self._config["mode"] == "in-out":
            if self.phase == 0:
                bar_end = x
                bar_start = 0
            elif self.phase == 1:
                bar_end = 1 - x
                bar_start = 0

        # Construct the bar
        color = self.get_gradient_color(self.color_idx)
        if self._config["beat_skip"] != "none" and (
            (
                (self.beat_count == 0 or self.beat_count == 1)
                if (self._config["skip_every"] == 2)
                else not self.beat_count % 2
            )
            == (self._config["beat_skip"] == "even")
        ):
            color = np.array([0, 0, 0])

        self.pixels = np.zeros(np.shape(self.pixels))
        self.pixels[
            int(self.pixel_count * bar_start) : int(
                self.pixel_count * bar_end
            ),
            :,
        ] = color
