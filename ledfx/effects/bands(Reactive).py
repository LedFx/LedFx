import numpy as np
import voluptuous as vol

from ledfx.color import COLORS, GRADIENTS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BandsAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Bands"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "band_count", description="Number of bands", default=6
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
            vol.Optional(
                "align",
                description="Alignment of bands",
                default="left",
            ): vol.In(list(["left", "right", "invert", "center"])),
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
        }
    )

    def config_updated(self, config):
        # Create the filters used for the effect
        self._r_filter = self.create_filter(alpha_decay=0.05, alpha_rise=0.999)
        self.bkg_color = np.array(COLORS["black"], dtype=float)

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
            color = self.get_gradient_color(i / self._config["band_count"])
            vol = int(out_split[i].max() * band_width)  # length (vol) of band
            out_split[i][:] = self.bkg_color
            if vol:
                out_split[i][:vol] = color
            if self._config["align"] == "center":
                out_split[i] = np.roll(
                    out_split[i], (band_width - vol) // 2, axis=0
                )
            elif self._config["align"] == "invert":
                out_split[i] = np.roll(out_split[i], -vol // 2, axis=0)
            elif self._config["align"] == "right":
                out_split[i] = np.flip(out_split[i], axis=0)
            elif self._config["align"] == "left":
                pass

        self.pixels = np.vstack(out_split)
