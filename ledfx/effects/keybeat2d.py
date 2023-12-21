import logging
import urllib.request
import re

import PIL.Image as Image
import PIL.ImageSequence as ImageSequence
import voluptuous as vol

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


def extract_positive_integers(s):
    # Use regular expression to find all sequences of digits
    numbers = re.findall(r'\d+', s)

    # Convert each found sequence to an integer and filter out non-positive numbers
    return [int(num) for num in numbers if int(num) >= 0]

def remove_values_above_limit(numbers, limit):
    # Keep only values that are less than or equal to the limit
    return [num for num in numbers if num <= limit]

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
                "skip frames",
                description="Frames to remove from gif animation",
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
        self.beat = 0.0
        self.bar = 0.0

        self.framecount = len(self.orig_frames)
        self.beat_frames = remove_values_above_limit(sorted(extract_positive_integers(self._config["beat frames"])), len(self.orig_frames))
        self.skip_frames = remove_values_above_limit(sorted(extract_positive_integers(self._config["skip frames"])), len(self.orig_frames))

        _LOGGER.info(f"framecount {self.framecount} beat frames {self.beat_frames}")
        _LOGGER.info(f"framecount {self.framecount} skip frames {self.skip_frames}")

        self.post_frames = self.orig_frames.copy()
        # remove any frames that are in skip_frames
        for frame_index in self.skip_frames:
            self.post_frames[frame_index] = None

        # strip out None frames
        self.post_frames = [img for img in self.post_frames if img is not None]

        _LOGGER.info("************************* start beat frame debug *************************")
        # adjust beat frames for removed frames
        sl = len(self.skip_frames)
        for s, skip_index in enumerate(reversed(self.skip_frames)):
            si = sl - 1 - s
            _LOGGER.info(f"si: {si} skip_index: {skip_index} resolves {self.skip_frames[si]} from {self.skip_frames}")
            bl = len(self.beat_frames)
            for b, beat_index in enumerate(reversed(self.beat_frames)):
                bi = bl - 1 - b
                #_LOGGER.info(f"bi: {bi} len: {len(self.beat_frames)}")
                _LOGGER.info(f"bi: {bi} beat_index: {beat_index} resolves {self.beat_frames[bi]} from {self.beat_frames}")
                if beat_index > skip_index:
                    self.beat_frames[bi] -= 1
                    _LOGGER.info(f"reduce by 1 {self.beat_frames[bi]}")
                if beat_index == skip_index:
                    del self.beat_frames[bi]
                    _LOGGER.info(f"delete {beat_index} from {self.beat_frames}")

        self.framecount = len(self.post_frames)

        _LOGGER.info(f"framecount {self.framecount} beat frames {self.beat_frames}")

        # we have beat frames, that are now correctly indexed against image frames
        # next we have to calculate for each beat end point, how much a frame represents in a beat continuum of 1
        # then we can interpolate between frames based on beat progress
        # we should always start animation from the first frame with a beat, never from frame 0

        self.beat_incs = []
        if len(self.beat_frames) == 0:
            # TODO: no beat frames so use a safe default
            self.idx = 0
            self.beat_idx = 0
            self.beat_incs = [1.0]
        elif len(self.beat_frames) == 1:
            # TODO: only one beat frame so use a safe default
            self.beat_idx = 0
            self.idx = self.beat_frames[self.beat_idx]
            self.beat_incs = [1.0]
        else:
            self.beat_idx = 0
            self.idx = self.beat_frames[self.beat_idx]
            _LOGGER.info(f"First beat frame will be : {self.idx}")

            for b, beat_index in enumerate(self.beat_frames):
                if b == len(self.beat_frames) - 1:
                    # last beat frame so loop to first for calculation
                    frames = self.framecount - beat_index + self.beat_frames[0]
                    _LOGGER.info(f"Last beat frame wrap around {frames} {frames / 1.0}")
                    self.beat_incs.append(1.0 / frames)
                else:
                    self.beat_incs.append(1.0 / (self.beat_frames[b+1] - beat_index))

        _LOGGER.info("************************* end beat frame debug *************************")
        _LOGGER.info(f"beat_frames: {self.beat_frames}")
        _LOGGER.info(f"beat_incs  {self.beat_incs}")
        _LOGGER.info("************************* end beat frame debug *************************")

        self.last_beat = 0.0

        if self.rotate == 1 or self.rotate == 3:
            self.stretch_v, self.stretch_h = self.stretch_h, self.stretch_v
            self.center_v, self.center_h = self.center_h, self.center_v

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known

        for frame in self.post_frames:
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

        self.offset_x = int(
            ((self.r_width - stretch_width) / 2)
            + (self.center_h * self.r_width)
        )
        self.offset_y = int(
            ((self.r_height - stretch_height) / 2)
            + (self.center_v * self.r_height)
        )

    def audio_data_updated(self, data):
        self.bar = data.bar_oscillator()
        self.beat = data.beat_oscillator()

    def bump_frame(self):
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

    def draw(self):
        if self.test:
            self.draw_test(self.m_draw)

        # Using the self.beat progress, we can interpolate between frames
        # if we see beat go from a larger number to a smaller one, we hit a beat and wrapped, so display the beat frame itself
        if len(self.beat_frames) == 0:
            # TODO: move one frame per beat
            frame = 0
        else:
            if self.beat < self.last_beat:
                self.beat_idx += 1
                if self.beat_idx >= len(self.beat_frames):
                    self.beat_idx = 0
                _LOGGER.info(f"beat kick {self.beat_idx} {self.beat_frames[self.beat_idx]}")

            frame_progress = self.beat / self.beat_incs[self.beat_idx]
            _LOGGER.info(f"self.beat {self.beat} beat_inc: {self.beat_incs[self.beat_idx]} frame_progress: {frame_progress}")
            frame = int(frame_progress) + self.beat_frames[self.beat_idx]
            _LOGGER.info(f"frame: {frame}")
            if frame >= self.framecount:
                frame = frame - self.framecount
                _LOGGER.info(f"frame wrap: {frame}")

            self.last_beat = self.beat

        current_frame = self.frames[frame]
        self.matrix.paste(current_frame, (self.offset_x, self.offset_y))

#        self.bump_frame()