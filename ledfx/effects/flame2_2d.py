import logging

import numpy as np
import voluptuous as vol
from PIL import Image

# Import your compiled Rust module
try:
    import ledfx_rust

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.error(
        "Rust effects module not available - effect will show red error"
    )

from ledfx.color import parse_color, validate_color
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Flame2_2d(Twod):
    NAME = "Flame2"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["test", "background_color"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "spawn_rate", description="Particles spawn rate", default=0.5
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "velocity", description="Trips to top per second", default=0.3
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
            vol.Optional(
                "animation_speed",
                description="Overall animation speed",
                default=0.7,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
            vol.Optional(
                "intensity",
                description="Application of the audio power input",
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "blur_amount", description="Blur radius in pixels", default=2
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
            vol.Optional(
                "low_band", description="low band flame", default="#FF0000"
            ): validate_color,
            vol.Optional(
                "mid_band", description="mid band flame", default="#00FF00"
            ): validate_color,
            vol.Optional(
                "high_band", description="high band flame", default="#0000FF"
            ): validate_color,
        }
    )

    def __init__(self, ledfx, config):
        # Initialize all audio-related attributes with safe defaults
        # These must be set before audio_data_updated() is called
        self.bar = 0
        self.audio_bar = 0.0
        self.audio_bass = 0.0
        self.audio_pow = np.array([0.0, 0.0, 0.0], dtype=np.float32)

        # Generate unique instance ID for this effect instance
        import random
        import time

        self._instance_id = int(time.time() * 1000000) + random.randint(
            0, 999999
        )

        # Set error state based on Rust module availability
        self.error_state = not RUST_AVAILABLE

        super().__init__(ledfx, config)

        if not RUST_AVAILABLE:
            _LOGGER.error(
                "Rust effects module not available - effect will show red"
            )
        else:
            _LOGGER.info(
                "Rust effects module available and loaded successfully"
            )

    def config_updated(self, config):
        super().config_updated(config)
        self.intensity = self._config["intensity"]
        self.spawn_rate = self._config["spawn_rate"]
        self.velocity = self._config["velocity"]
        self.animation_speed = self._config["animation_speed"]
        self.blur_amount = self._config["blur_amount"]
        self.low_band = self._config["low_band"]
        self.mid_band = self._config["mid_band"]
        self.high_band = self._config["high_band"]

        self.low_rgb = np.array(parse_color(self.low_band), dtype=float)
        self.mid_rgb = np.array(parse_color(self.mid_band), dtype=float)
        self.high_rgb = np.array(parse_color(self.high_band), dtype=float)

    def do_once(self):
        super().do_once()

    def audio_data_updated(self, data):
        osc = data.bar_oscillator()
        self.bar = osc
        self.audio_bar = osc
        self.audio_pow = np.array(
            [
                data.lows_power(),
                data.mids_power(),
                data.high_power(),
            ],
            dtype=np.float32,
        )

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        if self.error_state:
            self.red_error()
            return

        try:
            self._draw_rust()
        except Exception as e:
            _LOGGER.error(f"Rust effect processing failed: {e}")
            self.error_state = True
            self.red_error()

    def _draw_rust(self):
        # Convert PIL image to numpy array in case we want to build on top of history
        # this can be deleted if we also create from scratch each frame
        img_array = np.array(self.matrix)

        # Call the Rust flame effect function
        processed_array = ledfx_rust.flame2_process(
            img_array,
            self.audio_bar,
            self.audio_pow,
            self.intensity,
            self.passed,
            self.spawn_rate,
            self.velocity,
            self.blur_amount,
            self._instance_id,
            self.low_rgb,
            self.mid_rgb,
            self.high_rgb,
            self.animation_speed,
        )

        # Convert back to PIL Image
        self.matrix = Image.fromarray(processed_array, mode="RGB")
