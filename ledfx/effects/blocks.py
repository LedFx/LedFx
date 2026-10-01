import numpy as np
from pydantic import Field

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BlocksAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Blocks"
    CATEGORY = "2D"
    USES_MELBANK_RANGE = True

    class Config(GradientEffect.Config):
        block_count: CoercedInt = Field(
            4, description="Number of color blocks", ge=1, le=10
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)

    def render(self):
        blocks_active = min(self.config.block_count, self.pixel_count)

        out = np.tile(self.r, (3, 1))
        out_split = np.array_split(out, blocks_active, axis=1)
        for i in range(blocks_active):
            color = self.get_gradient_color(i / blocks_active)[:, np.newaxis]
            out_split[i] = np.multiply(out_split[i], (out_split[i].max() * color))

        self.pixels = np.hstack(out_split).T
        self.roll_gradient()
