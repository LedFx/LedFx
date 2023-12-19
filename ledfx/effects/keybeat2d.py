import logging
import timeit

import numpy as np
import urllib.request
import PIL.Image as Image
import PIL.ImageSequence as ImageSequence
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# inspired by 2D Hiphotic effect in WLED
# https://github.com/Aircoookie/WLED/blob/main/wled00/FX.cp


class Keybeat2d(Twod, GradientEffect):
    NAME = "Keybeat2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["background_color", "gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "stretch hor",
                description="Percentage of original to matrix width",
                default=100,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(
                "stretch ver",
                description="Percentage of original to matrix height",
                default=100,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(
                "center hor",
                description="center offset in horizontal direction percent of matrix width",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=100)),
            vol.Optional(
                "center ver",
                description="center offset in vertical direction percent of matrix height",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=-100.0, max=100)),
            vol.Optional(
                "gif at", description="Load gif from url or path", default=""
            ): str,
            vol.Optional(
                "beat frames", description="Frame index to interpolate beats between", default=""
            ): str,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def open_gif(self, gif_path):
        try:
            if gif_path.startswith('http://') or gif_path.startswith(
                    'https://'):
                with urllib.request.urlopen(gif_path) as url:
                    return Image.open(url)
            else:
                return Image.open(gif_path)  # Directly open for local files
        except Exception as e:
            _LOGGER.error("Failed to open gif: %s", e)
            return None

    def config_updated(self, config):
        super().config_updated(config)
        self.stretch_h = self._config["stretch hor"] / 100.0
        self.stretch_v = self._config["stretch ver"] / 100.0
        self.center_h = self._config["center hor"] / 100.0
        self.center_v = self._config["center ver"] / 100.0
        self.url_gif = self._config["gif at"]
        self.beat_frames = self._config["beat frames"]
        self.frames = []
        self.gif = None
        self.default = "C:/Users/atod/Downloads/cat.gif"
#        self.default = "https://media.tenor.com/Wgw2UQmPXM8AAAAM/vibing-cat-cat-nodding.gif"

        # attempt to load gif, default on error or no url to test pattern
        if self.url_gif:
            self.gif = self.open_gif(self.url_gif)

        if self.gif is None:
            self.gif = self.open_gif(self.default)


    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known
        iterator = ImageSequence.Iterator(self.gif)

        for frame in iterator:
            stretch_height = int(self.stretch_v * frame.height)
            stretch_width = int(self.stretch_h * frame.width)
            _LOGGER.info(f"{frame.size} {stretch_width} {stretch_height}")
            self.frames.append(frame.resize((stretch_width, stretch_height)))
        self.framecount = len(self.frames)
        self.idx = 0

        self.gif.close()
        self.offset_x = int(((self.r_width - stretch_height) / 2) + (self.center_h * self.r_width))
        self.offset_y = int(((self.r_height - stretch_height) / 2) + (self.center_v * self.r_height))

    def audio_data_updated(self, data):
        # get beat bar progress
        pass

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        # using beat bar progress, interpolate between frames
        # put current frame in self.matrix

        # render bass_sized_img into self.matrix centered with alpha
        current_frame = self.frames[self.idx]
        self.matrix.paste(current_frame, (self.offset_x, self.offset_y))
        self.idx += 1
        if self.idx >= self.framecount:
            self.idx = 0

        # profit
