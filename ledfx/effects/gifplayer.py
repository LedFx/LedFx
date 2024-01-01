import logging
import os
import time
import urllib.request

import voluptuous as vol
from PIL import Image

from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class GifPlayer(Twod):
    NAME = "GIF Player"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + ["bilinear", "blur"]
    DEFAULT_GIF_PATH = f"{os.path.join(LEDFX_ASSETS_PATH, 'animated.gif')}"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "bilinear",
                description="default NEAREST, use BILINEAR for smoother scaling, expensive on runtime takes a few ms",
                default=False,
            ): bool,
            vol.Optional(
                "url source", description="Load image from", default=""
            ): str,
            vol.Optional(
                "bounce",
                description="Bounce the GIF instead of looping",
                default=False,
            ): bool,
            vol.Optional(
                "GIF FPS", description="How fast to play the gif", default=10
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        self.gif_fps = self._config["GIF FPS"]
        self.bounce = self._config["bounce"]
        self.resize = (
            Image.BILINEAR if self._config["bilinear"] else Image.NEAREST
        )
        self.frames = []
        self.current_frame = 0
        self.start_time = time.time()
        self.last_frame_time = self.start_time
        self.init = True

    def audio_data_updated(self, data):
        # Non-reactive by design - do nothing
        return

    def open_image(self, image_path):
        try:
            if image_path.startswith("http://") or image_path.startswith(
                "https://" or image_path.startswith("file://")
            ):
                with urllib.request.urlopen(image_path) as url:
                    return Image.open(url)
            else:
                return Image.open(image_path)  # Directly open for local files
        except Exception as e:
            _LOGGER.error("Failed to open image, using default GIF: %s", e)
            return Image.open(self.DEFAULT_GIF_PATH)

    def do_once(self):
        super().do_once()

        url_path = self._config["url source"]

        if url_path == "":
            self.gif = self.open_image(self.DEFAULT_GIF_PATH)
        else:
            self.gif = self.open_image(url_path)
        self.process_gif()
        # Seed the frame data with the first frame
        self.frame_data = self.frames[0]
        self.gif_frame_duration = 1 / self.gif_fps
        self.init = False

    def draw(self):
        if self.init:
            self.do_once()
        current_time = time.time()
        self.step_gif_if_time_elapsed(current_time)
        self.matrix.paste(self.frame_data)

    def step_gif_if_time_elapsed(self, current_time):
        """
        Steps to the next frame of the GIF if the specified time has elapsed.

        Args:
            current_time (float): The current time in seconds.

        Returns:
            None
        """
        if current_time - self.last_frame_time >= self.gif_frame_duration:
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
            self.last_frame_time = time.time()

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
                (self.r_width, self.r_height), resample=self.resize
            )
            # Add the frame to our frames object
            self.frames.append(final_frame_data)
        # Close image
        self.gif.close()
