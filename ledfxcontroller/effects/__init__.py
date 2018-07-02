import os
import sys
import colorsys
import pkgutil
import logging
import importlib
import numpy as np
import voluptuous as vol
from scipy.ndimage.filters import gaussian_filter1d
from ledfxcontroller.utils import MetaRegistry

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

class Effect(object, metaclass=MetaRegistry):
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
        vol.Optional('blur', default = 0.0): vol.Coerce(float),
        vol.Optional('flip', default = False): bool,
        vol.Optional('mirror', default = False): bool,
    })

    def __init__(self, config):
        pass

    def __del__(self):
        if self._active:
            self.deactivate()

    def activate(self, pixel_count):
        """Attaches an output channel to the effect"""
        self._pixels = np.zeros((pixel_count, 3))

        self.channel_updated(None)
        self._active = True

        _LOGGER.info("Effect {} activated.".format(self.NAME))

    def deactivate(self):
        """Detaches an output channel from the effect"""
        self._pixels = None
        self._active = False

        _LOGGER.info("Effect {} deactivated.".format(self.NAME))

    def update_config(self, config):
        # TODO: Sync locks to ensure everything is thread safe
        validated_config = type(self).get_schema()(config)
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

    def channel_updated(self, channel):
        """
        Optional event for when an effect's channel is updated. This
        shold be used by the subclass only if they need to build up
        complex properties off the device's channel, otherwise the channel
        should just be referenced in the effect's loop directly
        """
        pass

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

        return self._pixels

    @pixels.setter
    def pixels(self, pixels):
        """Sets the pixels for the channel"""
        if not self._active:
            raise Exception('Attempting to set pixels before effect is active')

        if isinstance(pixels, tuple):
            self._pixels = pixels
        elif isinstance(pixels, np.ndarray):

            # Apply some of the base output filters if necessary
            if self._config['blur'] != 0.0:
                pixels = blur_pixels(pixels=pixels, sigma=self._config['blur'])
            if self._config['flip']:
                pixels = flip_pixels(pixels)
            if self._config['mirror']:
                pixels = mirror_pixels(pixels)
            self._pixels = pixels
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


class EffectManager(object):
    def __init__(self):
        self.reload_effects()

    def reload_effects(self, force_reload = False):

        # First load all the effect modules
        package_directory = os.path.dirname(__file__)
        for (_, module_name, _) in pkgutil.iter_modules([package_directory]):
            module = importlib.import_module('.' + module_name, __package__)
            if force_reload:
                print("Reload module", module)
                importlib.reload(module)

        self._supported_effects = {}
        for effect in Effect.get_registry():
            self._supported_effects[effect.NAME.lower()] = effect

    def create_effect(self, name, config = {}):
        effect_class = self._supported_effects.get(name.lower())
        if effect_class:

            validated_config = effect_class.get_schema()(config)
            _LOGGER.info("Creating effect {} with config {}".format(
                name, validated_config))

            # TODO: Should we even bother passing in the config to init?
            # or should effects just only bother handling "configUpdated"?
            effect = effect_class(validated_config)
            effect.update_config(validated_config)

            return effect
        raise AttributeError('Couldn\'t find effect {}'.format(name))

    @property
    def supported_effects(self):
        return self._supported_effects