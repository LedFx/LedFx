import logging
import os

import PIL.ImageEnhance as ImageEnhance
import PIL.ImageSequence as ImageSequence
import voluptuous as vol

from ledfx.consts import LEDFX_ASSETS_PATH
from ledfx.effects.gifbase import GifBase
from ledfx.effects.twod import Twod
from ledfx.utils import (
    clip_at_limit,
    extract_positive_integers,
    get_mono_font,
    open_gif,
)

_LOGGER = logging.getLogger(__name__)


class Keybeat2d(Twod, GifBase):
    NAME = "Keybeat2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
    ]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + [
        "deep_diag",
        "fake_beat",
        "pp_skip",
        "resize_method",
        "image_brightness",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "stretch_horizontal",
                description="Percentage of original to matrix width",
                default=100,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(
                "stretch_vertical",
                description="Percentage of original to matrix height",
                default=100,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(
                "center_horizontal",
                description="Center offset in horizontal direction percent of matrix width",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=-95, max=95)),
            vol.Optional(
                "center_vertical",
                description="Center offset in vertical direction percent of matrix height",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=-95, max=95)),
            vol.Optional(
                "image_location",
                description="Load gif from url or path",
                default="",
            ): str,
            vol.Optional(
                "beat_frames",
                description="Frame index to interpolate beats between",
                default="",
            ): str,
            vol.Optional(
                "skip_frames",
                description="Frames to remove from gif animation",
                default="",
            ): str,
            vol.Optional(
                "deep_diag",
                description="Diagnostic overlayed on matrix",
                default=False,
            ): bool,
            vol.Optional(
                "fake_beat",
                description="Trigger test code with 0.05 beat per frame",
                default=False,
            ): bool,
            vol.Optional(
                "keep_aspect_ratio",
                description="Preserve aspect ratio if force fit",
                default=False,
            ): bool,
            vol.Optional(
                "force_fit",
                description="Force fit to matrix",
                default=False,
            ): bool,
            vol.Optional(
                "ping_pong_skip",
                description="When ping pong, skip the first beat key frame on both ends, use when key beat frames are very close to start and ends only",
                default=False,
            ): bool,
            vol.Optional(
                "ping_pong",
                description="Play gif forward and reverse, not just loop",
                default=False,
            ): bool,
            vol.Optional(
                "half_beat",
                description="half the beat input impulse, slow things down",
                default=False,
            ): bool,
            vol.Optional(
                "image_brightness",
                description="Image brightness",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=3.0)),
        }
    )

    last_gif = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def config_updated(self, config):
        super().config_updated(config)
        self.stretch_h = self._config["stretch_horizontal"] / 100.0
        self.stretch_v = self._config["stretch_vertical"] / 100.0
        self.center_h = self._config["center_horizontal"] / 100.0
        self.center_v = self._config["center_vertical"] / 100.0

        self.image_location = self._config["image_location"]

        self.ping_pong = self._config["ping_pong"]
        self.ping_pong_skip = self._config["ping_pong_skip"]
        self.force_fit = self._config["force_fit"]
        self.force_aspect = self._config["keep_aspect_ratio"]
        self.fake_beat = self._config["fake_beat"]
        self.deep_diag = self._config["deep_diag"]
        self.half_beat = self._config["half_beat"]

        self.frames = []
        self.reverse = False

        self.gif = None
        self.default = os.path.join(LEDFX_ASSETS_PATH, "gifs", "skull.gif")

        # attempt to load gif, default on error or no url to test pattern
        if self.last_gif != self.image_location:
            if self.image_location:
                self.gif = open_gif(self.image_location)

            if self.gif is None:
                self.gif = open_gif(self.default)
                self.force_fit = True

            iterator = ImageSequence.Iterator(self.gif)
            self.orig_frames = []

            for frame in iterator:
                self.orig_frames.append(frame.convert("RGB"))
            self.gif.close()

        self.last_gif = self.image_location
        self.beat = 0.0  # beat oscillator
        self.frame_c = 0  # current frame index to render
        self.frame_s = 0  # seq frame index for when wrapping around
        self.f_beat = 0.0  # fake beat oscillator

        self.framecount = len(self.orig_frames)
        self.beat_frames = clip_at_limit(
            sorted(extract_positive_integers(self._config["beat_frames"])),
            len(self.orig_frames),
        )
        self.skip_frames = clip_at_limit(
            sorted(extract_positive_integers(self._config["skip_frames"])),
            len(self.orig_frames),
        )

        if self.diag:
            _LOGGER.info(
                f"framecount {self.framecount} beat frames {self.beat_frames}"
            )
            _LOGGER.info(
                f"framecount {self.framecount} skip frames {self.skip_frames}"
            )

        self.post_frames = self.orig_frames.copy()
        # remove any frames that are in skip_frames
        for frame_index in self.skip_frames:
            self.post_frames[frame_index] = None

        # strip out None frames
        self.post_frames = [img for img in self.post_frames if img is not None]
        self.post_frames = [
            ImageEnhance.Brightness(frame).enhance(
                self._config["image_brightness"]
            )
            for frame in self.post_frames
        ]

        if self.diag:
            _LOGGER.info(
                "************************* start beat frame debug *************************"
            )
        # adjust beat frames for removed frames
        sl = len(self.skip_frames)
        for s, skip_index in enumerate(reversed(self.skip_frames)):
            si = sl - 1 - s
            if self.diag:
                _LOGGER.info(
                    f"si: {si} skip_index: {skip_index} resolves {self.skip_frames[si]} from {self.skip_frames}"
                )
            bl = len(self.beat_frames)
            for b, beat_index in enumerate(reversed(self.beat_frames)):
                bi = bl - 1 - b
                if self.diag:
                    _LOGGER.info(
                        f"bi: {bi} beat_index: {beat_index} resolves {self.beat_frames[bi]} from {self.beat_frames}"
                    )
                if beat_index > skip_index:
                    self.beat_frames[bi] -= 1
                    if self.diag:
                        _LOGGER.info(f"reduce by 1 {self.beat_frames[bi]}")
                if beat_index == skip_index:
                    del self.beat_frames[bi]
                    if self.diag:
                        _LOGGER.info(
                            f"delete {beat_index} from {self.beat_frames}"
                        )

        self.framecount = len(self.post_frames)

        if self.diag:
            _LOGGER.info(
                f"framecount {self.framecount} beat frames {self.beat_frames}"
            )

        # for ping pong, first lets copy all the frames in reverse order, without repeating the end frames
        # then we need to add the beat frame indexs in reverse order, while accounting that they are now reversed and offset
        if self.ping_pong:
            # remove first and last frames from the copy, so we don't repeat them
            self.post_frames.extend(reversed(self.post_frames[1:-1]))
            # ensure we don't have beat indexes into the removed frames
            self.mirror_beats = [
                x
                for x in reversed(self.beat_frames)
                if x != 0 and x != self.framecount - 1
            ]
            beat_frames_ext = [
                self.framecount + self.framecount - b - 2
                for b in self.mirror_beats
            ]

            # its hard to decide if this makes sense as a feature
            if self.ping_pong_skip and len(beat_frames_ext) >= 2:
                beat_frames_ext = beat_frames_ext[:-1]
                self.beat_frames = self.beat_frames[:-1]

            self.beat_frames.extend(beat_frames_ext)
            self.framecount = len(self.post_frames)

            if self.diag:
                _LOGGER.info(
                    "************************* Ping Pong impacts *************************"
                )
                _LOGGER.info(
                    f"framecount {self.framecount} beat frames {self.beat_frames}"
                )

        # we have beat frames, that are now correctly indexed against image frames
        # next we have to calculate for each beat end point, how much a frame represents in a beat continuum of 1
        # then we can interpolate between frames based on beat progress
        # we should always start animation from the first frame with a beat, never from frame 0

        self.beat_incs = []
        if len(self.beat_frames) == 0:
            self.idx = 0
            self.beat_idx = 0
            self.beat_incs = [1.0]
        else:
            self.beat_idx = 0
            self.idx = self.beat_frames[self.beat_idx]

            for b, beat_index in enumerate(self.beat_frames):
                if b == len(self.beat_frames) - 1:
                    # last beat frame so loop to first for calculation
                    frames = self.framecount - beat_index + self.beat_frames[0]
                    self.beat_incs.append(1.0 / frames)
                else:
                    self.beat_incs.append(
                        1.0 / (self.beat_frames[b + 1] - beat_index)
                    )

        if self.diag:
            _LOGGER.info(
                "************************* end beat frame debug *************************"
            )
            _LOGGER.info(f"beat_frames: {self.beat_frames}")
            _LOGGER.info(f"beat_incs  {self.beat_incs}")
            _LOGGER.info(
                "************************* end beat frame debug *************************"
            )

        self.num_beat_frames = len(self.beat_frames)
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
                self.center_h = 0
                self.center_v = 0

                if not self.force_aspect:
                    stretch_height = self.r_height
                    stretch_width = self.r_width
                else:
                    # preserve aspect ratio
                    # find the larger scale factor
                    scale = min(
                        float(self.r_width) / frame.width,
                        float(self.r_height) / frame.height,
                    )
                    stretch_height = int(scale * frame.height)
                    stretch_width = int(scale * frame.width)

            stretch_width = max(1, stretch_width)
            stretch_height = max(1, stretch_height)

            self.frames.append(
                frame.resize(
                    (stretch_width, stretch_height), self.resize_method
                )
            )

        self.offset_x = int(
            ((self.r_width - stretch_width) / 2)
            + (self.center_h * self.r_width)
        )
        self.offset_y = int(
            ((self.r_height - stretch_height) / 2)
            + (self.center_v * self.r_height)
        )

        if self.deep_diag:
            self.font = get_mono_font(10)

            self.beat_times = []  # rolling window of beat timestamps
            self.beat_f_times = []  # rolling windows of frame info
            self.begin_time = self.current_time

        self.last_beat_t = self.current_time

    def audio_data_updated(self, data):
        if self.half_beat:
            self.beat = (data.bar_oscillator() % 2) / 2
        else:
            self.beat = data.beat_oscillator()

    def overlay(self, beat_kick, skip_beat):
        # add beat timestamps to the rolling window beat_list
        # use len of beat_list as bpm
        if beat_kick:
            self.beat_times.append(self.current_time)
            color = (255, 255, 255)
        elif skip_beat:
            color = (255, 0, 0)
        else:
            color = (255, 0, 255)

        self.beat_f_times.append(
            (self.current_time, self.beat, self.frame_c, color)
        )
        # cull any beats older than 60 seconds
        self.beat_times = [
            beat for beat in self.beat_times if self.current_time - beat < 60.0
        ]
        self.beat_f_times = [
            f_beat
            for f_beat in self.beat_f_times
            if self.current_time - f_beat[0] < 60.0
        ]

        # lets graph directly into the draw space
        # loop through beat_list and draw a dot for each beat
        # start at the last entry and work backwards
        graph_s = 9
        graph_h = min(self.r_height - 9, 32)
        x = 0
        pixels = self.matrix.load()
        for _, beat, f_frame, color in reversed(self.beat_f_times):
            y_beat = graph_s + graph_h - beat * graph_h
            if y_beat < self.matrix.height:
                pixels[x, y_beat] = (255, 255, 0)
            y_frame = graph_s + graph_h - (f_frame / self.framecount) * graph_h
            if y_frame < self.matrix.height:
                pixels[x, y_frame] = color
            x += 1
            if x >= self.matrix.width:
                break

        # if we have not reached a 60 second window yet, then gestimate bpm
        passed = self.current_time - self.begin_time
        self.bpm = len(self.beat_times)

        if passed > 0 and passed < 60.0:
            self.bpm *= 60 / passed
            color = (255, 0, 255)
        else:
            color = (255, 255, 0)

        if beat_kick:
            diag_string = "\u25CF\u25CF\u25CF\u25CF"  # filled circle char
            color = (255, 255, 255)
        else:
            diag_string = "\u25CB" * int(self.beat * 4) + " " * (
                4 - int(self.beat * 4)
            )

        diag_string += f"{self.frame_c:03} {self.bpm:3.0f} {passed:.0f}"
        self.m_draw.text((0, 0), diag_string, fill=color, font=self.font)

    def draw(self):
        beat_kick = False
        skip_beat = False

        # fake beat for testing at 200 frames per beat
        if self.fake_beat:
            self.f_beat = (self.f_beat + 0.005) % 1.0
            self.beat = self.f_beat

        # if we see beat go from a larger number to a smaller one, we hit a beat
        if self.beat < self.last_beat:
            # protect against false beats with less than 100ms ~= 600 bpm!
            if self.current_time - self.last_beat_t < 0.1:
                skip_beat = True
                if self.deep_diag:
                    _LOGGER.info(
                        f"skip beat threshold triggered: {self.current_time - self.last_beat_t:0.6f}"
                    )
            else:
                beat_kick = True
                if self.num_beat_frames == 0:
                    # let's just advance one frame per beat when there are no key frames
                    self.frame_s = self.frame_c = (
                        self.frame_c + 1
                    ) % self.framecount
                else:
                    self.beat_idx = (self.beat_idx + 1) % self.num_beat_frames

            self.last_beat_t = self.current_time

        self.last_beat = self.beat

        if self.num_beat_frames > 0:
            # Using the self.beat progress, we can interpolate between frames
            frame_progress = self.beat / self.beat_incs[self.beat_idx]
            self.frame_c = (
                int(frame_progress) + self.beat_frames[self.beat_idx]
            )
            self.frame_s = self.frame_c
            self.frame_c %= self.framecount
        else:
            frame_progress = 0.0

        if self.deep_diag:
            _LOGGER.info(
                f"self.beat {self.beat:0.6f} beat_inc: {self.beat_incs[self.beat_idx]:0.6f} beat_idx: {self.beat_idx} frame_progress: {frame_progress:0.6f} kick: {beat_kick} seq: {self.frame_s} frame: {self.frame_c}"
            )

        current_frame = self.frames[self.frame_c]
        self.matrix.paste(current_frame, (self.offset_x, self.offset_y))

        if self.deep_diag:
            self.overlay(beat_kick, skip_beat)
