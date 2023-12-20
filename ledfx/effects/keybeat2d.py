import logging
import urllib.request

import PIL.Image as Image
import PIL.ImageSequence as ImageSequence
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


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
                "beat frames",
                description="Frame index to interpolate beats between",
                default="",
            ): str,
            vol.Optional(
                "force fit",
                description="Force fit to matrix",
                default=False,
            ): bool,
            vol.Optional(
                "force aspect",
                description="Preserve aspect ratio if force fit",
                default=False,
            ): bool,
            vol.Optional(
                "ping pong",
                description="play in gif source forward and reverse, not just loop",
                default=False,
            ): bool,
        }
    )

    last_gif = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def open_gif(self, gif_path):
        try:
            if gif_path.startswith("http://") or gif_path.startswith(
                "https://"
            ):
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
        self.ping_pong = self._config["ping pong"]
        self.force_fit = self._config["force fit"]
        self.force_aspect = self._config["force aspect"]

        self.frames = []
        self.reverse = False

        self.gif = None
        #        self.default = "C:/Users/atod/Downloads/cat.gif"
        self.default = "https://media.tenor.com/Wgw2UQmPXM8AAAAM/vibing-cat-cat-nodding.gif"

        # attempt to load gif, default on error or no url to test pattern
        if self.last_gif != self.url_gif:
            if self.url_gif:
                self.gif = self.open_gif(self.url_gif)

            if self.gif is None:
                self.gif = self.open_gif(self.default)

            iterator = ImageSequence.Iterator(self.gif)
            self.orig_frames = []

            for frame in iterator:
                self.orig_frames.append(frame.copy())
            self.gif.close()

        self.last_gif = self.url_gif

        if self.rotate == 1 or self.rotate == 3:
            self.stretch_v, self.stretch_h = self.stretch_h, self.stretch_v
            self.center_v, self.center_h = self.center_h, self.center_v

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known

        for frame in self.orig_frames:
            if not self.force_fit:
                stretch_height = int(self.stretch_v * frame.height)
                stretch_width = int(self.stretch_h * frame.width)
            else:
                if not self.force_aspect:
                    stretch_height = self.r_height
                    stretch_width = self.r_width
                else:
                    # preserve aspect ratio
                    # find the larger scale factor
                    scale = min(self.r_width, self.r_height)
                    stretch_height = scale
                    stretch_width = scale

            self.frames.append(frame.resize((stretch_width, stretch_height)))

        self.framecount = len(self.frames)

        self.idx = 0
        self.offset_x = int(
            ((self.r_width - stretch_width) / 2)
            + (self.center_h * self.r_width)
        )
        self.offset_y = int(
            ((self.r_height - stretch_height) / 2)
            + (self.center_v * self.r_height)
        )

    def audio_data_updated(self, data):
        # get beat bar progress
        pass

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        # using beat bar progress, interpolate between frames
        # put current frame in self.matrix
        current_frame = self.frames[self.idx]
        self.matrix.paste(current_frame, (self.offset_x, self.offset_y))

        if not self.reverse:
            self.idx += 1
        else:
            self.idx -= 1

        if self.idx >= self.framecount:
            if self.ping_pong:
                self.reverse = True
                self.idx -= 2
            else:
                self.idx = 0
        if self.idx < 0:
            self.idx = 1
            self.reverse = False
