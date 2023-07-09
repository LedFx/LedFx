import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class EQAudioEffect(AudioReactiveEffect, GradientEffect):
    NAME = "Equalizer"
    CATEGORY = "2D"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "align",
                description="Alignment of bands",
                default="left",
            ): vol.In(list(["left", "right", "invert", "center"])),
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

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)
        np.clip(self.r, 0, 1, out=self.r)

    def render(self):
        gradient_repeat = min(
            self._config["gradient_repeat"], self.pixel_count
        )
        r_split = np.array_split(self.r, gradient_repeat)
        for i in range(gradient_repeat):
            band_width = len(r_split[i])
            # length (volume) of band
            volume = int(r_split[i].mean() * band_width)
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
