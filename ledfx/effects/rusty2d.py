import logging
import numpy as np
from PIL import Image

import voluptuous as vol

# Import your compiled Rust module
try:
    import ledfx_rust_effects
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.error("Rust effects module not available - effect will show red error")

from ledfx.effects import Effect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# copy this file and rename it into the effects folder
# Anywhere you see template, replace it with your own class reference / name


# Remove the @Effect.no_registration line when you use this template
# This is a decorator that prevents the effect from being registered
# If you don't remove it, you will not be able to test your effect!
class Rusty2d(Twod):
    NAME = "The Rusty One"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "a_switch",
                description="Does a boolean thing",
                default=False,
            ): bool,
            vol.Optional(
                "rust_intensity", 
                description="Intensity multiplier for Rust effect",
                default=1.0
            ): vol.Range(min=0.0, max=2.0),
        }
    )

    def __init__(self, ledfx, config):
        # set any default values first, as config_updated will be called
        # from the super().__init__() which may depend on them
        self.bar = 0
        self.audio_bar = 0.0
        self.audio_bass = 0.0
        self.error_state = False
        super().__init__(ledfx, config)
        
        if not RUST_AVAILABLE:
            _LOGGER.error("Rust effects module not available")
            self.error_state = True

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["a_switch"]
        self.rust_intensity = self._config["rust_intensity"]

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
        
        if self.error_state:
            return
            
        self.audio_bar = data.bar_oscillator()
        self.audio_bass = np.mean(data.lows_power(filtered=False))

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
        
        # Call into Rust
        processed_array = ledfx_rust_effects.rusty_effect_process(
            img_array,
            self.audio_bar * self.rust_intensity,
            self.audio_bass,
            self.passed
        )
        
        # Convert back to PIL Image
        self.matrix = Image.fromarray(processed_array, mode='RGB')

    def _fill_red_error(self):
        """Fill the entire matrix with red to indicate failure"""
        # Create a solid red image
        red_array = np.full((self.matrix.height, self.matrix.width, 3), 255, dtype=np.uint8)
        red_array[:, :, 1] = 0  # Green = 0
        red_array[:, :, 2] = 0  # Blue = 0
        
        self.matrix = Image.fromarray(red_array, mode='RGB')
        
        # Optional: Log error periodically but not every frame
        if hasattr(self, '_error_log_counter'):
            self._error_log_counter += 1
            if self._error_log_counter % 60 == 0:  # Log every ~1 second at 60fps
                _LOGGER.error("Rust effect still in error state - showing red")
        else:
            self._error_log_counter = 1
