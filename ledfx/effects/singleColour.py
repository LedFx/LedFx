from ledfx.color import COLORS, GRADIENTS
from ledfx.effects import Effect
import voluptuous as vol
import numpy as np

class SingleColourEffect(Effect):

    NAME = "Single Colour"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('Colour', description='Amount to blur the effect', default = 4.0): vol.Coerce(float),
        vol.Optional('Brightness', description='Strip Brightness', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
    })

    def config_updated(self, config):
        pass

    def audio_data_updated(self, data):

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

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(p)
