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
            vol.Optional(
                "flip_horizontal",
                description="Flip horizontally",
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
        self.flip_horizontal = config["flip_horizontal"]
        self.band_count = config["band_count"]

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)

    def render(self):
        bands_active = min(self.band_count, self.pixel_count)
        out = np.tile(self.r, (3, 1)).T
        np.clip(out, 0, 1, out=out)
        out_split = np.array_split(out, bands_active, axis=0)

        # Pre-calculate gradient direction multiplier (avoid conditional in loop)
        grad_sign = -1.0 if self.flip_gradient else 1.0
        grad_offset = 1.0 if self.flip_gradient else 0.0

        # Process all bands using vectorized operations
        for i in range(bands_active):
            band_width = len(out_split[i])
            volume = int(out_split[i].max() * band_width)

            # Fill entire band with background color first (avoids conditional)
            out_split[i][:] = self.bkg_color

            # Vectorized gradient calculation for active pixels
            if volume > 0:
                # Calculate gradient values for all positions at once
                positions = np.arange(volume, dtype=np.float32)
                gradient_values = grad_offset + grad_sign * (
                    positions / band_width
                )
                # Get all gradient colors at once using vectorized method
                out_split[i][:volume] = self.get_gradient_color_vectorized1d(
                    gradient_values
                )

            # Flip every other band (in-place)
            if i & 1:  # Bitwise AND is faster than modulo
                out_split[i] = out_split[i][::-1]

        # Use numpy indexing instead of list reverse for horizontal flip
        if self.flip_horizontal:
            out_split = out_split[::-1]

        self.pixels = np.vstack(out_split)
        self.roll_gradient()
