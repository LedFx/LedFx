import numpy as np
import voluptuous as vol
import time

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect

#Second attempt at reimplementing https://gist.github.com/kriegsman/756ea6dcae8e30845b5a / twinklefox_base from https://github.com/Aircoookie/WLED/blob/main/wled00/FX.cpp
#in a manner suited to a machine with more RAM and CPU than a microcontroller/numpy
class Twinklefox2(AudioReactiveEffect, HSVEffect):
    NAME = "Twinklefox v2"
    CATEGORY = "Atmospheric"

    _power_funcs = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Effect Speed",
                default=0.25,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "phase_peak",
                description="Phase peak",
                default=0.33,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "density",
                description="Twinkle density",
                default=0.30,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "speed_reac",
                description="Audio Reactivity (speed)",
                default=0.2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
            vol.Optional(
                "dens_reac",
                description="Audio Reactivity (density)",
                default=0.8,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.00001, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.last_time = time.time_ns()
        self.speed_modifier = 1.0 + 2.0*np.random.rand(self.pixel_count)
        self.phase = np.random.rand(self.pixel_count)/self._config["density"]
        self.hue = np.random.rand(self.pixel_count)

    def config_updated(self, config):
        self._power = 0
        self._power_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.2
        )

        self.clk_div = np.power(2, 7 - 6*self._config["speed"])
        self.trig_thresh = (1.0/self.config["density"]) - 1.0
        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        self._power = self._power_filter.update(
            getattr(data, self.power_func)()
        )

    def array_sawtooth(self, a):
        pk = self.config["phase_peak"] #I don't want to type this over and over again...
        return np.where(a < pk, a/pk, 1.0-(a-pk)/(1-pk))

    def render_hsv(self):
        now_ns = time.time_ns()
        dt = (now_ns - self.last_time)/1.0e6 #Original twinklefox ticks in milliseconds

        dt *= 1.0 + self._power*np.power(2,self._config["speed_reac"]*7-1)
        #Rewrite twinklefox's clock increase in a different manner.
        self.phase += self.speed_modifier*dt/(self.clk_div*256.0)
        self.last_time = now_ns


        #Get brightness from our current phase if < 1.0
        bright = self.array_sawtooth(np.where(self.phase < 1.0, self.phase, 0))

        #Determine whether to trigger a new twinkle, and if so, choose a new random hue and speed mult, and reset phase to zero
        #Unlike original twinklefox, the deadtime for any pixel is exactly (1-density) - we rely on the speed multiplier to hide that
        #from the viewer
        trig_idxs = (self.phase > 1.0 + (1.0-self._config["dens_reac"]*self._power)*self.trig_thresh).nonzero()[0] #Can lows_power ever be > 1.0?  I don't think so?
        numup = len(trig_idxs)

        if(numup > 0):
            #reset phase to 0 when we trigger
            #This is inefficient/wasteful as hell, need to rework this once it seems to be mostly OK.
            self.phase[trig_idxs] = 0
            self.hue[trig_idxs] = np.random.rand(numup)
            self.speed_modifier[trig_idxs] = 1.0+2.0*np.random.rand(numup)

        self.hsv_array[:, 0] = self.hue
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = bright