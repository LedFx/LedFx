import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.temporal import TemporalEffect


class ChunchunEffect(TemporalEffect, GradientEffect):
    """
    Birds flying along the strip in a sinusoidal pattern.
    Ported from WLED effect FX_MODE_CHUNCHUN (effect #111).
    """

    NAME = "Chunchun"
    CATEGORY = "Non-Reactive"
    HIDDEN_KEYS = ["gradient_roll"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "speed",
                default=1.0,
                description="Speed of bird movement",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
            vol.Optional(
                "intensity",
                default=0.5,
                description="Spread of birds along the sine wave",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "bg_color",
                default="#000000",
                description="Background color",
            ): validate_color,
        }
    )

    def config_updated(self, config):
        self._gradient_curve = None
        self._bg_color = np.array(
            parse_color(self._config["bg_color"]), dtype=float
        )

    def on_activate(self, pixel_count):
        self._counter = 0.0

    def effect_loop(self):
        # Advance the sine-wave counter. TemporalEffect scales loop rate by
        # speed, so a fixed increment here gives speed-proportional animation.
        self._counter += 0.05

        num_birds = 2 + self.pixel_count // 8

        # total angular spread across all birds: 0 → tightly clustered, 1 → full sine cycle
        total_spread = self._config["intensity"] * 2 * np.pi
        span = total_spread / num_birds

        pixels = np.tile(self._bg_color, (self.pixel_count, 1))

        for i in range(num_birds):
            angle = self._counter - i * span
            # sin maps [-1,1] → position maps [0,1]
            position = (np.sin(angle) + 1.0) / 2.0
            pixel_idx = int(position * (self.pixel_count - 1))
            color = self.get_gradient_color(i / num_birds)
            pixels[pixel_idx] = color

        self.pixels = pixels
