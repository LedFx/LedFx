import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect


class WavelengthAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Wavelength"

    # There is no additional configuration here, but override the blur
    # default to be 3.0 so blurring is enabled.
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10))
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

        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self.apply_gradient(r)
