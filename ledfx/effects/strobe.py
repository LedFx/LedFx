from ledfx.effects.temporal import TemporalEffect
import voluptuous as vol
import numpy as np

class Strobe(TemporalEffect):

    NAME = "Strobe"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('delay', description='Strobe delay', default = 50):  vol.All(vol.Coerce(int), vol.Range(min=1, max=100))
    })

    def config_updated(self, config):
        self.counter = self._config["delay"]
        self.flipflop = True

    def effect_loop(self):
        self.counter -= 1
        if self.counter == 0:
            self.counter += self._config["delay"]
            self.flipflop = not self.flipflop
        if self.flipflop:
            self.pixels = np.full((self.pixel_count, 3), 255)
        else:
            self.pixels = np.zeros((self.pixel_count, 3))

