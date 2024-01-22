import logging

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)


def interpolate_point(p1, p2, t):
    return (p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t)


class Equalizer2d(Twod, GradientEffect):
    NAME = "Equalizer2d"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + [
        "peak_percent",
        "peak_decay",
        "max_vs_mean",
        "frequency_range",
        "spin_multiplier",
        "spin_decay",
    ]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "peak_percent",
                description="Size of the tracer bar that follows a filtered value",
                default=1.0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
            vol.Optional(
                "peak_decay",
                description="Decay filter applied to the peak value",
                default=0.03,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.1)),
            vol.Optional(
                "peak_marks",
                description="Turn on white peak markers that follow a freq value filtered with decay",
                default=False,
            ): bool,
            vol.Optional(
                "center",
                description="Center the equalizer bar",
                default=False,
            ): bool,
            vol.Optional(
                "max_vs_mean",
                description="Use max or mean value for bar size",
                default=False,
            ): bool,
            vol.Optional(
                "ring",
                description="Why be so square?",
                default=False,
            ): bool,
            vol.Optional(
                "spin",
                description="Weeeeeeeeeee",
                default=False,
            ): bool,
            vol.Optional(
                "bands",
                description="Number of freq bands",
                default=16,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=64)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for spin impulse",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "spin_multiplier",
                description="Spin impulse multiplier",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
            vol.Optional(
                "spin_decay",
                description="Decay filter applied to the spin impulse",
                default=0.1,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=0.3)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)
        self.spin_value = 0.0

    def config_updated(self, config):
        super().config_updated(config)
        self.bands = self._config["bands"]
        self.center = self._config["center"]
        self.grad_roll = self._config["gradient_roll"]
        self.max = self._config["max_vs_mean"]
        self.peak = self._config["peak_marks"]
        self.peak_per = self._config["peak_percent"]
        self.peak_decay = self._config["peak_decay"]
        self.ring = self._config["ring"]
        self.spin = self._config["spin"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.power_multiplier = self._config["spin_multiplier"]
        self.impulse_filter = self.create_filter(
            alpha_decay=self._config["spin_decay"], alpha_rise=0.99
        )

    def calc_ring_segments(self, rotation):
        # we want coordinates for self.bands around an oval defined by self.r_width and self.r_height
        # do 1 more than bands to get closure of ring

        # calculate start and end of bands on circle
        self.bandsc = []
        for i in range(self.bands + 1):
            angle = 2.0 * np.pi * i / self.bands + np.radians(rotation)
            x = (self.r_width) / 2.0 + (self.r_width - 1) / 2.0 * np.cos(angle)
            y = (self.r_height) / 2.0 + (self.r_height - 1) / 2.0 * np.sin(
                angle
            )
            self.bandsc.append((x, y))

        # calc mid points of bands
        self.bandscm = []
        for i in range(self.bands):
            self.bandscm.append(
                interpolate_point(self.bandsc[i], self.bandsc[i + 1], 0.5)
            )
        # Add from beginnning to end for wrap around
        self.bandscm.append(self.bandscm[0])
        self.p_center = (self.r_width / 2.0, self.r_height / 2.0)

    def do_once(self):
        super().do_once()
        # defer things that can't be done when pixel_count is not known
        self.bands = min(self.bands, self.pixel_count)
        self.bandsx = []
        for i in range(self.bands):
            start = int((self.r_width / float(self.bands)) * i)
            end = max(
                start, int(((self.r_width / float(self.bands)) * (i + 1)) - 1)
            )
            self.bandsx.append([start, end])
        self.peaks_filter = self.create_filter(
            alpha_decay=self.peak_decay, alpha_rise=0.99
        )
        self.peak_size = int(self.peak_per * self.r_height / 100)
        self.half_height = self.r_height // 2

        if self.ring:
            self.calc_ring_segments(0)
            self.impulse = 0.0

    def audio_data_updated(self, data):
        # Grab the filtered melbank
        self.r = self.melbank(filtered=True, size=self.pixel_count)
        np.clip(self.r, 0, 1, out=self.r)
        self.impulse = self.impulse_filter.update(
            getattr(data, self.power_func)() * self.power_multiplier
        )

    def prep_frame_vars(self):
        # prepare volumes, peaks and colors for drawing
        # these are per render frame or audio frame vars
        # so cannot be done in do_once()
        r_split = np.array_split(self.r, self.bands)
        if self.max:
            self.volumes = np.array([split.max() for split in r_split])
        else:
            self.volumes = np.array([split.mean() for split in r_split])
        self.volumes = np.append(self.volumes, self.volumes[0])

        if self.peak:
            self.peaks = self.peaks_filter.update(self.volumes)

        self.gradient_colors = [
            tuple(self.get_gradient_color(1 / self.bands * i).astype(int))
            for i in range(self.bands)
        ]

        if self.ring and self.spin:
            self.spin_value += self.impulse
            self.spin_value %= 360
            self.calc_ring_segments(self.spin_value)

    def draw_ring(self):
        for i in range(self.bands):
            if self.center:
                self.m_draw.polygon(
                    [
                        interpolate_point(
                            self.p_center, self.bandsc[i], self.volumes[i]
                        ),
                        interpolate_point(
                            self.p_center, self.bandsc[i + 1], self.volumes[i]
                        ),
                        self.p_center,
                    ],
                    fill=self.gradient_colors[i],
                )

                if self.peak:
                    self.m_draw.line(
                        [
                            interpolate_point(
                                self.p_center, self.bandscm[i], self.peaks[i]
                            ),
                            interpolate_point(
                                self.p_center,
                                self.bandscm[i + 1],
                                self.peaks[i + 1],
                            ),
                        ],
                        fill=(255, 255, 255),
                        width=self.peak_size,
                    )
            else:
                self.m_draw.polygon(
                    [
                        self.bandsc[i],
                        self.bandsc[i + 1],
                        interpolate_point(
                            self.bandscm[i], self.p_center, self.volumes[i]
                        ),
                    ],
                    fill=self.gradient_colors[i],
                    outline=tuple(
                        max(component - 1, 0)
                        for component in self.gradient_colors[i]
                    ),
                )

                if self.peak:
                    self.m_draw.line(
                        [
                            interpolate_point(
                                self.bandscm[i], self.p_center, self.peaks[i]
                            ),
                            interpolate_point(
                                self.bandscm[i + 1],
                                self.p_center,
                                self.peaks[i + 1],
                            ),
                        ],
                        fill=(255, 255, 255),
                        width=self.peak_size,
                    )

    def draw_normal(self):
        for i in range(self.bands):
            band_start, band_end = self.bandsx[i]
            volume_scaled = int(self.r_height * self.volumes[i])
            if self.center:
                # Calculate dimensions for the centered rectangle
                bottom = self.half_height - volume_scaled // 2
                top = self.half_height + volume_scaled // 2
            else:
                # Dimensions for the bottom to top rectangle
                bottom = 0
                top = volume_scaled

            self.m_draw.rectangle(
                (band_start, bottom, band_end, top),
                fill=self.gradient_colors[i],
            )

            # Draw the peak marker
            if self.peak:
                if self.center:
                    peak_scaled = int(self.half_height * self.peaks[i])
                    peak_end = int(peak_scaled + self.peak_size // 2)
                    self.m_draw.rectangle(
                        (
                            band_start,
                            self.half_height + peak_scaled,
                            band_end,
                            self.half_height + peak_end,
                        ),
                        fill=(255, 255, 255),
                    )
                    self.m_draw.rectangle(
                        (
                            band_start,
                            self.half_height - peak_end,
                            band_end,
                            self.half_height - peak_scaled,
                        ),
                        fill=(255, 255, 255),
                    )
                else:
                    peak_scaled = int(self.r_height * self.peaks[i])
                    peak_end = peak_scaled + self.peak_size

                    self.m_draw.rectangle(
                        (band_start, peak_scaled, band_end, peak_end),
                        fill=(255, 255, 255),
                    )

    def draw(self):
        # note we are leaving all math in float space until it gets clipped
        # down to int by Image draw functions

        if self.test:
            self.draw_test(self.m_draw)

        self.prep_frame_vars()

        if self.ring:
            self.draw_ring()
        else:
            self.draw_normal()

        self.roll_gradient()
