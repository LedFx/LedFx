import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class PowerAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Power"

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

    def config_updated(self, config):

        # Create the filters used for the effect
        self._r_filter = self.create_filter(alpha_decay=0.2, alpha_rise=0.99)

        self._bass_filter = self.create_filter(
            alpha_decay=0.1, alpha_rise=0.99
        )

        # Would be nice to initialise here with np.shape(self.pixels)
        self.sparks_overlay = None

        self.sparks_decay = 0.75
        self.sparks_color = np.array(COLORS["white"], dtype=float)

    def audio_data_updated(self, data):

        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count, filtered=False)
        filtered_y = data.interpolated_melbank(self.pixel_count, filtered=True)

        # Grab the filtered difference between the filtered melbank and the
        # raw melbank.
        r = self._r_filter.update(y - filtered_y)

        # Apply the melbank data to the gradient curve
        out = self.apply_gradient(r)

        if self._config["sparks"]:
            # Initialise sparks overlay if its not made yet
            if self.sparks_overlay is None:
                self.sparks_overlay = np.zeros(np.shape(self.pixels))
            # Get onset data
            onsets = data.onset()
            # Fade existing sparks a little
            self.sparks_overlay *= self.sparks_decay
            # Apply new sparks
            if onsets["high"]:
                sparks = np.random.choice(
                    self.pixel_count, self.pixel_count // 50
                )
                self.sparks_overlay[sparks] = self.sparks_color
            if onsets["mids"]:
                sparks = np.random.choice(
                    self.pixel_count, self.pixel_count // 10
                )
                self.sparks_overlay[sparks] = self.sparks_color * 1
            # Apply sparks over pixels
            out += self.sparks_overlay

        # Get bass power through filter
        bass = np.max(data.melbank_lows()) * (1 / 5)
        bass = self._bass_filter.update(bass)
        # Grab corresponding color
        color = self.get_gradient_color(bass)
        # Map it to the length of the strip and apply it
        bass_idx = int(bass * self.pixel_count)
        out[:bass_idx] = color

        # Update the pixels
        self.pixels = out
