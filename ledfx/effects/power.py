import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class PowerAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Power"
    CATEGORY = "Classic"

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
                "sparks_color",
                description="Flash on percussive hits",
                default="#ffffff",
            ): validate_color,
            vol.Optional(
                "bass_decay_rate",
                description="Bass decay rate. Higher -> decays faster.",
                default=0.05,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
            vol.Optional(
                "sparks_decay_rate",
                description="Sparks decay rate. Higher -> decays faster.",
                default=0.15,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
        }
    )

    def on_activate(self, pixel_count):
        self.sparks_overlay = np.zeros((pixel_count, 3))
        self.bass_overlay = np.zeros((pixel_count, 3))
        self.bg = np.zeros((pixel_count, 3))
        self.onset = False

    def config_updated(self, config):
        # Create the filters used for the effect
        self._bass_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.8)
        self.sparks_color = parse_color(self._config["sparks_color"])
        self.sparks_decay_rate = 1 - self._config["sparks_decay_rate"]
        self.bass_decay_rate = 1 - self._config["bass_decay_rate"]

    def audio_data_updated(self, data):
        # Fade existing sparks a little
        self.sparks_overlay *= self.sparks_decay_rate
        # Get onset data
        if data.onset():
            # Apply new sparks
            sparks = np.random.choice(self.pixel_count, self.pixel_count // 20)
            self.sparks_overlay[sparks] = self.sparks_color

        # Fade bass overlay a little
        self.bass_overlay *= self.bass_decay_rate
        # Get bass power through filter
        bass = np.max(data.lows_power(filtered=False))
        bass = self._bass_filter.update(bass)
        # Map it to the length of the overlay and apply it
        bass_idx = int(bass * self.pixel_count)
        self.bass_overlay[:bass_idx] = self.get_gradient_color(bass)

        # Grab the filtered melbank
        r = self.melbank(filtered=True, size=self.pixel_count)
        # Apply the melbank data to the gradient curve
        self.bg = self.apply_gradient(r)

    def render(self):
        self.pixels = self.bg + self.bass_overlay + self.sparks_overlay
