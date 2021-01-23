import colorsys
import logging

# from ledfx.effects.audio import FREQUENCY_RANGES
from functools import lru_cache

import numpy as np
import voluptuous as vol

from ledfx.color import COLORS
from ledfx.utils import BaseRegistry, RegistryLoader

_LOGGER = logging.getLogger(__name__)


def mix_colors(color_1, color_2, ratio):
    if np.array_equal(color_2, []):
        return (
            color_1[0] * (1 - ratio) + 0,
            color_1[1] * (1 - ratio) + 0,
            color_1[2] * (1 - ratio) + 0,
        )
    else:
        return (
            color_1[0] * (1 - ratio) + color_2[0] * ratio,
            color_1[1] * (1 - ratio) + color_2[1] * ratio,
            color_1[2] * (1 - ratio) + color_2[2] * ratio,
        )


def fill_solid(pixels, color):
    pixels[
        :,
    ] = color


def fill_rainbow(pixels, initial_hue, delta_hue):
    hue = initial_hue
    sat = 0.95
    val = 1.0
    for i in range(0, len(pixels)):
        pixels[i, :] = tuple(
            int(i * 255) for i in colorsys.hsv_to_rgb(hue, sat, val)
        )
        hue = hue + delta_hue
    return pixels


def mirror_pixels(pixels):
    # TODO: Figure out some better logic here. Needs to reduce the signal
    # and reflect across the middle. The prior logic was broken for
    # non-uniform effects.
    mirror_shape = (np.shape(pixels)[0], 2, np.shape(pixels)[1])
    return (
        np.append(pixels[::-1], pixels, axis=0)
        .reshape(mirror_shape)
        .mean(axis=1)
    )


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
    """
    Produces a 1D Gaussian or Gaussian-derivative filter kernel as a numpy array.

    Args:
        sigma (float): The standard deviation of the filter.
        order (int): The derivative-order to use. 0 indicates a Gaussian function, 1 a 1st order derivative, etc.
        radius (int): The kernel produced will be of length (2*radius+1)

    Returns:
        Array of length (2*radius+1) containing the filter kernel.
    """
    if order < 0:
        raise ValueError("Order must non-negative")
    if not (isinstance(radius, int) or radius.is_integer()) or radius <= 0:
        raise ValueError("Radius must a positive integer")

    p = np.polynomial.Polynomial([0, 0, -0.5 / (sigma * sigma)])
    x = np.arange(-radius, radius + 1)
    phi_x = np.exp(p(x), dtype=np.double)
    phi_x /= phi_x.sum()

    if order > 0:
        # For Gaussian-derivative filters, the function must be derived one or more times.
        q = np.polynomial.Polynomial([1])
        p_deriv = p.deriv()
        for _ in range(order):
            # f(x) = q(x) * phi(x) = q(x) * exp(p(x))
            # f'(x) = (q'(x) + q(x) * p'(x)) * phi(x)
            q = q.deriv() + q * p_deriv
        phi_x *= q(x)

    return phi_x


def smooth(x, sigma):
    """
    Smooths a 1D array via a Gaussian filter.

    Args:
        x (array of floats): The array to be smoothed.
        sigma (float): The standard deviation of the smoothing filter to use.

    Returns:
        Array of same length as x.
    """

    if len(x) == 0:
        raise ValueError("Cannot smooth an empty array")

    # Choose a radius for the filter kernel large enough to include all significant elements. Using
    # a radius of 4 standard deviations (rounded to int) will only truncate tail values that are of
    # the order of 1e-5 or smaller. For very small sigma values, just use a minimal radius.
    kernel_radius = max(1, int(round(4.0 * sigma)))
    filter_kernel = _gaussian_kernel1d(sigma, 0, kernel_radius)

    # The filter kernel will be applied by convolution in 'valid' mode, which includes only the
    # parts of the convolution in which the two signals full overlap, i.e. where the shorter signal
    # is entirely contained within the longer signal, producing an output signal of length equal to
    # the difference in length between the two input signals, plus one. So the input signal must be
    # extended by mirroring the ends (to give realistic values for the first and last pixels after
    # smoothing) until len(x_mirrored) - len(w) + 1 = len(x). This requires adding (len(w)-1)/2
    # values to each end of the input. If len(x) < (len(w)-1)/2, then the mirroring will need to be
    # performed over multiple iterations, as the mirrors can only, at most, triple the length of x
    # each time they are applied.
    extended_input_len = len(x) + len(filter_kernel) - 1
    x_mirrored = x
    while len(x_mirrored) < extended_input_len:
        mirror_len = min(
            len(x_mirrored), (extended_input_len - len(x_mirrored)) // 2
        )
        x_mirrored = np.r_[
            x_mirrored[mirror_len - 1 :: -1],
            x_mirrored,
            x_mirrored[-1 : -(mirror_len + 1) : -1],
        ]

    # Convolve the extended input copy with the filter kernel to apply the filter.
    # Convolving in 'valid' mode clips includes only the parts of the convolution in which the two
    # signals full overlap, i.e. the shorter signal is entirely contained within the longer signal.
    # It produces an output of length equal to the difference in length between the two input
    # signals, plus one. So this relies on the assumption that len(s) - len(w) + 1 >= len(x).
    y = np.convolve(x_mirrored, filter_kernel, mode="valid")

    assert len(y) == len(x)

    return y


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
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "blur",
                description="Amount to blur the effect",
                default=0.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10)),
            vol.Optional(
                "flip", description="Flip the effect", default=False
            ): bool,
            vol.Optional(
                "mirror",
                description="Mirror the effect",
                default=False,
            ): bool,
            vol.Optional(
                "brightness",
                description="Brightness of strip",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                "background_color",
                description="Apply a background colour",
                default="black",
            ): vol.In(list(COLORS.keys())),
        }
    )

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

        _LOGGER.info(f"Effect {self.NAME} activated.")

    def deactivate(self):
        """Detaches an output channel from the effect"""
        self._pixels = None
        self._active = False

        _LOGGER.info(f"Effect {self.NAME} deactivated.")

    def update_config(self, config):
        # TODO: Sync locks to ensure everything is thread safe
        validated_config = type(self).schema()(config)
        self._config = validated_config

        self._bg_color = np.array(
            COLORS[self._config["background_color"]], dtype=float
        )

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

        _LOGGER.info(
            f"Effect {self.NAME} config updated to {validated_config}."
        )

        self.configured_blur = self._config["blur"]

    def config_updated(self, config):
        """
        Optional event for when an effect's config is updated. This
        should be used by the subclass only if they need to build up
        complex properties off the configuration, otherwise the config
        should just be referenced in the effect's loop directly
        """
        self.configured_blur = self._config["blur"]
        pass

    @property
    def is_active(self):
        """Return if the effect is currently active"""
        return self._active

    def get_pixels(self):
        return self.pixels

    @property
    def pixels(self):
        """Returns the pixels for the channel"""
        if not self._active:
            raise Exception(
                "Attempting to access pixels before effect is active"
            )

        return np.copy(self._pixels)

    @pixels.setter
    def pixels(self, pixels):
        """Sets the pixels for the channel"""
        if not self._active:
            _LOGGER.warning(
                "Attempting to set pixels before effect is active. Dropping."
            )
            return

        if isinstance(pixels, tuple):
            self._pixels = np.copy(pixels)
        elif isinstance(pixels, np.ndarray):

            # Apply some of the base output filters if necessary
            if self._config["flip"]:
                pixels = flip_pixels(pixels)
            if self._config["mirror"]:
                pixels = mirror_pixels(pixels)
            if self._config["background_color"]:
                # TODO: colours in future should have an alpha value, which would work nicely to apply to dim the background colour
                # for now, just set it a bit less bright.
                bg_brightness = np.max(pixels, axis=1)
                bg_brightness = (255 - bg_brightness) / 510
                _bg_color_array = np.tile(self._bg_color, (len(pixels), 1))
                pixels += np.multiply(_bg_color_array.T, bg_brightness).T
            if self._config["brightness"] is not None:
                pixels = brightness_pixels(pixels, self._config["brightness"])
            # If the configured blur is greater than 0 we need to blur it
            if self.configured_blur != 0.0:
                pixels = blur_pixels(pixels=pixels, sigma=self.configured_blur)
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

    PACKAGE_NAME = "ledfx.effects"

    def __init__(self, ledfx):
        super().__init__(ledfx=ledfx, cls=Effect, package=self.PACKAGE_NAME)
        self._ledfx.audio = None
