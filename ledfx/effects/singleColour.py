from ledfx.color import COLORS, GRADIENTS
from ledfx.effects import Effect
import voluptuous as vol
import numpy as np

# needs to be it's own class, maybe part of gradienteffect
class SingleColourEffect(Effect):

    NAME = "Single Colour"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('colour', description='Colour of strip', default = "red"): vol.In(list(COLORS.keys())),
    })

    def config_updated(self, config):
        self.p = np.zeros(np.shape(self.pixels))
        for i in range(3):
            self.p[i] = self._config['colour'][i]

    def audio_data_updated(self, data):
        self.pixels = self.p

