from ledfx.effects.audio import AudioReactiveEffect
from ledfx.color import COLORS
from random import randint
import voluptuous as vol
import numpy as np

class Rain(AudioReactiveEffect):

    NAME = "Rain"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('intensity', description='Intensity of rain', default = 0.5): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        vol.Optional('lows_colour', description='Colour for low sounds, ie beats', default = 'red'): vol.In(list(COLORS.keys())),
        vol.Optional('mids_colour', description='Colour for mid sounds, ie vocals', default = 'green'): vol.In(list(COLORS.keys())),
        vol.Optional('high_colour', description='Colour for high sounds, ie hi hat', default = 'blue'): vol.In(list(COLORS.keys())),
    })

    def config_updated(self, config):
        self.drop_effectlet = np.load("droplet.npy")
        self._p_filter = self.create_filter(
            alpha_decay = 0.1,
            alpha_rise = 0.50)

    def audio_data_updated(self, data):

        # Calculate the low, mids, and high indexes scaling based on the pixel count
        # lows_idx = int(np.mean(data.melbank_lows()))
        # mids_idx = int(np.mean(data.melbank_mids()))
        # highs_idx = int(np.mean(data.melbank_highs()))

        # Calculate the low, mids, and high indexes scaling based on the pixel count
        lows_idx = int(np.mean(self.pixel_count * data.melbank_lows()) ** self._config['scale'])
        mids_idx = int(np.mean(self.pixel_count * data.melbank_mids()) ** self._config['scale'])
        highs_idx = int(np.mean(self.pixel_count * data.melbank_highs()) ** self._config['scale'])

        # Build the new energy profile based on the mids, highs and lows setting
        # the colors as red, green, and blue channel respectively
        p = np.zeros(np.shape(self.pixels))
        p[:lows_idx, 0] = 255.0
        p[:mids_idx, 1] = 255.0
        p[:highs_idx, 2] = 255.0

        # Apply the melbank data to the gradient curve and update the pixels
        self.pixels = self._p_filter.update(p)
