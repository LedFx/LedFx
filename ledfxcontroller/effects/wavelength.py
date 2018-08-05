from ledfxcontroller.effects.audio import AudioReactiveEffect
from ledfxcontroller.effects.gradient import GradientEffect
import voluptuous as vol
import numpy as np


class WavelengthAudioEffect(AudioReactiveEffect, GradientEffect):

    NAME = "Wavelength"

    # There is no additional configuration here, but override the blur
    # default to be 3.0 so blurring is enabled.
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 3.0): vol.Coerce(float)
    })

    def audio_data_updated(self, data):

        # Grab the filtered and interpolated melbank data
        y = data.interpolated_melbank(self.pixel_count // 2, filtered = False)
        filtered_y = data.interpolated_melbank(self.pixel_count // 2, filtered = True)

        # Grab the filtered difference between the filtered melbank and the
        # raw melbank.
        r = data.get_filter(
            filter_key = "filtered_difference",
            filter_size = self.pixel_count // 2,
            alpha_decay = 0.2,
            alpha_rise = 0.99).update(y - filtered_y)

        # Zip the melbank differences with itself. Not really sure why this is 
        # done instaed of interpolating up to self.pixel_count but not messing
        # with effects yet.
        r = np.array([j for i in zip(r,r) for j in i])

        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self.apply_gradient(r)
