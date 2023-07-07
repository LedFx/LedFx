import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class BandsMatrixAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Bands Matrix"
    CATEGORY = "2D"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "band_count", description="Number of bands", default=6
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
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

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def config_updated(self, config):
        # Create the filters used for the effect
        self.bkg_color = np.array((0, 0, 0), dtype=float)
        self.flip_gradient = config["flip_gradient"]

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)

    def render(self):
        bands_active = min(self._config["band_count"], self.pixel_count)
        out = np.tile(self.r, (3, 1)).T
        np.clip(out, 0, 1, out=out)
        out_split = np.array_split(out, bands_active, axis=0)
        for i in range(bands_active):
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
