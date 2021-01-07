import numpy as np
import voluptuous as vol

from ledfx.color import GRADIENTS
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class EQAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Equalizer"

    CONFIG_SCHEMA = vol.Schema(
        {
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
                "gradient_repeat",
                description="Repeat the gradient into segments",
                default=6,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=False,
            ): bool,
        }
    )

    def config_updated(self, config):
        # Create the filters used for the effect
        self._r_filter = self.create_filter(alpha_decay=0.5, alpha_rise=0.1)

    def audio_data_updated(self, data):
        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count, filtered=False)
        filtered_y = data.interpolated_melbank(self.pixel_count, filtered=True)

        # Grab the filtered difference between the filtered melbank and the
        # raw melbank.
        r = self._r_filter.update(y - filtered_y)
        r_clipped = np.clip(r, 0, 1)
        r_split = np.array_split(r_clipped, self._config["gradient_repeat"])
        for i in range(self._config["gradient_repeat"]):
            band_width = len(r_split[i])
            # length (volume) of band
            volume = int(r_split[i].sum() * band_width)
            r_split[i][:] = 0
            if volume:
                r_split[i][:volume] = 1
            if self._config["align"] == "center":
                r_split[i] = np.roll(
                    r_split[i], (band_width - volume) // 2, axis=0
                )
            elif self._config["align"] == "invert":
                r_split[i] = np.roll(r_split[i], -volume // 2, axis=0)
            elif self._config["align"] == "right":
                r_split[i] = np.flip(r_split[i], axis=0)
            elif self._config["align"] == "left":
                pass

        self.pixels = self.apply_gradient(np.hstack(r_split))
