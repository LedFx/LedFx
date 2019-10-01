from ledfx.wled import powerState, WLEDEffects, WLEDPalette, WLEDSpeed, WLEDIntensity, WLEDBrightness, WLEDHueColor
from ledfx.effects.audio import AudioReactiveEffect
from threading import Thread
import voluptuous as vol
import numpy as np
import urllib.request as url
import time
import logging


class WLEDEffect(AudioReactiveEffect):

    NAME = "Power State"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('Power LED', description='Power of LED', default = True): bool,
        vol.Optional('WLED Effects', description='WLED Effects', default = "Solid"): vol.In(list(WLEDEffects.keys())),
        vol.Optional('Palette', description='Color Palette', default = "Solid"): vol.In(list(WLEDPalette.keys())),
        vol.Optional('Speed', description='Effect Speed', default = "Med"): vol.In(list(WLEDSpeed.keys())),
        vol.Optional('Effect Intensity', description='Effect Intensity', default = "Med"): vol.In(list(WLEDIntensity.keys())),
        vol.Optional('Brightness', description='Brightness', default = "Bright - 80 Percent"): vol.In(list(WLEDBrightness.keys())),
        vol.Optional('Primary Hue Color', description='Primary Hue Color', default = "Red"): vol.In(list(WLEDHueColor.keys())),
    })

    def config_updated(self, config):
        self.wled = np.array(WLEDEffects[self._config['Power LED']], dtype=float)
