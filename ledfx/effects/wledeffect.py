from ledfx.wled import powerState, WLEDEffects, WLEDPalette, WLEDSpeed, WLEDIntensity, WLEDBrightness, WLEDHueColor
from ledfx.effects.modulate import ModulateEffect
from ledfx.effects.temporal import TemporalEffect
from ledfx.effects.modulate import ModulateEffect
import voluptuous as vol
import numpy as np
import urllib.request as url

class SingleColorEffect(TemporalEffect, ModulateEffect):

    NAME = "Power State"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('Power LED', description='Power of LED', default = "Off"): vol.In(list(powerState.keys())),
        vol.Optional('WLED Effects', description='WLED Effects', default = "Solid"): vol.In(list(WLEDEffects.keys())),
        vol.Optional('Palette', description='Color Palette', default = "Solid"): vol.In(list(WLEDPalette.keys())),
        vol.Optional('Speed', description='Effect Speed', default = "Med"): vol.In(list(WLEDSpeed.keys())),
        vol.Optional('Effect Intensity', description='Effect Intensity', default = "Med"): vol.In(list(WLEDIntensity.keys())),
        vol.Optional('Brightness', description='Brightness', default = "Bright - 80 Percent"): vol.In(list(WLEDBrightness.keys())),
        vol.Optional('Primary Hue Color', description='Primary Hue Color', default = "Red"): vol.In(list(WLEDHueColor.keys())),
    })

    def config_updated(self, config):
        self.wled = np.array(WLEDEffects[self._config['Power LED']], dtype=float)

    def effect_loop(self):
        wled_array = np.tile(self.wled, (self.pixel_count, 1))
        self.pixels = self.modulate(wled_array)


#    CONFIG_SCHEMA = vol.Schema({
#        vol.Optional('gradient_name', description='Preset gradient name', default = 'Spectral'): vol.In(list(GRADIENTS.keys())),
#        vol.Optional('gradient_roll', description='Amount to shift the gradient', default = 0): vol.Coerce(int),
#       vol.Optional('gradient_method', description='Function used to generate gradient', default = 'cubic_ease'): vol.In(["cubic_ease", "bezier"]),
#    })
