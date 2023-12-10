import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


class Equalizer2d(Twod, GradientEffect):
    NAME = "Equalizer2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + [
        "peak percent",
        "peak decay",
        "max vs mean",
    ]

    start_time = timeit.default_timer()

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "peak percent",
                description="Size of the tracer bar that follows a filtered value",
                default=1.0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
            vol.Optional(
                "peak decay",
                description="Decay filter applied to the peak value",
                default=0.03,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.1)),
            vol.Optional(
                "peak marks",
                description="Turn on white peak markers that follow a freq value filtered with decay",
                default=False,
            ): bool,
            vol.Optional(
                "center",
                description="Center the equalizer bar",
                default=False,
            ): bool,
            vol.Optional(
                "max vs mean",
                description="Use max or mean value for bar size",
                default=False,
            ): bool,
            vol.Optional(
                "bands",
                description="Number of freq bands",
                default=16,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def config_updated(self, config):
        super().config_updated(config)
        self.bands = self._config["bands"]
        self.init = False
        self.center = self._config["center"]
        self.grad_roll = self._config["gradient_roll"]
        self.max = self._config["max vs mean"]
        self.peak = self._config["peak marks"]
        self.peak_per = self._config["peak percent"]
        self.peak_decay = self.config["peak decay"]

    def do_once(self):
        # defer things that can't be done when pixel_count is not known
        self.max_dim = max(self.t_width, self.t_height)
        self.bands = min(self.bands, self.pixel_count)
        self.bandsx = []
        for i in range(self.bands):
            self.bandsx.append(
                [
                    int(self.max_dim / self.bands * i),
                    int(self.max_dim / self.bands * (i + 1) - 1),
                ]
            )
        self.peaks_filter = self.create_filter(
            alpha_decay=self.peak_decay, alpha_rise=0.99
        )
        self.peak_size = int(self.peak_per * self.max_dim / 100)
        self.init = True

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)
        np.clip(self.r, 0, 1, out=self.r)

    def draw(self):
        if not self.init:
            self.do_once()

        rgb_image = Image.new(
            "RGB",
            (
                self.max_dim,
                self.max_dim,
            ),
        )
        rgb_draw = ImageDraw.Draw(rgb_image)

        if self.test:
            self.draw_test(rgb_draw)

        r_split = np.array_split(self.r, self.bands)
        if self.max:
            volumes = np.array([split.max() for split in r_split])
        else:
            volumes = np.array([split.mean() for split in r_split])

        if self.peak:
            peaks = self.peaks_filter.update(volumes)

        # Precompute values that are constant for each iteration
        half_max_dim = int(self.max_dim / 2)
        gradient_colors = [
            tuple(self.get_gradient_color(1 / self.bands * i).astype(int))
            for i in range(self.bands)
        ]

        for i in range(self.bands):
            band_start, band_end = self.bandsx[i]
            volume_scaled = int(self.max_dim * volumes[i])
            if self.center:
                # Calculate dimensions for the centered rectangle
                top = half_max_dim - volume_scaled // 2
                bottom = half_max_dim + volume_scaled // 2
            else:
                # Dimensions for the bottom to top rectangle
                bottom = 0
                top = volume_scaled

            # Draw the rectangle
            rgb_draw.rectangle(
                (band_start, top, band_end, bottom), fill=gradient_colors[i]
            )

            if self.peak:
                # Draw the peak marker
                peak_scaled = int(self.max_dim * peaks[i])
                peak_end = peak_scaled + self.peak_size
                rgb_draw.rectangle(
                    (band_start, peak_scaled, band_end, peak_end),
                    fill=(255, 255, 255),
                )

        self.roll_gradient()
        return rgb_image
