import colorsys
import logging

import numpy as np
import PIL.Image as Image
import PIL.ImageChops as ImageChops
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.twod import Twod

_LOGGER = logging.getLogger(__name__)

# copy this file and rename it into the effects folder
# Anywhere you see template, replace it with your own class reference / name

from ledfx.color import hsv_to_rgb


def hsv2rgb(h, s, v):
    # return hsv_to_rgb(h, s, v)
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h, s, v))


def rgb2hsv(rgb):
    # return colorsys.rgb_to_hsv(tuple(x/255 for x in rgb))
    return tuple(
        i
        for i in colorsys.rgb_to_hsv(
            rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        )
    )


def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))


def ease(value):
    return 0.5 * np.sin(np.pi * (value - 0.5)) + 0.5


def neonmod(self, h, s, v):
    # colormodes
    return ""


class neonfire(Twod):
    NAME = "NeonFire WIP"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="#FF5500"
            ): validate_color,
            vol.Optional(
                "peak_highlight",
                description="Highlights peaks",
                default=True,
            ): bool,
            vol.Optional(
                "mirroring",
                description="Mirror!",
                default=False,
            ): bool,
            vol.Optional(
                "hsv_colors",
                description="Dynamic color",
                default=False,
            ): bool,
            vol.Optional(
                "frequency_range",
                description="Frequency range for the beat detection",
                default="Lows (beat+bass)",
            ): vol.In(list(AudioReactiveEffect.POWER_FUNCS_MAPPING.keys())),
            vol.Optional(
                "multiplier",
                description="Applied to the audio input to amplify effect",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
            vol.Optional(
                "decay",
                description="Particle decay speed",
                default=0.02,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0001, max=0.5)),
            vol.Optional(
                "peak_sensitivity",
                description="Peak sensitivity",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
            vol.Optional(
                "render_multiplier",
                description="Internal rendersize multiplier, can be used to change the speed.",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
            vol.Optional(
                "alpha_stepsize",
                description="value of alpha reduction on particles per frame",
                default=16,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "peak_hue_shift",
                description="value of alpha reduction on particles per frame",
                default=0,
            ): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0)),
            vol.Optional(
                "intensity_hue_shift",
                description="value of alpha reduction on particles per frame",
                default=0,
            ): vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0)),
            vol.Optional(
                "use_stepsize",
                description="Wether to use alpha sepsize or decay speed",
                default=False,
            ): bool,
            vol.Optional(
                "diagonal_movement",
                description="Diagonal or straight pixel movement",
                default=True,
            ): bool,
            vol.Optional(
                "subtractive_decay",
                description="Multiplicative otherwise",
                default=True,
            ): bool,
            vol.Optional(
                "waterfall_mode",
                description="To replicate a waterfall, inspired by WMP",
                default=False,
            ): bool,
            vol.Optional(
                "clamp_peak",
                description="Clip peak-detection values",
                default=True,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0
        self.previousimage = 0
        self.even = False
        self.r_height = 0
        self.r_width = 0
        self.renderwidth = 0
        self.renderheight = 0
        self.out_split = ()

        self.imagebuffer = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        self.paste = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        self.emptybuffer = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        self.configchanged = True

    def fix_framebuffers(self):
        if self.r_width > 0 and self.r_height > 0:
            self.renderwidth = int(self.r_width * self.rendermultiplier)
            self.renderheight = int(self.r_height * self.rendermultiplier)
        else:
            self.renderwidth = 32
            self.renderheight = 32

        self.imagebuffer = Image.new(
            "RGBA", (self.renderwidth, self.renderheight), (0, 0, 0, 0)
        )
        self.pastebuffer = Image.new(
            "RGBA", (self.renderwidth, self.renderheight), (0, 0, 0, 0)
        )
        self.emptybuffer = Image.new(
            "RGBA", (self.renderwidth, self.renderheight), (0, 0, 0, 0)
        )

    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.showpeaks = self._config["peak_highlight"]
        self.mirroring = self._config["mirroring"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.hsvcolor = self._config["hsv_colors"]
        self.color = np.array(parse_color(self._config["color"]), dtype=float)
        self.decay = self._config["decay"]
        self.peaksense = self._config["peak_sensitivity"]
        self.rendermultiplier = self._config["render_multiplier"]
        self.diagmove = self._config["diagonal_movement"]
        self.stepsize = self._config["alpha_stepsize"]
        self.usestepsize = self._config["use_stepsize"]
        self.subtractive = self._config["subtractive_decay"]
        self.waterfall = self._config["waterfall_mode"]
        self.configchanged = True
        self.multiplier = self._config["multiplier"]
        self.clamp_peak = self._config["clamp_peak"]
        self.peak_hue_shift = self._config["peak_hue_shift"]
        self.intensity_hue_shift = self._config["intensity_hue_shift"]

        self.hsv = rgb2hsv(self.color)

    def do_once(self):
        super().do_once()

        self.fix_framebuffers()

        # defer things that can't be done when pixel_count is not known
        # this is probably important for most 2d matrix where you want
        # things to be initialized to led length and implied dimensions
        #
        # self.r_width and self.r_height should be used for the (r)ender space
        # as the self.matrix will not exist yet
        #
        # note that self.t_width and self.t_height are the physical dimensions
        #
        # this function will be called once on the first entry to render call
        # in base class twod AND every time there is a config_updated thereafter

    def audio_data_updated(self, data):
        # Grab your audio input here, such as bar oscillator

        self.bar = (
            getattr(data, self.power_func)() * self._config["multiplier"]
        )

        if self.configchanged:
            self.fix_framebuffers()
            self.configchanged = False

        if self.renderheight > 0:
            self.r = self.melbank(filtered=True, size=self.renderheight)
            self.prep_frame_vars()

    def prep_frame_vars(self):
        out = np.tile(self.r, (3, 1)).T
        np.clip(out, 0, 1, out=out)
        self.out_split = np.array_split(out, self.renderheight, axis=0)

    def renderframe(self):
        tempbuffer = self.imagebuffer.copy()
        pixelcolor = (255, 255, 255, 255)
        # rgbvalue = self.color
        # hsv = rgb2hsv(rgbvalue)

        if self.mirroring:
            rightlimit = int(0.5 * self.renderwidth)
        else:
            rightlimit = self.renderwidth

        if self.usestepsize:
            # TODO: measure performance difference
            if self.subtractive:
                # tempbuffer = ImageChops.overlay(tempbuffer.copy(), Image.new("RGBA", (self.renderwidth, self.renderheight),(0,0,0,self.stepsize)))
                tempbuffer = ImageChops.subtract(
                    tempbuffer.copy(),
                    Image.new(
                        "RGBA",
                        (self.renderwidth, self.renderheight),
                        (
                            self.stepsize,
                            self.stepsize,
                            self.stepsize,
                            self.stepsize,
                        ),
                    ),
                )

            else:
                tempbuffer = Image.blend(
                    tempbuffer.copy(),
                    Image.new(
                        "RGBA",
                        (self.renderwidth, self.renderheight),
                        (0, 0, 0, self.stepsize),
                    ),
                    self.stepsize / 255.0,
                )

        else:
            tempbuffer = Image.blend(
                tempbuffer.copy(), self.emptybuffer.copy(), self.decay
            )

        if not self.diagmove:
            self.imagebuffer = Image.new(
                "RGBA", (self.renderwidth, self.renderheight), (0, 0, 0, 0)
            )
            self.imagebuffer.paste(tempbuffer, (1, 0))

        else:
            self.imagebuffer = Image.new(
                "RGBA", (self.renderwidth, self.renderheight), (0, 0, 0, 0)
            )

            collo1 = self.imagebuffer.copy()
            collo2 = self.imagebuffer.copy()
            collo1.paste(tempbuffer, (1, 0))

            if self.even:
                collo2.paste(tempbuffer, (1, 1))
            else:
                collo2 = collo1.copy()

            if self.waterfall:
                croptransform = tuple(
                    (
                        int(0.125 * self.renderwidth),
                        0,
                        rightlimit,
                        self.renderheight,
                    )
                )
                waterfallmove = collo2.copy()
                waterfallmove = waterfallmove.crop(croptransform)
                collo2.paste(waterfallmove, (croptransform[0], 1))
                if self.even:
                    croptransform = tuple(
                        (
                            int(0.375 * self.renderwidth),
                            0,
                            rightlimit,
                            self.renderheight,
                        )
                    )
                    waterfallmove = collo2.copy()
                    waterfallmove = waterfallmove.crop(croptransform)
                    collo1.paste(waterfallmove, (croptransform[0], 1))

            # TODO: performance and comparative visual testing

            self.imagebuffer = Image.blend(
                collo1, collo2, 0.5
            )  # appears to have the best interaction with current alpha blending setups

        if len(self.out_split) >= self.renderheight:
            for i in range(self.renderheight):
                vol = self.out_split[i].max()
                # pixelcolor = (int(self.color[0]*vol), int(self.color[1]*vol), int(self.color[2]*vol) , 255)

                if self.hsvcolor:
                    h = (
                        self.peak_hue_shift * self.bar
                        + self.intensity_hue_shift * vol
                        + i / self.renderheight
                    )
                    s = 1
                    # s = self.bar
                    v = vol
                    if self.showpeaks:
                        if self.clamp_peak:
                            s = 1 - self.bar
                        else:
                            s = 0.25 - (ease(self.bar) - 0.5) * 2

                else:
                    h = (
                        self.peak_hue_shift * self.bar
                        + self.intensity_hue_shift * vol
                        + self.hsv[0]
                    )
                    s = self.hsv[1]
                    v = vol * self.hsv[2]
                    if self.showpeaks:
                        if self.clamp_peak:
                            s = self.hsv[1] - self.bar

                        else:
                            s = 0.25 - (ease(self.bar) - 0.5) * 2

                if self.waterfall:
                    # s = s*1.5-0.5
                    # s = 0.5-(self.bar-0.5)*2*self.multiplier
                    if self.clamp_peak:
                        s = clamp(
                            0.35
                            - (ease(v / 8 * 5 + self.bar / 8 * 3) - 0.175) * 2,
                            0.25,
                            1.0,
                        )
                    else:
                        s = 0.25 - (ease(self.bar) - 0.25) * 2
                    v = 0.1 + (v * 0.9)

                rgbvalue = hsv2rgb(h, s, v)
                # rgbvalue = hsv_to_rgb(h, s, v)

                if self.peaksense > 0:
                    peakresult = int(
                        255 / self.peaksense
                        + self.out_split[i].mean() * self.peaksense * 255
                    )
                else:
                    peakresult = 255
                pixelcolor = (
                    rgbvalue[0],
                    rgbvalue[1],
                    rgbvalue[2],
                    peakresult,
                )

                # TODO: move to paste array for writing to buffer at once.
                self.imagebuffer.putpixel((0, i), pixelcolor)

    def modifybuffer(self):
        self.pastebuffer = self.imagebuffer.copy()

        # bufferarray = np.array(self.pastebuffer)

        if self.mirroring:
            reversebuffer = self.pastebuffer.copy().transpose(
                method=Image.Transpose.FLIP_LEFT_RIGHT
            )
            # self.pastebuffer = Image.alpha_composite(self.pastebuffer, reversebuffer)

            # self.pastebuffer = Image.composite(self.pastebuffer, reversebuffer, self.pastebuffer)
            self.pastebuffer = ImageChops.add(self.pastebuffer, reversebuffer)

        if self.rendermultiplier > 1 and self.r_width > 0:
            self.pastebuffer = self.pastebuffer.resize(
                (self.r_width, self.r_height)
            )

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

        self.renderframe()

        self.modifybuffer()

        self.matrix.paste(self.pastebuffer)

        if self.test:
            self.draw_test(self.m_draw)

        self.even = np.invert(self.even)
