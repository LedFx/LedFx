import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect


class SpectrumAudioEffect(AudioReactiveEffect):
    NAME = "Spectrum"
    CATEGORY = "Classic"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "RGB Mix",
                description="How the melbank filters are applied to the RGB values",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
        }
    )

    rgb_mixes = [
        [0, 1, 2],
        [0, 2, 1],
        [1, 0, 2],
        [1, 2, 0],
        [2, 0, 1],
        [2, 1, 0],
    ]

    def on_activate(self, pixel_count):
        self.out = np.zeros((pixel_count, 3))
        self._prev_y = np.zeros(pixel_count)

        # make sure the b_filter is flushed from prior lifecycles
        # prevent crashes from segment edit / led count changes
        if self._b_filter is not None:
            self._b_filter.value = None
        self.rgb_mix = self.rgb_mixes[self._config["RGB Mix"]]

    def config_updated(self, config):
        # Create all the filters used for the effect
        self._b_filter = self.create_filter(alpha_decay=0.1, alpha_rise=0.5)
        self.rgb_mix = self.rgb_mixes[self._config["RGB Mix"]]

    def audio_data_updated(self, data):
        # Grab the filtered and interpolated melbank data
        # Grab the filtered melbank
        y = self.melbank(filtered=False, size=self.pixel_count)
        self.out[:, self.rgb_mix[0]] = self.melbank(
            filtered=True, size=self.pixel_count
        )
        self.out[:, self.rgb_mix[1]] = np.abs(y - self._prev_y)
        self.out[:, self.rgb_mix[2]] = self._b_filter.update(y)
        self.out *= 1000

        self._prev_y = y

    def render(self):
        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self.out
