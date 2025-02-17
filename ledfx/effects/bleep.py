import logging
import timeit
from enum import Enum

import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects import Effect
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

RENDER_MAPPINGS = {
    "Points": "points_render",
    "Lines": "lines_render",
    "Fill": "fill_render",
}


class Bleeper:

    def __init__(self, shape, scroll_time, colors, points, points_linear):
        self.points = points
        self.points_linear = points_linear
        self.coords = np.zeros((self.points, 2))
        self.coords[:, 0] = self.points_linear
        self.coords[:, 1] = 0.5
        self.amplitudes = np.zeros(self.points)
        self.colors = colors
        self.shape = shape
        self.norm_shape = (self.shape[0] - 1, self.shape[1] - 1)
        self.scroll_time = scroll_time
        self.last_time = timeit.default_timer()
        self.progress = 0.0
        self.step_time = self.scroll_time / self.points

    def update(self, power):
        now = timeit.default_timer()
        delta_t = now - self.last_time
        self.progress = self.progress + delta_t
        # while loop this for multiple steps incase delays have built up debt
        while self.progress > self.step_time:
            self.progress = self.progress - self.step_time
            # roll all the values, and zero the first
            self.amplitudes = np.roll(self.amplitudes, 1)
            self.amplitudes[0] = power
        self.last_time = now

    def render(self, pixel_data, render_func, mirror):

        if render_func not in RENDER_MAPPINGS.values():
            _LOGGER.error(f"Invalid render function: {render_func}")
            return

        getattr(self, render_func)(pixel_data, mirror)

    def points_render(self, pixel_data, mirror):
        plot_coords = self.coords.copy()
        if mirror:
            plot_coords_top = plot_coords.copy()
            plot_coords_bottom = plot_coords.copy()
            plot_coords_top[:, 1] += self.amplitudes / 2
            plot_coords_bottom[:, 1] -= self.amplitudes / 2

            plot_coords_top = np.clip(plot_coords_top, 0, 1)
            plot_coords_bot = np.clip(plot_coords_bottom, 0, 1)
            plot_coords_top = np.round(
                plot_coords_top * self.norm_shape
            ).astype(int)
            pixel_data[plot_coords_top[:, 1], plot_coords_top[:, 0]] = (
                self.colors
            )
            plot_coords_bot = np.round(
                plot_coords_bot * self.norm_shape
            ).astype(int)
            pixel_data[plot_coords_bot[:, 1], plot_coords_bot[:, 0]] = (
                self.colors
            )
        else:
            plot_coords[:, 1] += -0.5 + self.amplitudes
            plot_coords = np.clip(plot_coords, 0, 1)
            plot_coords = np.round(plot_coords * self.norm_shape).astype(int)
            pixel_data[plot_coords[:, 1], plot_coords[:, 0]] = self.colors

    def lines_render(self, pixel_data, mirror):
        plot_coords = self.coords.copy()
        _LOGGER.error("Lines not implemented yet")
        pass

    def fill_render(self, pixel_data, mirror):
        plot_coords = self.coords.copy()
        _LOGGER.error("Fill not implemented yet")
        pass


class Bleep(Twod, GradientEffect):
    NAME = "Bleep"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mirror_effect",
                description="mirror effect",
                default=False,
            ): bool,
            vol.Optional(
                "scroll_time",
                description="Time to scroll the bleep",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=5.0)),
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "draw",
                description="How to plot the data",
                default="Points",
            ): vol.In(list(RENDER_MAPPINGS.keys())),
        }
    )

    def __init__(self, ledfx, config):
        self.points = 64
        super().__init__(ledfx, config)
        self.bar = 0
        self.power = 0

    def config_updated(self, config):
        super().config_updated(config)
        self.mirror_effect = self._config["mirror_effect"]
        self.scroll_time = self._config["scroll_time"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.render_func = RENDER_MAPPINGS[self._config["draw"]]

    def do_once(self):
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        # note that self.t_width and self.t_height are the physical dimensions
        self.points_linear = np.linspace(0, 1, self.points)
        colors = self.get_gradient_color_vectorized1d(self.points_linear)
        self.bleeper = Bleeper(
            (self.r_width, self.r_height),
            self.scroll_time,
            colors,
            self.points,
            self.points_linear,
        )

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()
        # grab the audio level
        self.power = getattr(data, self.power_func)()

    def draw(self):
        # this is where you pixel mash, it will be a black image object each call
        # a draw object is already attached
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

        self.bleeper.update(self.power)
        pixel_data = np.array(self.matrix)

        self.bleeper.render(pixel_data, self.render_func, self.mirror_effect)

        self.matrix = Image.fromarray(pixel_data)
