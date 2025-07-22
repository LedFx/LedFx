import logging

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.twod import Twod
from ledfx.utils import nonlinear_log
from ledfx.virtuals import virtual_id_validator

_LOGGER = logging.getLogger(__name__)

# div zero protection
epsilon = 1e-6


class Radial2d(Twod):
    NAME = "Radial"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test", "background_color"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "source_virtual",
                description="The virtual from which to source the 1d pixels",
                default="strip1",
            ): virtual_id_validator,
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
            vol.Optional(
                "star",
                description="pull polygon points to star shape",
                default=0.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        self.bar = 0
        self.virtual = None
        self.spin_total = 0.0
        self.max_radius = None
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
        self.star = self._config.get("star")

    def audio_data_updated(self, data):
        self.impulse = getattr(data, self.power_func)()
        self.spin_total += self.impulse * self.spin
        self.spin_total %= 1.0  # keep it in [0, 1)

    def do_once(self):
        super().do_once()

        # Compute center based on normalized offsets
        self.cx = self.r_width * self.x_offset
        self.cy = self.r_height * self.y_offset

        # Create fixed coordinate grid
        y, x = np.indices((self.r_height, self.r_width))
        self.dx = x - self.cx
        self.dy = y - self.cy

        # Precompute base radius from center
        self.radius_base = np.sqrt(self.dx**2 + self.dy**2)

        # Compute maximum radius (used for normalization)
        self.max_radius = np.max(self.radius_base)

    def draw(self):

        if not self.source_virtual:
            # Try to fetch source_virtual (e.g. on startup race)
            self.source_virtual = self._ledfx.virtuals._virtuals.get(
                self._config["source_virtual"]
            )

        if self.source_virtual and hasattr(
            self.source_virtual, "assembled_frame"
        ):
            pixels_in = self.source_virtual.assembled_frame

            # Use precomputed geometry
            dx = self.dx
            dy = self.dy
            radius = self.radius_base.copy()

            # Compute rotation + spin as one angle in radians
            rotate_and_spin = (self.spin_total + self.rotation) % 1.0
            theta = rotate_and_spin * 2 * np.pi

            # Angle and rotation
            angle = np.arctan2(dy, dx)
            angle -= theta
            angle_norm = (angle + np.pi) / (2 * np.pi)  # [0, 1)

            # Radius modulation based on edges
            if self.edges == 1:
                ux = np.cos(theta)
                uy = np.sin(theta)
                radius = np.abs(dx * ux + dy * uy)
            elif self.edges == 2:
                cos_angle = np.cos(angle)
                sin_angle = np.sin(angle)
                modulation = np.sqrt(cos_angle**2 + 0.25 * sin_angle**2)
                radius *= modulation
            elif self.edges >= 3:
                if not self.polygon:
                    modulation = np.cos((self.edges * angle) / 2)
                    radius *= np.abs(modulation)
                else:
                    a = np.pi * 2 / self.edges
                    half_a = a / 2
                    angle_mod = (angle + half_a) % a - half_a
                    polygon_radius = np.cos(np.pi / self.edges) / np.clip(
                        np.cos(angle_mod), epsilon, None
                    )

                    # Optional starburst shaping
                    if self.star != 0:
                        ripple = 1 + self.star * np.cos(self.edges * angle)
                        polygon_radius *= ripple
                    radius /= polygon_radius

            # Normalize and apply twist
            norm_radius = radius / self.max_radius
            twist_index = (norm_radius + self.twist * angle_norm) % 1.0

            # Map to strip
            strip = pixels_in.clip(0, 255).astype(np.uint8)
            N = len(strip)
            indices = np.clip((twist_index * N).astype(np.int32), 0, N - 1)

            # Fill image
            rgb_array = strip[indices]
            image = Image.fromarray(rgb_array, mode="RGB")
            self.matrix.paste(image)
