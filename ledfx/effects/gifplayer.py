import logging
import os

import voluptuous as vol
from PIL import Image

from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.effects.gifbase import GifBase
from ledfx.effects.twod import Twod
from ledfx.utils import open_gif

_LOGGER = logging.getLogger(__name__)


class GifPlayer(Twod, GifBase):
    NAME = "GIF Player"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["gradient", "background"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + ["blur", "resize_method"]
    DEFAULT_GIF_PATH = f"{os.path.join(LEDFX_ASSETS_PATH, 'animated.gif')}"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "image_location",
                description="Load GIF from URL/local file",
                default="",
            ): str,
            vol.Optional(
                "bounce",
                description="Bounce the GIF instead of looping",
                default=False,
            ): bool,
            vol.Optional(
                "gif_fps", description="How fast to play the gif", default=10
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        self.gif_fps = self._config["gif_fps"]
        self.bounce = self._config["bounce"]
        self.frames = []
        self.current_frame = 0
        self.init = True

    def audio_data_updated(self, data):
        # Non-reactive by design - do nothing
        return

    def do_once(self):
        super().do_once()

        gif_path = self._config["image_location"]
        # If for some unknown reason the url_path is blank (someone saved a preset with no string)/
        if gif_path == "":
            # Show animated LedFx logo
            self.gif = open_gif(self.DEFAULT_GIF_PATH)
        else:
            # Try to open the url
            self.gif = open_gif(gif_path)
        # If the URL doesn't work
        if self.gif is None:
            # Show the animated LedFx logo
            self.gif = open_gif(self.DEFAULT_GIF_PATH)

        self.process_gif()
        # Seed the frame data with the first frame
        self.frame_data = self.frames[0]
        self.gif_frame_duration = 1 / self.gif_fps
        self.last_frame_time = self.current_time

    def draw(self):
        self.step_gif_if_time_elapsed()
        self.matrix.paste(self.frame_data)

    def step_gif_if_time_elapsed(self):
        """
        Steps to the next frame of the GIF if the specified time has elapsed.

        Returns:
            None
        """
        if self.current_time - self.last_frame_time >= self.gif_frame_duration:
            if self.bounce:
                if self.current_frame == (len(self.frames) - 1):
                    self.increment = -1
                elif self.current_frame == 0:
                    self.increment = 1
                self.current_frame += self.increment
            else:
                if self.current_frame == (len(self.frames) - 1):
                    self.current_frame = 0
                else:
                    self.current_frame += 1
            self.frame_data = self.frames[self.current_frame]
            self.last_frame_time = self.current_time

    def process_gif(self):
        """
        Process the GIF frames and store them in the frames object.

        This method iterates over each frame of the GIF, applies necessary transformations,
        and stores the processed frames.

        Returns:
            None
        """
        black_background = Image.new("RGBA", self.gif.size, (0, 0, 0))
        # For every frame
        for frame_index in range(self.gif.n_frames):
            self.gif.seek(frame_index)
            raw_frame_data = self.gif.convert("RGBA")
            # We need to alpha composite to change the white to black for transparent pixels
            composite_frame_data = Image.alpha_composite(
                black_background, raw_frame_data
            )
            # Resize the gif to the matrix size

            final_frame_data = composite_frame_data.resize(
                (self.r_width, self.r_height), resample=self.resize_method
            )
            # Add the frame to our frames object
            self.frames.append(final_frame_data)
        # Close image
        self.gif.close()
