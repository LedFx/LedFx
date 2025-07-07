import logging
import timeit

import numpy as np
import voluptuous as vol
from PIL import Image, ImageDraw

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
    """
    The Bleeper class supports the rolling window of values and mask render
    modes associated with the bleep effect. It could be used to support
    multiple bleepers in one effect, though currently implemented as only one
    """

    def __init__(self):
        """
        Initialise the bleeper with a single amplitude value
        so that further init cycles can copy forward
        """
        self.amplitudes = np.zeros(1)

    def init(
        self,
        shape,
        scroll_time,
        points,
        points_linear,
        mirror,
        render_func,
        size,
    ):
        """
        Moved to a seperate init function to allow for re-init of the bleeper
        with out losing current amplitude data

        Args:
            shape (tuple): The shape of the mask image
            scroll_time (float): The time to scroll the bleep full width
            points (int): The number of historical points to capture
            points_linear (np.array): The linear space of the points
            mirror (bool): Mirror the bleep at render time
            render_func (str): The render function to use
            size (int): line width
        """
        self.points = points
        self.points_linear = points_linear
        self.coords = np.zeros((self.points, 2))
        self.coords[:, 0] = self.points_linear
        self.coords[:, 1] = 0.5

        # copy the old amplitudes into the new amplitudes, deal with mismatch lengths
        old_amplitudes = self.amplitudes.copy()
        self.amplitudes = np.zeros(self.points)
        length = min(len(self.amplitudes), len(old_amplitudes))
        self.amplitudes[:length] = old_amplitudes[:length]

        self.shape = shape
        self.norm_shape = (self.shape[0] - 1, self.shape[1] - 1)
        self.scroll_time = scroll_time
        # this is not an effect class inheritance, so we need to
        # use timeit to get the current time
        self.last_time = timeit.default_timer()
        self.progress = 0.0
        self.step_time = self.scroll_time / self.points
        self.mirror = mirror
        self.render_func = render_func
        self.size = size

    def update(self, power):
        """
        time invariant handling of the rolling points and update
        with latest power value

        """
        # this is not an effect class inheritance, so we need to
        # use timeit to get the current time
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

    def render(self, m_draw):
        """
        Prepare mask image
        Set up common render lists, account for mirror
        Call the currently active render_func

        args:
            m_draw (ImageDraw): The draw object to use for rendering

        returns:
            Image: The mask image to be merged with the gradient
        """
        mask_image = Image.new("L", self.shape, 0)
        mask_draw = ImageDraw.Draw(mask_image)

        list_plot_coords_top = None
        list_plot_coords_bot = None

        plot_coords_top = self.coords.copy()
        if self.mirror:
            plot_coords_bot = plot_coords_top.copy()
            plot_coords_top[:, 1] += self.amplitudes / 2
            plot_coords_bot[:, 1] -= self.amplitudes / 2

            plot_coords_top = np.clip(plot_coords_top, 0, 1)
            plot_coords_bot = np.clip(plot_coords_bot, 0, 1)
            plot_coords_top = np.round(
                plot_coords_top * self.norm_shape
            ).astype(int)
            plot_coords_bot = np.round(
                plot_coords_bot * self.norm_shape
            ).astype(int)
            list_plot_coords_top = [tuple(c) for c in plot_coords_top]
            list_plot_coords_bot = [tuple(c) for c in plot_coords_bot]
        else:
            plot_coords_top[:, 1] += -0.5 + self.amplitudes
            plot_coords_top = np.clip(plot_coords_top, 0, 1)
            plot_coords_top = np.round(
                plot_coords_top * self.norm_shape
            ).astype(int)
            list_plot_coords_top = [tuple(c) for c in plot_coords_top]

        getattr(self, self.render_func)(
            mask_draw, list_plot_coords_top, list_plot_coords_bot
        )
        return mask_image

    def points_render(
        self, m_draw, list_plot_coords_top, list_plot_coords_bot
    ):
        """
        Points style render of the bleep effect

        args:
            m_draw (ImageDraw): The draw object to use for rendering
            list_plot_coords_top (list): The list of top point coords
            list_plot_coords_bot (list): The list of bottom point coords
        """
        if self.mirror:
            for xy in list_plot_coords_top:
                m_draw.point(xy, fill=255)
            for xy in list_plot_coords_bot:
                m_draw.point(xy, fill=255)
        else:
            for xy in list_plot_coords_top:
                m_draw.point(xy, fill=255)

    def lines_render(self, m_draw, list_plot_coords_top, list_plot_coords_bot):
        """
        Lines style render of the bleep effect

        args:
            m_draw (ImageDraw): The draw object to use for rendering
            list_plot_coords_top (list): The list of top point coords
            list_plot_coords_bot (list): The list of bottom point coords
        """
        if self.mirror:
            for start, end in zip(
                list_plot_coords_top, list_plot_coords_top[1:]
            ):
                m_draw.line([start, end], fill=255, width=self.size)
            for start, end in zip(
                list_plot_coords_bot,
                list_plot_coords_bot[1:],
            ):
                m_draw.line([start, end], fill=255, width=self.size)
        else:
            for start, end in zip(
                [tuple(c) for c in list_plot_coords_top],
                [tuple(c) for c in list_plot_coords_top[1:]],
            ):
                m_draw.line([start, end], fill=255, width=self.size)

    def fill_render(self, m_draw, list_plot_coords_top, list_plot_coords_bot):
        """
        Filled Polygon style render of the bleep effect

        args:
            m_draw (ImageDraw): The draw object to use for rendering
            list_plot_coords_top (list): The list of top point coords
            list_plot_coords_bot (list): The list of bottom point coords
        """
        if self.mirror:
            for (x0, y0), (x1, y1), (x2, y2), (x3, y3) in zip(
                list_plot_coords_top,
                list_plot_coords_bot,
                list_plot_coords_bot[1:],
                list_plot_coords_top[1:],
            ):
                m_draw.polygon(
                    [(x0, y0), (x1, y1), (x2, y2), (x3, y3)], fill=255
                )
        else:
            for (x0, y0), (x1, y1) in zip(
                list_plot_coords_top,
                list_plot_coords_top[1:],
            ):
                m_draw.polygon(
                    [(x0, 0), (x1, 0), (x1, y1), (x0, y0)], fill=255
                )


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
                default="Lines",
            ): vol.In(list(RENDER_MAPPINGS.keys())),
            vol.Optional(
                "points",
                description="How many historical points to capture",
                default=64,
            ): vol.All(vol.Coerce(int), vol.Range(min=2, max=64)),
            vol.Optional(
                "size",
                description="Line width only",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bleeper = Bleeper()

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
        self.size = self._config["size"]

    def do_once(self):
        """
        Initalise vars for the bleep effect that are constants to a config change
        Done here as we need r_width and r_height to be set, which is not available in
        config_updated()
        """
        super().do_once()
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        # note that self.t_width and self.t_height are the physical dimensions
        self.points_linear = np.linspace(0, 1, self.points)

        lin_horizontal = np.linspace(0, 1, self.r_width)
        if self.mirror_effect:
            if self.r_height % 2 == 0:
                # even case
                half_height = np.linspace(1, 0, self.r_height // 2)
                lin_mirrored = np.concatenate((half_height, half_height[::-1]))
            else:
                # odd case
                half_height = np.linspace(1, 0, (self.r_height // 2) + 1)
                lin_mirrored = np.concatenate(
                    (half_height, half_height[::-1][1:])
                )
            lin_vertical = lin_mirrored
        else:
            lin_vertical = np.linspace(0, 1, self.r_height)

        self.bleeper.init(
            (self.r_width, self.r_height),
            self.scroll_time,
            self.points,
            self.points_linear,
            self.mirror_effect,
            self.render_func,
            self.size,
        )

        # make the gradient image that we will mask against
        self.gradient_image = Image.new("RGB", (self.r_width, self.r_height))
        self.gradient_draw = ImageDraw.Draw(self.gradient_image)
        if self.grad_power:
            colors = self.get_gradient_color_vectorized1d(lin_vertical).astype(
                int
            )
            for y in range(self.r_height):
                self.gradient_draw.line(
                    [(0, y), (self.r_width - 1, y)],
                    fill=tuple(colors[y]),
                    width=1,
                )
        else:
            colors = self.get_gradient_color_vectorized1d(
                lin_horizontal
            ).astype(int)
            for x in range(self.r_width):
                self.gradient_draw.line(
                    [(x, 0), (x, self.r_height - 1)],
                    fill=tuple(colors[x]),
                    width=1,
                )

    def audio_data_updated(self, data):
        if not self.init:
            self.bleeper.update(getattr(data, self.power_func)())

    def draw(self):
        # self.matrix is the Image object
        # self.m_draw is the attached draw object

        if self.test:
            self.draw_test(self.m_draw)

        mask = self.bleeper.render(self.m_draw)
        self.matrix = Image.composite(self.gradient_image, self.matrix, mask)
