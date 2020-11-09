from ledfx.utils import BaseRegistry, RegistryLoader
#from ledfx.effects.audio import FREQUENCY_RANGES
from functools import lru_cache
import voluptuous as vol
import numpy as np
import importlib
import colorsys
import pkgutil
import logging
import sys
import os

_LOGGER = logging.getLogger(__name__)

def mix_colors(color_1, color_2, ratio):
    if np.array_equal(color_2,[]):
       return (color_1[0] * (1-ratio) + 0,
            color_1[1] * (1-ratio) + 0,
            color_1[2] * (1-ratio) + 0)	
    else:
        return (color_1[0] * (1-ratio) + color_2[0] * ratio,
            color_1[1] * (1-ratio) + color_2[1] * ratio,
            color_1[2] * (1-ratio) + color_2[2] * ratio)

def fill_solid(pixels, color):
    pixels[:,] = color

def fill_rainbow(pixels, initial_hue, delta_hue):
    hue = initial_hue
    sat = 0.95
    val = 1.0
    for i in range(0,len(pixels)):
        pixels[i,:] = tuple(int(i * 255) for i in colorsys.hsv_to_rgb(hue, sat, val))
        hue = hue + delta_hue
    return pixels

def mirror_pixels(pixels):
    # TODO: Figure out some better logic here. Needs to reduce the signal 
    # and reflect across the middle. The prior logic was broken for
    # non-uniform effects.
    mirror_shape = (np.shape(pixels)[0], 2, np.shape(pixels)[1])
    return np.append(pixels[::-1], pixels, axis=0).reshape(mirror_shape).mean(axis = 1)

def flip_pixels(pixels):
    return np.flipud(pixels)

def blur_pixels(pixels, sigma):
    rgb_array = pixels.T
    rgb_array[0] = smooth(rgb_array[0], sigma)
    rgb_array[1] = smooth(rgb_array[1], sigma)
    rgb_array[2] = smooth(rgb_array[2], sigma)
    return rgb_array.T

def brightness_pixels(pixels, brightness):
    pixels = np.multiply(pixels, brightness, out=pixels, casting="unsafe")
    return pixels

@lru_cache(maxsize=32)
def _gaussian_kernel1d(sigma, order, radius):
    if order < 0:
        raise ValueError('order must be non-negative')
    p = np.polynomial.Polynomial([0, 0, -0.5 / (sigma * sigma)])
    x = np.arange(-radius, radius + 1)
    phi_x = np.exp(p(x), dtype=np.double)
    phi_x /= phi_x.sum()
    if order > 0:
        q = np.polynomial.Polynomial([1])
        p_deriv = p.deriv()
        for _ in range(order):
            # f(x) = q(x) * phi(x) = q(x) * exp(p(x))
            # f'(x) = (q'(x) + q(x) * p'(x)) * phi(x)
            q = q.deriv() + q * p_deriv
        phi_x *= q(x)
    return phi_x

def smooth(x, sigma):
    lw = int(4.0 * float(sigma) + 0.5)
    w = _gaussian_kernel1d(sigma, 0, lw)
    window_len = len(w)

    s = np.r_[x[window_len-1:0:-1],x,x[-1:-window_len:-1]]
    y = np.convolve(w/w.sum(),s,mode='valid')

    if window_len < len(x):
        return y[(window_len//2):-(window_len//2)]
    return y[0:len(x)]

@BaseRegistry.no_registration
class Effect(BaseRegistry):
    """
    Manages an effect
    """
    NAME = ""
    _pixels = None
    _dirty = False
    _config = None
    _active = False

    # Basic effect properties that can be applied to all effects
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('blur', description='Amount to blur the effect', default = 0.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
        vol.Optional('flip', description='Flip the effect', default = False): bool,
        vol.Optional('mirror', description='Mirror the effect', default = False): bool,
        vol.Optional('brightness', description='Brightness of strip', default = 1.0): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
    })

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._dirty_callback = None
        self.update_config(config)

    def __del__(self):
        if self._active:
            self.deactivate()

    def activate(self, pixel_count):
        """Attaches an output channel to the effect"""
        self._pixels = np.zeros((pixel_count, 3))
        self._active = True

        _LOGGER.info("Effect {} activated.".format(self.NAME))

    def deactivate(self):
        """Detaches an output channel from the effect"""
        self._pixels = None
        self._active = False

        _LOGGER.info("Effect {} deactivated.".format(self.NAME))

    def update_config(self, config):
        # TODO: Sync locks to ensure everything is thread safe
        validated_config = type(self).schema()(config)
        self._config = validated_config

        def inherited(cls, method):
            if hasattr(cls, method) and hasattr(super(cls, cls), method):
                return cls.foo == super(cls).foo
            return False

        # Iterate all the base classes and check to see if there is a custom
        # implementation of config updates. If to notify the base class.
        valid_classes = list(type(self).__bases__)
        valid_classes.append(type(self))
        for base in valid_classes:
            if base.config_updated != super(base, base).config_updated:
                base.config_updated(self, self._config)

        _LOGGER.info("Effect {} config updated to {}.".format(
            self.NAME, validated_config))

    def config_updated(self, config):
        """
        Optional event for when an effect's config is updated. This
        should be used by the subclass only if they need to build up
        complex properties off the configuration, otherwise the config
        should just be referenced in the effect's loop directly
        """
        pass

    @property
    def is_active(self):
        """Return if the effect is currently active"""
        return self._active

    @property
    def pixels(self):
        """Returns the pixels for the channel"""
        if not self._active:
            raise Exception('Attempting to access pixels before effect is active')

        return np.copy(self._pixels)

    @pixels.setter
    def pixels(self, pixels):
        """Sets the pixels for the channel"""
        if not self._active:
            _LOGGER.warning('Attempting to set pixels before effect is active. Dropping.')
            return

        if isinstance(pixels, tuple):
            self._pixels = np.copy(pixels)
        elif isinstance(pixels, np.ndarray):

            # Apply some of the base output filters if necessary
            if self._config['blur'] != 0.0:
                pixels = blur_pixels(pixels=pixels, sigma=self._config['blur'])
            if self._config['flip']:
                pixels = flip_pixels(pixels)
            if self._config['mirror']:
                pixels = mirror_pixels(pixels)
            if self._config['brightness']:
                pixels = brightness_pixels(pixels, self._config['brightness'])
            self._pixels = np.copy(pixels)
        else:
            raise TypeError()

        self._dirty = True

        
        if self._dirty_callback:
            self._dirty_callback()

    def setDirtyCallback(self, callback):
        self._dirty_callback = callback

    @property
    def pixel_count(self):
        """Returns the number of pixels for the channel"""
        return len(self.pixels)

    @property
    def name(self):
        return self.NAME

class Effects(RegistryLoader):
    """Thin wrapper around the effect registry that manages effects"""

    PACKAGE_NAME = 'ledfx.effects'

    def __init__(self, ledfx):
        super().__init__(ledfx = ledfx, cls = Effect, package = self.PACKAGE_NAME)
        self._ledfx.audio = None
