import logging

import numpy as np
import PIL.Image as Image
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# inspired by 2D Hiphotic effect in WLED
# https://github.com/Aircoookie/WLED/blob/main/wled00/FX.cp


class Plasmawled(Twod, GradientEffect):
    NAME = "PlasmaWled2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["background_color", "gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "speed",
                description="Speed multiplier",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "stretch_horizontal",
                description="Smaller is less block in horizontal dimension",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "stretch_vertical",
                description="Smaller is less block in vertical dimension",
                default=128,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "size_multiplication",
                description="Sound to size multiplier",
                default=0.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "speed_multiplication",
                description="Sound to speed multiplier",
                default=0.4,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        # all trig calculations are in 8 bit space 0 - 255 so lets create lookup tables
        self.sine_lookup_table = np.array(
            [
                (np.sin(theta * (2.0 * np.pi / 255.0)) * 127.5 + 127.5)
                for theta in range(256)
            ],
            dtype=int,
        )
        self.sine_lookup_table = np.clip(self.sine_lookup_table, 0, 255)
        self.cosine_lookup_table = np.array(
            [
                (np.cos(theta * (2.0 * np.pi / 255.0)) * 127.5 + 127.5)
                for theta in range(256)
            ],
            dtype=int,
        )
        self.cosine_lookup_table = np.clip(self.cosine_lookup_table, 0, 255)

    def sin8(self, theta):
        # Convert theta to a NumPy array of unsigned 8-bit integers for vectorized operations
        return self.sine_lookup_table[np.uint8(theta)]

    def cos8(self, theta):
        # Convert theta to a NumPy array of unsigned 8-bit integers for vectorized operations
        return self.cosine_lookup_table[np.uint8(theta)]

    def config_updated(self, config):
        super().config_updated(config)
        self.configured_speed = self._config["speed"]
        self.stretch_horizontal = self._config["stretch_horizontal"]
        self.stretch_vertical = self._config["stretch_vertical"]
        self.speed_multiplication = self._config["speed_multiplication"]
        self.size_multiplication = self._config["size_multiplication"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.speedb = 0
        self.sizeb = 0
        self.time_modifier = 0

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.sizeb = self.power * self.size_multiplication
        self.speedb = self.power * self.speed_multiplication

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        # create data, a numpy array of shape (self.r_width, self.r_height, 1)
        data = np.zeros((self.r_height, self.r_width), dtype=np.uint8)

        if self.speed_multiplication > 0.0:
            self.time_modifier += self.speedb
            time_val = int(self.time_modifier * 1000)
        else:
            time_val = int(self.current_time * 1000)

        a = time_val / (self.configured_speed + 1)

        h_stretch = max(
            0.01,
            self.stretch_horizontal
            - (self.sizeb * self.stretch_horizontal / 3),
        )
        v_stretch = max(
            0.01,
            self.stretch_vertical - (self.sizeb * self.stretch_vertical / 3),
        )

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
        sin_cos_indices = (
            self.cosine_lookup_table[np.uint8(x_vals)] + a
        ) % 256
        sin_indices = (self.sine_lookup_table[np.uint8(y_vals)] + a) % 256

        # Use advanced indexing to access lookup table values
        data = self.sin8(sin_cos_indices + sin_indices) / 255.0

        color_mapped_plasma = self.get_gradient_color_vectorized(data).astype(
            np.uint8
        )

        self.matrix = Image.fromarray(color_mapped_plasma, "RGB")
