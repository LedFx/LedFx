import logging

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Waterfall(Twod, GradientEffect):
    """
    A 2D waterfall effect for LED matrices. This effect creates a scrolling
    waterfall-like visualization based on audio data, with configurable
    frequency bands, scrolling speed, and gradient colors.
    """

    NAME = "Waterfall"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + [
        "background_color",
        "background_brightness",
        "bg_fill_first",
    ]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + [
        "max_vs_mean",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "center",
                description="Center the waterfall",
                default=False,
            ): bool,
            vol.Optional(
                "max_vs_mean",
                description="Use max or mean value for bar size",
                default=False,
            ): bool,
            vol.Optional(
                "bands",
                description="Number of frequency bands",
                default=16,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
            vol.Optional(
                "drop_secs",
                description="Seconds for the waterfall to drop from the top to bottom of the matrix",
                default=3.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
        }
    )

    def __init__(self, ledfx, config):
        """
        Initialize the Waterfall effect.

        Args:
            ledfx: The LedFx instance.
            config: Configuration dictionary for the effect.
        """
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        """
        Called when the effect is activated. Initializes variables.

        Args:
            pixel_count: The number of pixels in the matrix.
        """
        self.r = np.zeros(pixel_count)
        self.o_width = 0
        self.o_height = 0
        self.history = None

    def config_updated(self, config):
        """
        Called when the effect configuration is updated.

        Args:
            config: The updated configuration dictionary.
        """
        super().config_updated(config)
        self.bands = self._config["bands"]
        self.center = self._config["center"]
        self.grad_roll = self._config["gradient_roll"]
        self.max = self._config["max_vs_mean"]
        self.drop_secs = self._config["drop_secs"]

    def do_once(self):
        """
        Perform one-time setup tasks that depend on the pixel count.
        """
        super().do_once()
        self.bands = min(self.bands, self.pixel_count)
        self.bandsx = []
        for i in range(self.bands):
            start = int((self.r_width / float(self.bands)) * i)
            end = max(
                start, int(((self.r_width / float(self.bands)) * (i + 1)) - 1)
            )
            self.bandsx.append([start, end])
        self.half_height = int(self.r_height // 2)
        self.half_odd = bool(self.r_height % 2)

        if (
            self.history is None
            or self.o_height != self.r_height
            or self.o_width != self.r_width
        ):
            self.history = Image.new("RGB", (self.r_width, self.r_height))
            self.h_draw = ImageDraw.Draw(self.history)

        self.o_width = self.r_width
        self.o_height = self.r_height

        self.drop_tick = self.drop_secs / self.r_height

        if self.center:
            self.drop_tick = self.drop_tick * 2
        self.drop_remainder = 0.0

    def audio_data_updated(self, data):
        """
        Update the audio data for the effect.

        Args:
            data: The audio data to process.
        """
        self.r = self.melbank(filtered=True, size=self.pixel_count)
        np.clip(self.r, 0, 1, out=self.r)

    def prep_frame_vars(self):
        """
        Prepare variables for rendering the current frame.
        """
        r_split = np.array_split(self.r, self.bands)
        if self.max:
            self.volumes = np.array([split.max() for split in r_split])
        else:
            self.volumes = np.array([split.mean() for split in r_split])

        self.new_row_colors = self.get_gradient_color_vectorized1d(
            self.volumes
        ).astype(int)

    def scroll_history_one_row(self):
        """
        Scroll the history image down by one row.
        """
        w, h = self.history.size

        # if there is no space to scroll just return
        if h < 2:
            return

        region = self.history.crop((0, 0, w, h - 1))
        self.history.paste(region, (0, 1))

    def scroll_center_history_one_row(self):
        """
        Scroll the history image from the center by one row.
        """
        w, h = self.history.size

        # if there is no space to scroll just return
        if (self.half_odd and h < 3) or (not self.half_odd and h < 4):
            return

        region = self.history.crop((0, self.half_height, w, h - 1))
        self.history.paste(region, (0, self.half_height + 1))

        # top half depend on odd/even height
        if self.half_odd:
            region = self.history.crop((0, 1, w, self.half_height + 1))
        else:
            region = self.history.crop((0, 1, w, self.half_height))
        self.history.paste(region, (0, 0))

    def process_history(self):
        """
        Process the history image by scrolling it based on elapsed time.
        """
        total_time = self.passed + self.drop_remainder
        ticks, self.drop_remainder = divmod(total_time, self.drop_tick)

        # _LOGGER.info(f"Waterfall dropping {ticks} ticks")
        for _ in range(int(ticks)):
            if self.center:
                self.scroll_center_history_one_row()
            else:
                self.scroll_history_one_row()

    def draw_normal(self):
        """
        Draw the current frame onto the history image.
        """
        for i in range(self.bands):
            band_start, band_end = self.bandsx[i]

            color = tuple(self.new_row_colors[i])

            if self.center:
                self.h_draw.line(
                    (band_start, self.half_height, band_end, self.half_height),
                    fill=color,
                )

                if not self.half_odd:
                    self.h_draw.line(
                        (
                            band_start,
                            self.half_height - 1,
                            band_end,
                            self.half_height - 1,
                        ),
                        fill=color,
                    )

            else:
                self.h_draw.line(
                    (band_start, 0, band_end, 0),
                    fill=color,
                )

        self.matrix.paste(self.history)

    def draw(self):
        """
        Render the current frame of the effect.
        """
        if self.test:
            self.draw_test(self.m_draw)

        self.prep_frame_vars()

        self.process_history()

        self.draw_normal()

        self.roll_gradient()
