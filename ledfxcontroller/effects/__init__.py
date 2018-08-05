
from ledfxcontroller.utils import BaseRegistry, RegistryLoader
from scipy.ndimage.filters import gaussian_filter1d
import voluptuous as vol
import numpy as np
import importlib
import colorsys
import pkgutil
import logging
import sys
import os

_LOGGER = logging.getLogger(__name__)

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
    return np.concatenate((pixels[::-2,:], pixels[::2,:]), axis=0)

def flip_pixels(pixels):
    return np.flipud(pixels)

def blur_pixels(pixels, sigma):
    return gaussian_filter1d(pixels, axis=0, sigma=sigma)

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
        vol.Optional('blur', description='Amount to blur the effect', default = 0.0): vol.Coerce(float),
        vol.Optional('flip', description='Flip the effect', default = False): bool,
        vol.Optional('mirror', description='Mirror the effect', default = False): bool,
    })

    def __init__(self, config):
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
        shold be used by the subclass only if they need to build up
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
            raise Exception('Attempting to set pixels before effect is active')

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
            self._pixels = np.copy(pixels)
        else:
            raise TypeError()

        self._dirty = True

    @property
    def pixel_count(self):
        """Returns the number of pixels for the channel"""
        return len(self.pixels)

    @property
    def name(self):
        return self.NAME

class Effects(RegistryLoader):
    """Thin wrapper around the effect registry that manages effects"""

    PACKAGE_NAME = 'ledfxcontroller.effects'

    def __init__(self, ledfx):
        super().__init__(Effect, self.PACKAGE_NAME, ledfx)