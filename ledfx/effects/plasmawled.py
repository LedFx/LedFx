import logging
import timeit

import numpy as np
import voluptuous as vol
import PIL.Image as Image

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# inspired by 2D Hiphotic effect in WLED
# https://github.com/Aircoookie/WLED/blob/main/wled00/FX.cp

class Plasmawled(Twod, GradientEffect):
    NAME = "PlasmaWled2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    start_time = timeit.default_timer()

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
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(_power_funcs.keys())),
            vol.Optional(
                "speed",
                description="Speed multiplier",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "h_stretch",
                description="Smaller is less block in horizontal dimension",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "v_stretch",
                description="Smaller is less block in vertical dimension",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "size x",
                description="Sound to size multiplier",
                default=0.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "speed x",
                description="Sound to speed multiplier",
                default=0.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),

        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        # all trig calculations are in 8 bit space 0 - 255 so lets create lookup tables
        self.sine_lookup_table = np.array(
            [(np.sin(theta * (2.0 * np.pi / 255.0)) * 127.5 + 127.5) for theta
             in range(256)], dtype=int)
        self.sine_lookup_table = np.clip(self.sine_lookup_table, 0, 255)
        self.cosine_lookup_table = np.array(
            [(np.cos(theta * (2.0 * np.pi / 255.0)) * 127.5 + 127.5) for theta
                in range(256)], dtype=int)
        self.cosine_lookup_table = np.clip(self.cosine_lookup_table, 0, 255)

    def sin8(self, theta):
        # Convert theta to a NumPy array of unsigned 8-bit integers for vectorized operations
        return self.sine_lookup_table[np.uint8(theta)]

    def cos8(self, theta):
        # Convert theta to a NumPy array of unsigned 8-bit integers for vectorized operations
        return self.cosine_lookup_table[np.uint8(theta)]

    def config_updated(self, config):
        super().config_updated(config)
        self._speed = self._config["speed"]
        self.h_stretch = self._config["h_stretch"]
        self.v_stretch = self._config["v_stretch"]
        self.speedx = self._config["speed x"]
        self.sizex = self._config["size x"]
        self.power_func = self._power_funcs[self._config["frequency_range"]]
        self.speedb = 0
        self.sizeb = 0
        self.time = 0

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.sizeb = self.power * self.sizex
        self.speedb = self.power * self.speedx

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        # create data, a numpy array of shape (self.r_width, self.r_height, 1)
        data = np.zeros((self.r_height, self.r_width), dtype=np.uint8)

        if self.speedx > 0.0:
            self.time += self.speedb
            time_val = int(self.time * 1000)
        else:
            time_val = int((timeit.default_timer() - self.start_time) * 1000)

        a = time_val / (self._speed + 1)

        h_stretch = max(0.01, self.h_stretch - (self.sizeb * self.h_stretch / 3))
        v_stretch = max(0.01, self.v_stretch - (self.sizeb * self.v_stretch / 3))

        # original python code was as commented below
        # kudo's to chatgpt for working through vectorisation
        # reduce from cost on 128 x 128 from 40 ms to 1.5 ms

        # for x in range(self.r_height):
        #     for y in range(self.r_width):
        #         data[x][y] = self.sin8(self.cos8( x * self.h_stretch/16 + a / 3) + self.sin8(y * self.v_stretch/16 + a / 4) + a)

        x_indices = np.arange(self.r_height).reshape(-1, 1)  # Column vector
        y_indices = np.arange(self.r_width)  # Row vector

        x_vals = x_indices * h_stretch / 16 + a / 3
        y_vals = y_indices * v_stretch / 16 + a / 4

        # Use vectorized operations to compute indices for lookup tables
        sin_cos_indices = (self.cosine_lookup_table[np.uint8(x_vals)] + a) % 256
        sin_indices = (self.sine_lookup_table[np.uint8(y_vals)] + a) % 256

        # Use advanced indexing to access lookup table values
        data = self.sin8(sin_cos_indices + sin_indices) / 255.0

        color_mapped_plasma = self.get_gradient_color_vectorized(data).astype(np.uint8)

        self.matrix = Image.fromarray(color_mapped_plasma, 'RGB')

        self.roll_gradient()
