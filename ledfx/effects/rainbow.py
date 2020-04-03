from ledfx.effects.temporal import TemporalEffect
from ledfx.effects import fill_rainbow
import voluptuous as vol

class RainbowEffect(TemporalEffect):

    NAME = "Rainbow"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('frequency', description='Frequency of the effect curve', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
    })

    _hue = 0.1

    def effect_loop(self):
        hue_delta = self._config['frequency'] / self.pixel_count
        self.pixels = fill_rainbow(self.pixels, self._hue, hue_delta)
        
        self._hue = self._hue + 0.01