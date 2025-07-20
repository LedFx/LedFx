import logging

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.utils import nonlinear_log

_LOGGER = logging.getLogger(__name__)

# div zero protection
epsilon = 1e-6

class Radial2d(Twod):
    NAME = "Radial"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "source_virtual",
                description="The virtual from which to source the 1d pixels",
                default="strip1",
            ): str,
            vol.Optional(
                "edges",
                description="Edges count of mapping",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
            vol.Optional(
                "x_offset",
                description="X offset for center point",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "y_offset",
                description="Y offset for center point",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "twist",
                description="twist that thing",
                default=0,
            ): vol.All(vol.Coerce(float), vol.Range(min=-4, max=4)),
            vol.Optional(
                "polygon",
                description="Use polygonal or radial lobes",
                default=True,
            ): bool,
            vol.Optional(
                "rotation",
                description="static rotation",
                default=0,
            ): vol.All(vol.Coerce(float), vol.Range(min=-0.5, max=0.5)),
            vol.Optional(
                "spin",
                description="Spin the radial effect to the audio impulse",
                default=0.0,
                ): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the spin impulse",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
        }
    )

    def __init__(self, ledfx, config):
        self.bar = 0
        self.virtual = None
        self.spin_total = 0.0
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        self.source_virtual = None
        self.edges = self._config.get("edges")
        self.x_offset = self._config.get("x_offset")
        self.y_offset = self._config.get("y_offset")
        self.twist = self._config.get("twist")
        self.polygon = self._config.get("polygon")
        self.rotation = self._config.get("rotation")
        # bring impulse spin injection into a reasonable range of control
        self.spin = nonlinear_log(self._config.get("spin"), 2) / 10.0
        self.power_func = AudioReactiveEffect.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]

    def do_once(self):
        super().do_once()

    def audio_data_updated(self, data):
        self.impulse = (getattr(data, self.power_func)())
        self.spin_total += self.impulse * self.spin
        self.spin_total %= 1.0  # keep it in [0, 1)

    def draw(self):

        if not self.source_virtual:
            # keep trying to grab the source virtual incase this is a startup race
            self.source_virtual = self._ledfx.virtuals._virtuals.get(
                self._config["source_virtual"]
            )

        if self.source_virtual and hasattr(
            self.source_virtual, "assembled_frame"
        ):
            pixels_in = self.source_virtual.assembled_frame

            width, height = self.matrix.size
            cx = width * self.x_offset
            cy = height * self.y_offset

            # Coordinate grid
            y, x = np.indices((height, width))
            dx = x - cx
            dy = y - cy

            # Base polar coordinates
            radius = np.sqrt(dx**2 + dy**2)

            angle = np.arctan2(dy, dx)
            rotate_and_spin = self.spin_total + self.rotation
            # Apply rotation (0–1 maps to 0–2π clockwise)
            angle -= rotate_and_spin * 2 * np.pi
            angle_norm = (angle + np.pi) / (2 * np.pi)  # [0, 1)

            # Radius modulation based on edges
            if self.edges == 1:
                theta = rotate_and_spin * 2 * np.pi
                ux = np.cos(theta)
                uy = np.sin(theta)
                radius = np.abs(dx * ux + dy * uy)
            elif self.edges == 2:
                modulation = np.sqrt(
                    np.cos(angle) ** 2 + 0.25 * np.sin(angle) ** 2
                )
                radius *= modulation
            elif self.edges >= 3:
                if not self.polygon:
                    modulation = np.cos((self.edges * angle) / 2)
                    radius *= np.abs(modulation)
                else:
                    # Polygonal mask based on angle
                    # Reference: https://iquilezles.org/articles/distfunctions2d/
                    a = np.pi * 2 / self.edges
                    half_a = a / 2
                    angle_mod = (angle + half_a) % a - half_a

                    # maximum radius at this angle for a regular polygon
                    polygon_radius = np.cos(np.pi / self.edges) / np.clip(np.cos(angle_mod), epsilon, None)
                    # apply polygon shaping
                    radius /= polygon_radius

            # Normalize radius
            max_radius = np.max(radius)
            norm_radius = radius / max_radius

            # Combine radius and twist
            twist_index = (norm_radius + self.twist * angle_norm) % 1.0

            # Map to strip
            strip = pixels_in.clip(0, 255).astype(np.uint8)
            N = len(strip)
            indices = (twist_index * N).astype(np.int32)
            indices = np.clip(indices, 0, N - 1)

            # Fill image
            rgb_array = strip[indices]
            image = Image.fromarray(rgb_array, mode="RGB")
            self.matrix.paste(image)
