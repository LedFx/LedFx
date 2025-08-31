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
    CATEGORY = "2D"
    HIDDEN_KEYS = (
        *Twod.HIDDEN_KEYS,  # preserves 'blur', 'mirror', etc.
        "gradient_roll",
        "rotate",
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
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=4.0)),
            vol.Optional(
                "stretch_width",
                description="Stretch effect horizontally",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
            vol.Optional(
                "stretch_height",
                description="Stretch effect vertically",
                default=1.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
            vol.Optional(
                "center_smoothing",
                description="Soften the center point",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=5.0)),
            vol.Optional(
                "idle_speed",  # To avoid static during breaks etc...
                description="Idle motion speed",
                default=1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=3.0)),
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
        self.speedb = 0
        self.offset = 0
        self.power = 0.0

    def audio_data_updated(self, data):
        self.power = getattr(data, self.power_func)() * 2
        self.speedb = self.power * self.speed_multiplier

    def draw(self):
        # Get effect properties
        width = self.r_width
        height = self.r_height
        center_x = (width - 1) / 2
        center_y = (height - 1) / 2
        stretch_w = self._config["stretch_width"]
        stretch_h = self._config["stretch_height"]
        smoothing = self._config["center_smoothing"]

        # Create a coordinate grid
        y_coords, x_coords = np.ogrid[0:height, 0:width]

        # Calculate distance from the center, applying stretching
        # Dividing by stretch values makes the gradient expand further along that axis
        dist = np.sqrt(
            ((x_coords - center_x) / stretch_w) ** 2
            + ((y_coords - center_y) / stretch_h) ** 2
        )

        # Soften the center using a scalar-image Gaussian blur
        if smoothing > 0:
            # Normalize dist to 0-255 for 8-bit image processing
            dist_max = np.max(dist)
            if dist_max > 0:
                dist_normalized = (dist / dist_max * 255).astype(np.uint8)
                dist_img = Image.fromarray(dist_normalized, mode="L").filter(
                    ImageFilter.GaussianBlur(radius=smoothing)
                )
                # Convert back to float and scale back to original range
                dist = np.asarray(dist_img, dtype=np.float32) * (
                    dist_max / 255.0
                )

        max_radius = np.hypot(center_x / stretch_w, center_y / stretch_h)

        if max_radius > 0:
            dist /= max_radius

        dist = np.clip(dist, 0.0, 1.0)

        dist = np.power(dist, 0.9)  # mild smoothing, lower values = softer

        # Wave expansion
        self.speedb += 0.2 * self._config["idle_speed"]
        self.offset += (
            self.speedb / 23
        )  # Arbritary value that looks good when speed_multiplier = 1
        color_points = (
            dist + (self.offset if self._config["invert"] else -self.offset)
        ) % 1.0

        # Get colors from the gradient and reshape to the matrix dimensions
        pixels = self.get_gradient_color_vectorized2d(color_points).astype(
            np.uint8
        )
        self.matrix = Image.fromarray(pixels)
