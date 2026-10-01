import numpy as np
from pydantic import Field

from ledfx.color import parse_color
from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class PowerAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Power"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True

    class Config(GradientEffect.Config):
        mirror: bool = Field(True, description="Mirror the effect")
        blur: CoercedFloat = Field(
            0.0, description="Amount to blur the effect", ge=0.0, le=10
        )
        sparks_color: Color = Field("#ffffff", description="Flash on percussive hits")
        bass_decay_rate: CoercedFloat = Field(
            0.05, description="Bass decay rate. Higher -> decays faster.", ge=0, le=1
        )
        sparks_decay_rate: CoercedFloat = Field(
            0.15, description="Sparks decay rate. Higher -> decays faster.", ge=0, le=1
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.sparks_overlay = np.zeros((pixel_count, 3))
        self.bass_overlay = np.zeros((pixel_count, 3))
        self.bg = np.zeros((pixel_count, 3))
        self.onset = False

    def config_updated(self, config):
        # Create the filters used for the effect
        self._bass_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.8)
        self.sparks_color = parse_color(self.config.sparks_color)
        self.sparks_decay_rate = 1 - self.config.sparks_decay_rate
        self.bass_decay_rate = 1 - self.config.bass_decay_rate

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
