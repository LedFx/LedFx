import numpy as np
import voluptuous as vol
from PIL import Image, ImageFilter

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod


class Concentric(Twod, GradientEffect):
    """
    A 2D effect that renders concentric circles expanding from the center
    on the beat. The colors of the circles are determined by a gradient.
    """

    NAME = "Concentric"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = (
        *Twod.HIDDEN_KEYS,  # preserves 'blur', 'mirror', etc.
        "gradient_roll",
        "background_color",
        "test",
    )

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "frequency_range",
                description="Frequency range for beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "invert",
                description="Invert propagation direction",
                default=False,
            ): bool,
            vol.Optional(
                "speed_multiplier",
                description="Audio to speed multiplier",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "gradient_scale",
                description="Scales the gradient",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
            vol.Optional(
                "stretch_height",
                description="Stretches the gradient vertically",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
            vol.Optional(
                "center_smoothing",
                description="Soften the center point",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
            vol.Optional(
                "idle_speed",  # To avoid static during breaks etc...
                description="Idle motion speed",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1)),
        }
    )

    def on_activate(self, pixel_count):
        super().on_activate(pixel_count)

    def config_updated(self, config):
        super().config_updated(config)
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.speed_multiplier = self._config["speed_multiplier"]
        self.gscale = self._config["gradient_scale"]
        self.h_stretch = self._config["stretch_height"]
        self.smoothing = self._config["center_smoothing"]
        self.idle_speed = self._config["idle_speed"]
        self.invert = self._config["invert"]
        self.offset = 0
        self.power = 0.0

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)()
        self.power *= self.speed_multiplier * 2

    # Pre-calculate distance Grid
    def do_once(self):
        super().do_once()
        self.center_x = (self.r_width - 1) / 2
        self.center_y = (self.r_height - 1) / 2
        self.y_coords, self.x_coords = np.ogrid[
            0 : self.r_height, 0 : self.r_width
        ]
        # Create a coordinate grid
        # Calculate distance from the center, applying stretching
        # Dividing by stretch values makes the gradient expand further along that axis

        dist = np.sqrt(
            ((self.x_coords - self.center_x) / self.gscale) ** 2
            + ((self.y_coords - self.center_y) / self.gscale / self.h_stretch)
            ** 2
        )
        # Soften the center using a scalar-image Gaussian blur
        if self.smoothing > 0:
            # Normalize dist to 0-255 for 8-bit image processing
            dist_max = np.max(dist)
            if dist_max > 0:
                dist_normalized = (dist / dist_max * 255).astype(np.uint8)
                dist_img = Image.fromarray(dist_normalized, mode="L").filter(
                    ImageFilter.GaussianBlur(radius=self.smoothing)
                )
                # Convert back to float and scale back to original range
                dist = np.asarray(dist_img, dtype=np.float32) * (
                    dist_max / 255.0
                )

        max_radius = np.hypot(self.center_x, self.center_y / self.h_stretch)
        if max_radius > 0:
            dist /= max_radius
        dist = np.clip(dist, 0.0, 1.0)

        self.dist = np.power(
            dist, 0.9
        )  # mild smoothing, lower values = softer

    def draw(self):
        # Wave expansion
        self.offset += (self.power + self.idle_speed) * self.passed
        self.offset %= 1.0
        color_points = (
            self.dist + (self.offset if self.invert else -self.offset)
        ) % 1.0

        # Get colors from the gradient and reshape to the matrix dimensions
        pixels = self.get_gradient_color_vectorized2d(color_points).astype(
            np.uint8
        )
        self.matrix = Image.fromarray(pixels)
