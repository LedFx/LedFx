import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BlocksAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Blocks"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "block_count",
                description="Number of color blocks",
                default=4,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10))
        }
    )

    def config_updated(self, config):
        # Create the filters used for the effect
        self._r_filter = self.create_filter(alpha_decay=0.2, alpha_rise=0.99)

    def audio_data_updated(self, data):
        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count, filtered=False)
        filtered_y = data.interpolated_melbank(self.pixel_count, filtered=True)

        # Grab the filtered difference between the filtered melbank and the
        # raw melbank.
        r = self._r_filter.update(y - filtered_y)
        out = np.tile(r, (3, 1))
        out_split = np.array_split(out, self._config["block_count"], axis=1)
        for i in range(self._config["block_count"]):
            color = self.get_gradient_color(i / self._config["block_count"])[
                :, np.newaxis
            ]
            out_split[i] = np.multiply(
                out_split[i], (out_split[i].max() * color)
            )

        self.pixels = np.hstack(out_split).T
