import numpy as np
import voluptuous as vol

from ledfx.color import COLORS, GRADIENTS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BandsMatrixAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Bands Matrix"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "band_count", description="Number of bands", default=6
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
            vol.Optional(
                "gradient_name",
                description="Color gradient to display",
                default="Rainbow",
            ): vol.In(list(GRADIENTS.keys())),
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=False,
            ): bool,
            vol.Optional(
                "flip_gradient",
                description="Flip Gradient",
                default=False,
            ): bool,
        }
    )

    def config_updated(self, config):
        # Create the filters used for the effect
        self._r_filter = self.create_filter(alpha_decay=0.05, alpha_rise=0.999)
        self.bkg_color = np.array(COLORS["black"], dtype=float)
        self.flip_gradient = config["flip_gradient"]

    def audio_data_updated(self, data):
        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count, filtered=False)
        filtered_y = data.interpolated_melbank(self.pixel_count, filtered=True)

        # Grab the filtered difference between the filtered melbank and the
        # raw melbank.
        r = self._r_filter.update(y - filtered_y)
        out = np.tile(r, (3, 1)).T
        out_clipped = np.clip(out, 0, 1)
        out_split = np.array_split(
            out_clipped, self._config["band_count"], axis=0
        )
        for i in range(self._config["band_count"]):
            band_width = len(out_split[i])
            volume = int(out_split[i].max() * band_width)
            out_split[i][volume:] = self.bkg_color
            for p in range(volume):
                gradient_value = (
                    1 - p / band_width
                    if self.flip_gradient
                    else p / band_width
                )
                out_split[i][p] = self.get_gradient_color(gradient_value)

            if i % 2 != 0:
                out_split[i] = np.flip(out_split[i], axis=0)

        self.pixels = np.vstack(out_split)
