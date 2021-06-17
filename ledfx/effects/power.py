import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class PowerAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Power"
    CATEGORY = "1.0"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=True,
            ): bool,
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=0.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "sparks",
                description="Flash on percussive hits",
                default=True,
            ): bool,
        }
    )

    def on_activate(self, pixel_count):
        self.sparks_overlay = np.zeros((pixel_count, 3))
        self.out = np.zeros((pixel_count, 3))
        self.sparks_decay = 0.75
        self.onset = False

    def config_updated(self, config):
        # Create the filters used for the effect
        self._bass_filter = self.create_filter(
            alpha_decay=0.1, alpha_rise=0.99
        )
        self.sparks_color = np.array(COLORS["white"], dtype=float)

    def audio_data_updated(self, data):
        # Get onset data
        self.onset = data.onset()

        # Grab the filtered melbank
        r = self.melbank(filtered=True, size=self.pixel_count)
        # Apply the melbank data to the gradient curve
        self.out = self.apply_gradient(r)

        # Get bass power through filter
        bass = np.max(data.lows_power(filtered=False))
        bass = self._bass_filter.update(bass)
        # Grab corresponding color
        color = self.get_gradient_color(bass)
        # Map it to the length of the strip and apply it
        bass_idx = int(bass * self.pixel_count)
        self.out[:bass_idx] = color

    def render(self):
        if self._config["sparks"]:
            # Fade existing sparks a little
            self.sparks_overlay *= self.sparks_decay
            # Apply new sparks
            if self.onset:
                sparks = np.random.choice(
                    self.pixel_count, self.pixel_count // 50
                )
                self.sparks_overlay[sparks] = self.sparks_color
            # Apply sparks over pixels
            self.out += self.sparks_overlay

        # Update the pixels
        return self.out
