from ledfx.effects.audio import AudioReactiveEffect
import voluptuous as vol
import numpy as np

class EnergyAudioEffect(AudioReactiveEffect):

    NAME = "Energy"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 4.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
        vol.Optional('sensitivity', description='Responsiveness to changes in sound', default = 0.7): vol.All(vol.Coerce(float), vol.Range(min=0.2, max=0.99)),
    })

    def config_updated(self, config):
        # scale decay value between 0.1 and 0.2
        decay_sensitivity = (self._config["sensitivity"]-0.2)*0.25
        self._p_filter = self.create_filter(
            alpha_decay = decay_sensitivity,
            alpha_rise = self._config["sensitivity"])

    def audio_data_updated(self, data):

        # Calculate the low, mids, and high indexes scaling based on the pixel count
        lows_idx = int(np.mean(self.pixel_count * data.melbank_lows()))
        mids_idx = int(np.mean(self.pixel_count * data.melbank_mids()))
        highs_idx = int(np.mean(self.pixel_count * data.melbank_highs()))

        # Build the new energy profile based on the mids, highs and lows setting
        # the colors as red, green, and blue channel respectively
        p = np.zeros(np.shape(self.pixels))
        p[:lows_idx, 0] = 255.0
        p[:mids_idx, 1] = 255.0
        p[:highs_idx, 2] = 255.0

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(p)
