import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image

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

    def __init__(
        self,
        shape,
        scroll_time,
        colors,
        points,
        points_linear,
        mirror,
        render_func,
    ):
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
        self.mirror = mirror
        self.render_func = render_func

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

    def render(self, m_draw, colors):
        list_plot_coords_top = None
        list_plot_coords_bot = None

        plot_coords_top = self.coords.copy()
        if self.mirror:
            plot_coords_bot = plot_coords_top.copy()
            plot_coords_top[:, 1] += self.amplitudes / 2
            plot_coords_bot[:, 1] -= self.amplitudes / 2

            plot_coords_top = np.clip(plot_coords_top, 0, 1)
            plot_coords_bot = np.clip(plot_coords_bot, 0, 1)
            plot_coords_top = np.round(plot_coords_top * self.norm_shape).astype(int)
            plot_coords_bot = np.round(plot_coords_bot * self.norm_shape).astype(int)
            list_plot_coords_top = [tuple(c) for c in plot_coords_top]
            list_plot_coords_bot = [tuple(c) for c in plot_coords_bot]
        else:
            plot_coords_top[:, 1] += -0.5 + self.amplitudes
            plot_coords_top = np.clip(plot_coords_top, 0, 1)
            plot_coords_top = np.round(plot_coords_top * self.norm_shape).astype(int)
            list_plot_coords_top = [tuple(c) for c in plot_coords_top]

        getattr(self, self.render_func)(m_draw, 
                                        list_plot_coords_top, 
                                        list_plot_coords_bot, 
                                        colors)

    def points_render(self, m_draw, list_plot_coords_top, list_plot_coords_bot, colors):
        if self.mirror:
            for xy, color in zip(list_plot_coords_top, [tuple(c) for c in colors]):
                m_draw.point(xy, fill=color)
            for xy, color in zip(list_plot_coords_bot, [tuple(c) for c in colors]):
                m_draw.point(xy, fill=color)
        else:
            for xy, color in zip(list_plot_coords_top, [tuple(c) for c in colors]):
                m_draw.point(xy, fill=color)

    def lines_render(self, m_draw, list_plot_coords_top, list_plot_coords_bot, colors):        
        if self.mirror:
            for start, end, color in zip(list_plot_coords_top,
                                         list_plot_coords_top[1:], 
                                         [tuple(c) for c in colors]):
                m_draw.line([start, end], fill=color, width=1)
            for start, end, color in zip(list_plot_coords_bot,
                                         list_plot_coords_bot[1:], 
                                         [tuple(c) for c in colors]):
                m_draw.line([start, end], fill=color, width=1)
        else:
            for start, end, color in zip([tuple(c) for c in list_plot_coords_top],
                                         [tuple(c) for c in list_plot_coords_top[1:]], 
                                         [tuple(c) for c in colors]):
                m_draw.line([start, end], fill=color, width=1)


    def fill_render(self, m_draw, list_plot_coords_top, list_plot_coords_bot, colors):
        if self.mirror:
            for (x0, y0), (x1, y1), (x2, y2), (x3, y3), color in zip(
                                                 list_plot_coords_top,
                                                 list_plot_coords_bot,
                                                 list_plot_coords_bot[1:], 
                                                 list_plot_coords_top[1:], 
                                                 [tuple(c) for c in colors]):
                m_draw.polygon([(x0, y0), (x1, y1), (x2, y2), (x3, y3)], fill=color)
        else:
            for (x0, y0), (x1, y1), color in zip(list_plot_coords_top,
                                         list_plot_coords_top[1:], 
                                         [tuple(c) for c in colors]):
                m_draw.polygon([(x0, 0), (x1, 0), (x1, y1), (x0, y0)], fill=color)

class Bleep(Twod, GradientEffect):
    NAME = "Bleep"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + ["gradient_roll"]
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mirror_effect",
                description="mirror effect",
                default=False,
            ): bool,
            vol.Optional(
                "grad_power",
                description="Use gradient in power dimension instead of time",
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
            vol.Optional(
                "points",
                description="How many historical points to capture",
                default=64,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=64))
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0
        self.power = 0

    def config_updated(self, config):
        super().config_updated(config)
        self.points = self._config["points"]
        self.mirror_effect = self._config["mirror_effect"]
        self.grad_power = self._config["grad_power"]
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
            self.mirror_effect,
            self.render_func,
        )

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator
        self.bar = data.bar_oscillator()
        # grab the audio level
        self.power = getattr(data, self.power_func)()

    def draw(self):
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        if self.test:
            self.draw_test(self.m_draw)

        self.bleeper.update(self.power)

        if self.grad_power:
            colors = self.get_gradient_color_vectorized1d(
                self.bleeper.amplitudes
            )
        else:
            colors = self.bleeper.colors

        colors = np.clip(colors, 0, 255).astype(int)
        self.bleeper.render(self.m_draw, colors)
