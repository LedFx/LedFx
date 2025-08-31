import logging
import time

import numpy as np
import voluptuous as vol
from PIL import Image

# Import your compiled Rust module
try:
    import ledfx_rust_effects

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.error(
        "Rust effects module not available - effect will show red error"
    )

from ledfx.color import validate_color
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

def hex_to_rgb(hex_color):
    """Convert hex color string to RGB tuple"""
    # Remove the # if present
    hex_color = hex_color.lstrip('#')
    # Convert to RGB tuple
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# copy this file and rename it into the effects folder
# Anywhere you see template, replace it with your own class reference / name


# Remove the @Effect.no_registration line when you use this template
# This is a decorator that prevents the effect from being registered
# If you don't remove it, you will not be able to test your effect!
class Rusty2d(Twod):
    NAME = "Rust Effects"
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
        import time
        import random
        self._instance_id = int(time.time() * 1000000) + random.randint(0, 999999)

        # Set error state based on Rust module availability
        self.error_state = not RUST_AVAILABLE

        # Debug tracking for particle counts
        self._debug_last_report = 0.0
        self._debug_report_interval = 1.0  # Report every 1 second

        # Initialize default RGB color tuples (will be updated in config_updated)
        self.low_rgb = (255, 0, 0)   # Red
        self.mid_rgb = (0, 255, 0)   # Green  
        self.high_rgb = (0, 0, 255)  # Blue

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
        # copy over your configs here into variables
        self.intensity = self._config["intensity"]
        self.spawn_rate = self._config["spawn_rate"]
        self.velocity = self._config["velocity"]
        self.blur_amount = self._config["blur_amount"]
        self.low_band = self._config["low_band"]
        self.mid_band = self._config["mid_band"]
        self.high_band = self._config["high_band"]
        
        # Pre-convert hex colors to RGB tuples for efficiency
        self.low_rgb = hex_to_rgb(self.low_band)
        self.mid_rgb = hex_to_rgb(self.mid_band)
        self.high_rgb = hex_to_rgb(self.high_band)

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known
        # this is probably important for most 2d matrix where you want
        # things to be initialized to led length and implied dimensions
        #
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        #
        # note that self.t_width and self.t_height are the physical dimensions
        #
        # this function will be called once on the first entry to render call
        # in base class twod AND every time there is a config_updated thereafter

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()

        # Always update audio data, even in error state (for recovery)
        self.audio_bar = data.bar_oscillator()
        self.audio_pow = np.array(
            [
                data.lows_power(),
                data.mids_power(),
                data.high_power(),
            ],
            dtype=np.float32,
        )

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
        # Measure time passed per frame from the self.now and self.passed vars
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        # all rotation abstraction is done for you
        # you can use image dimensions now
        # self.matrix.height
        # self.matrix.width

        # look in this function for basic lines etc, use pillow primitives
        # for regular shapes
        if self.test:
            self.draw_test(self.m_draw)

        if self.error_state:
            self._fill_red_error()
            return

        try:
            self._draw_rust()
        except Exception as e:
            _LOGGER.error(f"Rust effect processing failed: {e}")
            self.error_state = True
            self._fill_red_error()

        # stuff pixels with
        # self.matrix.putpixel((x, y), (r, g, b))
        # or
        # pixels = self.matrix.load()
        # pixels[x, y] = (r, g, b)
        #   iterate

    def _draw_rust(self):
        # Convert PIL image to numpy array
        img_array = np.array(self.matrix)

        # Debug log parameters every 60 frames (~1 second at 60fps)
        if not hasattr(self, '_debug_frame_count'):
            self._debug_frame_count = 0
        self._debug_frame_count += 1
        
        if self._debug_frame_count % 60 == 0:
            _LOGGER.debug(
                f"RustyFlame[{self._instance_id}] params - Matrix: {img_array.shape}, "
                f"spawn_rate={self.spawn_rate:.3f}, velocity={self.velocity:.3f}, "
                f"intensity={self.intensity:.3f}, passed={self.passed:.6f}, "
                f"audio_pow={[f'{x:.2f}' for x in self.audio_pow]}"
            )

        # Call the Rust flame effect function
        processed_array = ledfx_rust_effects.rusty_flame_process(
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
        )
        
        # Debug particle count reporting for flame effect
        current_time = time.time()
        if current_time - self._debug_last_report >= self._debug_report_interval:
            try:
                particle_counts = ledfx_rust_effects.get_flame_particle_counts(self._instance_id)
                total_particles = sum(particle_counts)
                _LOGGER.debug(
                    f"RustyFlame particles - Low: {particle_counts[0]}, "
                    f"Mid: {particle_counts[1]}, High: {particle_counts[2]}, "
                    f"Total: {total_particles}"
                )
                self._debug_last_report = current_time
            except Exception as e:
                _LOGGER.warning(f"Failed to get particle counts: {e}")

        # Convert back to PIL Image
        self.matrix = Image.fromarray(processed_array, mode="RGB")

    def _fill_red_error(self):
        """Fill the entire matrix with red to indicate failure"""
        # Create a solid red image
        red_array = np.full(
            (self.matrix.height, self.matrix.width, 3), 255, dtype=np.uint8
        )
        red_array[:, :, 1] = 0  # Green = 0
        red_array[:, :, 2] = 0  # Blue = 0

        self.matrix = Image.fromarray(red_array, mode="RGB")

        # Log error periodically using actual time, not frame count
        if not hasattr(self, "_last_error_log_time"):
            self._last_error_log_time = 0.0

        self._last_error_log_time += self.passed
        if self._last_error_log_time >= 2.0:  # Log every 2 seconds
            _LOGGER.error("Rust effect still in error state - showing red")
            self._last_error_log_time = 0.0
