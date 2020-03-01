from ledfx.effects.audio import AudioReactiveEffect
from ledfx.color import COLORS
import voluptuous as vol
import numpy as np

class Strobe(AudioReactiveEffect):

    NAME = "Strobe"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('color', description='Strobe colour', default = "white"): vol.In(list(COLORS.keys())),
        vol.Optional('frequency', description='Strobe frequency', default = "1/16 (◉o◉ )"): vol.In(list(["1/2 (.-. )", "1/4 (.o. )", "1/8 (◉◡◉ )", "1/16 (◉﹏◉ )", "1/32 (⊙▃⊙ )"]))
    })

    def config_updated(self, config):
        self.color = np.array(COLORS[self._config['color']], dtype=float)
        self.mappings = {"1/2 (.-. )": 2,
                         "1/4 (.o. )": 4,
                         "1/8 (◉◡◉ )": 8,
                         "1/16 (◉﹏◉ )": 16,
                         "1/32 (⊙▃⊙ )": 32}


    def audio_data_updated(self, data):
        beat_oscillator, beat_now = data.oscillator()
        f = self.mappings[self._config["frequency"]]
        brightness = (-beat_oscillator % (2 / f)) * (f / 2)
        color_array = np.tile(self.color*brightness, (self.pixel_count, 1))
        self.pixels = color_array

