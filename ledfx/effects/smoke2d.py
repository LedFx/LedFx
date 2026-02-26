import logging
import random

import numpy as np
import voluptuous as vol
from PIL import Image
from pyfastnoiselite import pyfastnoiselite as fnl

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Smoke2d(Twod, GradientEffect):
    NAME = "Smoke"
    CATEGORY = "Matrix"

    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "background_brightness",
        "background_mode",
        "gradient_roll",
        "test",
    ]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                description="Speed of movement through noise space",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
            vol.Optional(
                "stretch",
                description="Stretch of the noise before mapping to gradient (contrast-like)",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=3.0)),
            vol.Optional(
                "zoom",
                description="Zoom density (higher = denser detail)",
                default=2,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=15)),
            vol.Optional(
                "impulse_decay",
                description="Decay filter applied to the impulse for development",
                default=0.06,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
            vol.Optional(
                "multiplier",
                description="Audio injection multiplier, 0 is none",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=4.0)),
        }
    )

    def __init__(self, ledfx, config):
        self.first_run = True
        self.last_rotate = 0
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)

        self.speed = self._config["speed"]
        self.stretch = self._config["stretch"]
        self.zoom = self._config["zoom"]
        self.multiplier = self._config["multiplier"]

        self.lows_impulse_filter = self.create_filter(
            alpha_decay=self._config["impulse_decay"], alpha_rise=0.99
        )
        self.lows_impulse = 0.0

        if self.last_rotate != self._config["rotate"]:
            self.first_run = True
            self.last_rotate = self._config["rotate"]

    def do_once(self):
        super().do_once()

        if self.first_run:
            self.noise_x = random.random()
            self.noise_y = random.random()
            self.noise_z = random.random()

            self.noise = fnl.FastNoiseLite()
            self.noise.noise_type = fnl.NoiseType.NoiseType_OpenSimplex2
            self.noise.frequency = 0.6

            # Set FBm fractal type and parameters (hardcoded for optimal performance)
            self.noise.fractal_type = fnl.FractalType.FractalType_FBm
            self.noise.fractal_octaves = 4
            self.noise.fractal_lacunarity = 2.0
            self.noise.fractal_gain = 0.5
            self.noise.fractal_weighted_strength = 0.0
            self.noise.fractal_ping_pong_strength = 2.0

            self.first_run = False

        self.scale_x = self.zoom / self.r_width
        self.scale_y = self.zoom / self.r_height

    def audio_data_updated(self, data):
        self.lows_impulse = self.lows_impulse_filter.update(
            data.lows_power(filtered=False) * self.multiplier
        )

    def draw(self):

        # time invariant movement through noise space
        mov = 0.5 * self.speed * self.passed

        self.noise_x += mov
        self.noise_z += mov

        if self.r_height > 1:
            self.noise_y += mov
            bass_x = self.scale_x * self.lows_impulse
            bass_y = self.scale_y * self.lows_impulse
        else:
            bass_x = 0.0
            bass_y = self.scale_y * self.lows_impulse * (1 / self.r_width)

        scale_x = self.scale_x + bass_x
        scale_y = self.scale_y + bass_y

        noise_x0 = self.noise_x - (scale_x * self.r_height / 2)
        noise_y0 = self.noise_y - (scale_y * self.r_width / 2)

        # Build coordinate plane (vectorized)
        x_array = np.linspace(
            noise_x0, noise_x0 + scale_x * self.r_height, self.r_height
        )
        y_array = np.linspace(
            noise_y0, noise_y0 + scale_y * self.r_width, self.r_width
        )

        x_grid, y_grid = np.meshgrid(y_array, x_array, indexing="xy")
        x_flat = x_grid.ravel()
        y_flat = y_grid.ravel()
        z_flat = np.full_like(x_flat, self.noise_z)

        coords = np.stack([x_flat, y_flat, z_flat], axis=0).astype(np.float32)

        noise_flat = self.noise.gen_from_coords(coords)
        noise_2d = noise_flat.reshape(self.r_height, self.r_width)

        # Stretch (contrast) then normalize to 0..1 for gradient lookup
        noise_stretched = noise_2d * self.stretch
        noise_norm = (noise_stretched + 1.0) * 0.5

        # Optional: clamp to avoid any gradient lookup surprises if stretch pushes outside range
        # (kept cheap + safe)
        np.clip(noise_norm, 0.0, 1.0, out=noise_norm)

        color_array = self.get_gradient_color_vectorized2d(noise_norm).astype(
            np.uint8
        )
        self.matrix = Image.fromarray(color_array, "RGB")
