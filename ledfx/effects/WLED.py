from ledfx.color import COLORS
from ledfx.effects.temporal import TemporalEffect
import voluptuous as vol
import numpy as np

class WLEDColorEffect(TemporalEffect):

    NAME = "WLED"  
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('Palette', description='WLED FastLED Palette', default = "Solid"): vol.In(list(PALETTE.keys())),
    })

    def config_updated(self, config):
        self.color = np.array(PALETTE[self._config['Palette']], dtype=float)

#    def effect_loop(self):
#        color_array = np.tile(self.color, (self.pixel_count, 1))
#        self.pixels = self.modulate(color_array)

from collections import namedtuple

Power = {
    'On': RGB(0, 255, 255),#http://192.168.1.102/win&T=0
    'Off': RGB(0, 0, 0),#http://192.168.1.102/win&T=1
    'Toggle': RGB(0, 0, 255),#http://192.168.1.102/win&T=2
}

WLEDEFFECTS = {
    'Solid': #http://192.168.1.102/win&FX=0
    'Blink': RGB(0, 0, 0),#1
    'Breathe': RGB(0, 0, 255),#2
    'Wipe': RGB(139, 69, 19),
    'WipeRandom': RGB(255, 215, 0),
    'green': RGB(0, 255, 0),
    'RandomColors': RGB(0, 255, 50),
    'Sweep': RGB(255, 105, 180),
    'Dynamic': RGB(173, 216, 230),
    'Colorloop': RGB(152, 251, 152),
    'Rainbow': RGB(255, 182, 193),
    'Scan': RGB(255, 255, 224),
    'DualScan': RGB(255, 0, 255),
    'Fade': RGB(128, 0, 0),
    'Chase': RGB(189, 252, 201),
    'ChaseRainbow': RGB(0, 0, 128),
    'Running': RGB(85, 107, 47),
    'Saw': RGB(34, 139, 34),
    'Twinkle': RGB(255, 128, 0),
    'Dissolve': RGB(255, 69, 0),
    'DissolveRnd': RGB(255, 0, 178),
    'Sparkle': RGB(255, 100,100),
    'Strobe': RGB(221, 160, 221),
    'Sparkle+': RGB(128, 0, 128),
    'Strobe Rainbow': RGB(255, 0, 0),
    'Mega Strobe': RGB(65, 105, 225),
    'Blink Rainbow': RGB(94, 38, 18),
    'Android': RGB(135, 206, 235),
    'Chase': RGB(0, 255, 127),
    'Chase Random': RGB(70, 130, 180),
    'Chase Rainbow': RGB(210, 180, 140),
    'Chase Flash': RGB(0, 128, 128),
    'Rainbow Runner': RGB(64, 224, 208),
    'Traffic Light': RGB(0, 199, 140),
    'Sweep Random': RGB(238, 130, 238),
    'Running 2': RGB(208, 32, 144),
    'Red & Blue': RGB(255, 255, 255),
    'Stream': RGB(255, 255, 0),
    'Scanner': RGB(34, 139, 34),
    'Lighthouse': RGB(255, 128, 0),
    'Fireworks': RGB(255, 69, 0),
    'Rain': RGB(255, 0, 178),
    'Merry Christmas': RGB(255, 100,100),
    'Fire Flicker': RGB(221, 160, 221),
    'Gradient': RGB(128, 0, 128),
    'Loading': RGB(255, 0, 0),
    'In Out': RGB(65, 105, 225),
    'In In': RGB(94, 38, 18),
    'Out Out': RGB(135, 206, 235),
    'Out In': RGB(0, 255, 127),
    'Circus': RGB(70, 130, 180),
    'Halloween': RGB(210, 180, 140),
    'Tri Chase': RGB(0, 128, 128),
    'Tri Wipe': RGB(64, 224, 208),
    'Tri Fade': RGB(0, 199, 140),
    'Lightning': RGB(238, 130, 238),
    'ICU': RGB(208, 32, 144),
    'Multi Comet': RGB(255, 255, 255),
    'Dual Scanner': RGB(255, 255, 0),
    'Stream 2': RGB(135, 206, 235),
    'Oscillate': RGB(0, 255, 127),
    'Pride 2015': RGB(70, 130, 180),
    'Juggle': RGB(210, 180, 140),
    'Palette': RGB(0, 128, 128),
    'Fire 2012': RGB(64, 224, 208),
    'Colorwaves': RGB(0, 199, 140),
    'Fill Noise': RGB(238, 130, 238),
    'Noise 1': RGB(208, 32, 144),
    'Noise 2': RGB(255, 255, 255),
    'Noise 3': RGB(208, 32, 144),
    'Noise 4': RGB(255, 255, 255),
    'Colortwinkle': RGB(255, 255, 0),
    'Lake': RGB(208, 32, 144),
    'Meteor': RGB(255, 255, 255),
    'Smooth Meteor': RGB(208, 32, 144),
    'Railway': RGB(255, 255, 255),
    'Ripple': RGB(255, 255, 0),
    'Twinklefox': RGB(255, 255, 0),
}

WLEDPALETTE = {
    'Default': RGB(0, 255, 255),#http://192.168.1.102/win&FP=0
    'Random Cycle': RGB(0, 0, 0),#1
    'Primary color': RGB(0, 0, 255),#2
    'Based on primary': RGB(139, 69, 19),
    'Set colors': RGB(255, 215, 0),
    'Based on set': RGB(0, 255, 0),
    'Party': RGB(0, 255, 50),
    'Cloud': RGB(255, 105, 180),
    'Lava': RGB(173, 216, 230),
    'Ocean': RGB(152, 251, 152),
    'Forest': RGB(255, 182, 193),
    'Rainbow': RGB(255, 255, 224),
    'Rainbow bands': RGB(255, 0, 255),
    'Sunset': RGB(128, 0, 0),
    'Rivendell': RGB(189, 252, 201),
    'Breeze': RGB(0, 0, 128),
    'Red & Blue': RGB(85, 107, 47),
    'Yellowout': RGB(34, 139, 34),
    'Analoguous': RGB(255, 128, 0),
    'Splash': RGB(255, 69, 0),
    'Pastel': RGB(255, 0, 178),
    'Sunset 2': RGB(255, 100,100),
    'Beech': RGB(221, 160, 221),
    'Vintage': RGB(128, 0, 128),
    'Departure': RGB(255, 0, 0),
    'Landscape': RGB(65, 105, 225),
    'Beach': RGB(94, 38, 18),
    'Android': RGB(135, 206, 235),
    'Sherbet': RGB(0, 255, 127),
    'Hult': RGB(70, 130, 180),
    'Hult 64': RGB(210, 180, 140),
    'Drywet': RGB(0, 128, 128),
    'Jul': RGB(64, 224, 208),
    'Grintage': RGB(0, 199, 140),
    'Rewhi': RGB(238, 130, 238),
    'Fire': RGB(208, 32, 144),
    'Icefire': RGB(255, 255, 255),
    'Cyane': RGB(255, 255, 0),
    'Light Pink': RGB(34, 139, 34),
    'Autumn': RGB(255, 128, 0),
    'Magenta': RGB(255, 69, 0),
    'Magred': RGB(255, 0, 178),
    'Yelmag': RGB(255, 100,100),
    'Yelblu': RGB(221, 160, 221),
    'Orange & Teal': RGB(128, 0, 128),
    'Tiamat': RGB(255, 0, 0),
    'April Night': RGB(65, 105, 225),
}

WLEDSEPEED = {
    'Slow': RGB(0, 255, 255),#http://192.168.1.102/win&FP=0
    'Med-Slow': RGB(0, 0, 0),#1
    'Med': RGB(0, 0, 255),#
    'Med-Fast': RGB(0, 0, 0),#1
    'Fast': RGB(0, 0, 255),#
    'Fastest': RGB(0, 0, 255),#
}

WLEDINTENSITY = {
    'Slow': RGB(0, 255, 255),#http://192.168.1.102/win&FP=0
    'Med-Slow': RGB(0, 0, 0),#1
    'Med': RGB(0, 0, 255),#
    'Med-Fast': RGB(0, 0, 0),#1
    'Fast': RGB(0, 0, 255),#
    'Fastest': RGB(0, 0, 255),#
}

WLEDBRIGHTNESS = {
    'Low - 10 Percent': RGB(0, 255, 255),#http://192.168.1.102/win&A=25
    'A Little- 25 Percent': RGB(0, 0, 0),#http://192.168.1.102/win&A=64
    'Med - 50 Percent': RGB(0, 0, 255),#http://192.168.1.102/win&A=128
    'Bright - 80 Percent': RGB(0, 0, 255),#http://192.168.1.102/win&A=204
    'Brightest - 100 Percent': RGB(0, 0, 255),#http://192.168.1.102/win&A=255
}

WLEDPRIMARYCOLOR = {
    'Red': #http://192.168.1.102/win&HU=255
    'Blue': #http://192.168.1.102/win&HU=255
    'Green': #http://192.168.1.102/win&HU=255
}