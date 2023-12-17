import time

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.hsv_effect import HSVEffect


# Inspired by https://gist.github.com/kriegsman/756ea6dcae8e30845b5a / twinklefox_base from https://github.com/Aircoookie/WLED/blob/main/wled00/FX.cpp
# rewritten in a manner suited to a machine with numpy and more RAM and CPU than a microcontroller
class Twinklefox(AudioReactiveEffect, HSVEffect):
    NAME = "Twinklefox"
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

        # Instead of generating our random values from a deterministic PRNG on every run to save RAM, we've got lots of RAM, so maintain state variables for each pixel
        # and assign fully random values to them all
        self.speed_modifier = 1.0 + 2.0 * np.random.rand(self.pixel_count) # Initialize with a random speed modifier, otherwise the effect starts out too uniform
        self.phase = np.random.rand(self.pixel_count) / self._config["density"] # Also a random portion of the phase cycle
        self.hue = np.random.rand(self.pixel_count) # Random hue

    def config_updated(self, config):
        self._power = 0
        self._power_filter = self.create_filter(
            alpha_decay=0.05, alpha_rise=0.2
        )

        # Original twinklefox's clock divisor is not a linear function of speed.
        # This is chosen to have a slightly larger range of achievable values (2 to 128 vs. 3 to 72)
        # with the same divisor (16) when speed is 0.5 as when original twinklefox is set to the default of 127
        self.clk_div = np.power(2, 7 - 6 * self._config["speed"])

        # Trigger threshold is the additional dead time after the lit portion (betwen 0.0 and 1.0) of the phase sequence.  Some of the reactivity math is a little easier when
        # represented this way as opposed to the absolute phase value
        self.trig_thresh = (1.0 / self.config["density"]) - 1.0

        self.power_func = self._power_funcs[self._config["frequency_range"]]

    def audio_data_updated(self, data):
        self._power = self._power_filter.update(
            getattr(data, self.power_func)()
        )

    def array_sawtooth(self, a):
        pk = self.config[
            "phase_peak"
        ]  # I don't want to type this over and over again...
        return np.where(a < pk, a / pk, 1.0 - (a - pk) / (1 - pk))

    def render_hsv(self):
        now_ns = time.time_ns()
        dt = (
            now_ns - self.last_time
        ) / 1.0e6  # Original twinklefox ticks in milliseconds

        # Nonlinear reactivity seems to give a lot more flexibiltiy here without making the slider do almost nothing in certain parts of its range
        dt *= 1.0 + self._power * np.power(
            2, self._config["speed_reac"] * 7 - 1
        )

        # If this clock handling looks strange, it is intended to result in similar timing behavior to
        # twingklefox's fastcycle8 variable for representing the phase within a given LED's sequence.
        # However instead of going from 0 to 256, we go from 0 to 1, and represent "off" pixels/dead time
        # as phase values greater than 1 instead of having a separate random decision of whether or not to light
        # at all for a given cycle.  This actually seems to visually work nicer than Twinklefox which can sometimes have
        # multiple repeats with no space, or long unlit intervals.
        self.phase += self.speed_modifier * dt / (self.clk_div * 256.0)
        self.last_time = now_ns

        # Get brightness from our current phase if < 1.0
        # Phase peak of 0.33 corresponds to traditional Twinklefox, 0 corresponds to Twinklecat.
        # Instead of a bool, allow arbitrarily varying the sawtooth peak
        bright = self.array_sawtooth(np.where(self.phase < 1.0, self.phase, 0))

        # Determine whether to trigger a new twinkle, and if so, choose a new random hue and speed mult, and reset phase to zero
        # Unlike original twinklefox, the deadtime for any pixel without reactivity is exactly 1.0/density - 1.0 - we rely on the speed multiplier to hide that
        # from the viewer
        # With full reactivity and a power input of 1, the deadtime is reduced to 0 and any unlit pixels will trigger
        # This does have the disadvantage of syncing all of the activated pixel phases to 0, so at the end of a reactivity response
        # there will be an above average number of unlit pixels.  However that gives more room to react to the next power spike so it is probably OK as is.
        # As a performance optimization, we find the indices of pixels that need a relight trigger.  In normal operation this will often be only 1 per update
        # at most, but a power spike will cause multiple relights in a single update
        trig_idxs = (
            self.phase
            > 1.0
            + (1.0 - self._config["dens_reac"] * self._power)
            * self.trig_thresh
        ).nonzero()[
            0
        ]  # Can lows_power ever be > 1.0?  I don't think so?
        numup = len(trig_idxs)

        if numup > 0:
            # reset phase to 0 when we trigger
            self.phase[trig_idxs] = 0
            self.hue[trig_idxs] = np.random.rand(numup)
            self.speed_modifier[trig_idxs] = 1.0 + 2.0 * np.random.rand(numup)

        self.hsv_array[:, 0] = self.hue
        self.hsv_array[:, 1] = 1
        self.hsv_array[:, 2] = bright
