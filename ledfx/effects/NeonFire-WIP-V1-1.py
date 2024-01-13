import logging

import colorsys

import numpy as np
import PIL.Image as Image
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.twod import Twod

from ledfx.effects.hsv_effect import hsv_to_rgb 

_LOGGER = logging.getLogger(__name__)

# copy this file and rename it into the effects folder
# Anywhere you see template, replace it with your own class reference / name

def hsv2rgb(h,s,v):
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h,s,v))


class NeonFire_WIP_V1_1(Twod):
    NAME = "NeonFire WIP V1.1"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "color", description="Color of strip", default="#FF0000"
            ): validate_color,
            vol.Optional(
                "A switch",
                description="Does a boolean thing",
                default=False,
            ): bool,
            vol.Optional(
                "Mirroring",
                description="Mirror!",
                default=False,
            ): bool,
            vol.Optional(
                "HSV Colors",
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
                default=0.5,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "decay",
                description="Particle decay speed",
                default=0.02,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0001, max=0.1)),
            vol.Optional(
                "peak sensitivity",
                description="Peak sensitivity",
                default=0,
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
        }
    )


    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.bar = 0
        self.previousimage = 0
        self.even = False
        self.r_height = 0
        #self.decay = 0.02

        self.imagebuffer = Image.new("RGBA", (32,32),(0,0,0,0))
        self.paste = Image.new("RGBA", (32,32),(0,0,0,0))
        self.emptybuffer = Image.new("RGBA", (32,32),(0,0,0,0))

        
    def on_activate(self, pixel_count):
        self.r = np.zeros(pixel_count)
    

    def config_updated(self, config):
        super().config_updated(config)
        # copy over your configs here into variables
        self.a_switch = self._config["A switch"]
        self.mirroring = self._config["Mirroring"]
        self.power_func = self.POWER_FUNCS_MAPPING[
            self._config["frequency_range"]
        ]
        self.hsvcolor = self._config["HSV Colors"]
        self.color = np.array(parse_color(self._config["color"]), dtype=float)
        self.decay = self._config["decay"]
        self.peaksense = self._config["peak sensitivity"]

    def do_once(self):
        super().do_once()
        
        self.imagebuffer = Image.new("RGBA", (self.r_width, self.r_height),(0,0,0,0))
        self.pastebuffer = Image.new("RGBA", (self.r_width, self.r_height),(0,0,0,0))
        self.emptybuffer = Image.new("RGBA", (self.r_width, self.r_height),(0,0,0,0))
        
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

        if self.r_height > 0 :
            self.r = self.melbank(filtered=True, size=self.r_height)
        
    def prep_frame_vars(self):
    
        out = np.tile(self.r, (3, 1)).T
        np.clip(out, 0, 1, out=out)
        out_split = np.array_split(out, self.r_height, axis=0)
        
        
            
        
        
        tempbuffer = self.imagebuffer.copy()
        #tempbuffer = Image.blend(tempbuffer.copy(), self.emptybuffer.copy(), 0.03)
        tempbuffer = Image.blend(tempbuffer.copy(), self.emptybuffer.copy(), self.decay)
        #tempbuffer.convert("RGBa")
        self.imagebuffer = Image.new("RGBA", (self.r_width, self.r_height),(0,0,0,0))

        collo1 = self.imagebuffer.copy()
        collo2 = self.imagebuffer.copy()
        collo1.paste(tempbuffer, (1,0), tempbuffer)
        
        if self.even:
            collo2.paste(tempbuffer, (1,1), tempbuffer)
            
        
        self.imagebuffer = Image.alpha_composite(collo1, collo2)

        if len(out_split) >= self.r_height :
            for i in range(self.r_height):
                vol = out_split[i].max()
                pixelcolor = (int(self.color[0]*vol), int(self.color[1]*vol), int(self.color[2]*vol) , 255)

                if self.hsvcolor :
                    h = i/self.r_height
                    s = 1
                    #s = self.bar
                    if self.a_switch:
                        s = 1 - self.bar 
                    v = vol

                    rgbvalue = hsv2rgb(h, s, v)
                    
                    if self.peaksense > 0:
                        peakresult = int(255/self.peaksense + out_split[i].mean()*self.peaksense*255 )
                    else :
                        peakresult = 255
                    pixelcolor = ( rgbvalue[0], rgbvalue[1], rgbvalue[2], peakresult )



                self.imagebuffer.putpixel((0,i), pixelcolor)
            

    def modifybuffer(self):
        self.pastebuffer = self.imagebuffer.copy()

        if self.mirroring:
            reversebuffer = self.pastebuffer.transpose(method=Image.Transpose.FLIP_LEFT_RIGHT)
            #self.pastebuffer = Image.alpha_composite(self.pastebuffer, reversebuffer)
            self.pastebuffer = Image.composite(self.pastebuffer, reversebuffer, self.pastebuffer)

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

        self.prep_frame_vars()

        self.modifybuffer()
        
        
        self.matrix.paste(self.pastebuffer)
        
        #self.matrix.putpixel((24,24), (255,255,255))
        
        #if self.even:
        #    self.matrix.putpixel((16,16), (255,255,255))
        #else:
        #    self.matrix.putpixel((17,17), (255,255,255))
        #    
        self.even = np.invert(self.even)
      
 