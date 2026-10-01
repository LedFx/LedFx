import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class WavelengthAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Wavelength"
    CATEGORY = "Classic"
    USES_MELBANK_RANGE = True

    # There is no additional configuration here, but override the blur
    # default to be 3.0 so blurring is enabled.
    class Config(GradientEffect.Config):
        blur: CoercedFloat = Field(
            3.0, description="Amount to blur the effect", ge=0.0, le=10
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)

    def render(self):
        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self.apply_gradient(self.r)
