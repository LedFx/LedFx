from ledfx.effects.legacyAudio import LegacyAudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
import voluptuous as vol
import numpy as np


class LegacyScrollAudioEffect(LegacyAudioReactiveEffect):

    NAME = "Scroll"

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 3.0): vol.Coerce(float),
        vol.Optional('mirror', description='Mirror the effect', default = True): bool,
        vol.Optional('speed', description='Speed of the effect', default = 4):  vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional('decay', description='Decay rate of the scroll', default = 0.95):  vol.All(vol.Coerce(float), vol.Range(min=0.2, max=1.0)),
    })

    def config_updated(self, config):

        # TODO: Determeine how buffers based on the pixels should be
        # allocated. Technically there is no guarentee that the effect
        # is bound to a device while the config gets updated. Might need
        # to move to a model where effects are created for a device and
        # must be destroyed and recreated to be moved to another device.
        self.output = None

    def audio_data_updated(self, data):

        if self.output is None:
            self.output = self.pixels

        # Grab the melbank and scale it up for the effect and clip
        y = data.melbank() ** 2
        y = np.clip(y, 0, 1)

        # Divide the melbank into lows, mids and highs
        lows = y[:len(y) // 6]
        mids = y[len(y) // 6: 2 * len(y) // 5]
        high = y[2 * len(y) // 5:]

        # Compute the value for each range based on the max
        lows_val = (np.array((255,0,0)) * np.max(lows))
        mids_val = (np.array((0,255,0)) * np.max(mids))
        high_val = (np.array((0,0,255)) * np.max(high))

        # Roll the effect and apply the decay
        speed = self.config['speed']
        self.output[speed:,:] = self.output[:-speed,:]
        self.output = (self.output * self.config['decay'])

        # Add in the new color from the signal maxes
        self.output[:speed, 0] = lows_val[0] + mids_val[0] + high_val[0]
        self.output[:speed, 1] = lows_val[1] + mids_val[1] + high_val[1]
        self.output[:speed, 2] = lows_val[2] + mids_val[2] + high_val[2]

        # Set the pixels
        self.pixels = self.output
