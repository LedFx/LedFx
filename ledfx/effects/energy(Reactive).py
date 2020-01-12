from ledfx.effects.audio import AudioReactiveEffect, AUDIO_CHANNEL
import voluptuous as vol
import numpy as np

class EnergyAudioEffect(AudioReactiveEffect):

    NAME = "Energy"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('Audio_Channel', description='Audio Channel to use as import source', default = "Mono"): vol.In(list(AUDIO_CHANNEL.keys())),
        vol.Optional('blur', description='Amount to blur the effect', default = 4.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
        vol.Optional('scale_low', description='Sensitivity for high frequencies', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
        vol.Optional('scale_mid', description='Sensitivity for mid frequencies', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
        vol.Optional('scale_high', description='Sensitivity for high frequencies', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0))
    })

    def config_updated(self, config):
        self._p_filter = self.create_filter(
            alpha_decay = 0.1,
            alpha_rise = 0.50)

    def audio_data_updated(self, data):

        # Calculate the low, mids, and high indexes scaling based on the pixel count
        lows_idx = int(np.mean(self.pixel_count * data.melbank_lows()) ** self._config['scale_low'])
        mids_idx = int(np.mean(self.pixel_count * data.melbank_mids()) ** self._config['scale_mid'])
        highs_idx = int(np.mean(self.pixel_count * data.melbank_highs()) ** self._config['scale_high'])

        # Build the new energy profile based on the mids, highs and lows setting
        # the colors as red, green, and blue channel respectively
        p = np.zeros(np.shape(self.pixels))
        p[:lows_idx, 0] = 255.0
        p[:mids_idx, 1] = 255.0
        p[:highs_idx, 2] = 255.0

        # Filter and update the pixel values
        self.pixels = self._p_filter.update(p)
