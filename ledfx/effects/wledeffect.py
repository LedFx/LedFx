from ledfx.wled import Power
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect
import voluptuous as vol
import numpy as np
import urllib.request as url

class WLEDColorEffect(TemporalEffect):

    NAME = "Power"  
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('wled', description='WLED Power', default = "On"): vol.In(list(Power.keys())),
    })

    def config_updated(self, config):
        self.wled = np.array(POWER[self._config['power']], dtype=float)

#

#    def effect_loop(self):
#        color_array = np.tile(self.color, (self.pixel_count, 1))
#        self.pixels = self.modulate(color_array)



# From **Singlecolor.py**
#from ledfx.color import COLORS
#from ledfx.effects.modulate import ModulateEffect
#from ledfx.effects.temporal import TemporalEffect
#from ledfx.effects.modulate import ModulateEffect
#import voluptuous as vol
#import numpy as np
#
#class SingleColorEffect(TemporalEffect, ModulateEffect):
#
#    NAME = "Single Color"
#    CONFIG_SCHEMA = vol.Schema({
#        vol.Optional('color', description='Color of strip', default = "red"): vol.In(list(COLORS.keys())),
#    })
#
#    def config_updated(self, config):
#        self.color = np.array(COLORS[self._config['color']], dtype=float)
#
#    def effect_loop(self):
#        color_array = np.tile(self.color, (self.pixel_count, 1))
#        self.pixels = self.modulate(color_array)