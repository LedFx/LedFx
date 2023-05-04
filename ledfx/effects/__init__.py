import colorsys
import logging
import threading

# from ledfx.effects.audio import FREQUENCY_RANGES
from functools import lru_cache

import numpy as np
import voluptuous as vol

from ledfx.color import parse_color, validate_color
from ledfx.utils import BaseRegistry, RegistryLoader

_LOGGER = logging.getLogger(__name__)


class DummyEffect:
    config = vol.Schema({})
    _active = True
    is_active = _active
    NAME = name = ""

    def __init__(self, pixel_count):
        self.pixels = np.zeros((pixel_count, 3))

    def _render(self):
        pass

    def render(self):
        pass

    def get_pixels(self):
        return self.pixels

    def activate(self):
        pass

    def deactivate(self):
        pass


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


def blur_pixels(pixels, sigma):
    rgb_array = pixels.T
    rgb_array[0] = smooth(rgb_array[0], sigma)
    rgb_array[1] = smooth(rgb_array[1], sigma)
    rgb_array[2] = smooth(rgb_array[2], sigma)
    return rgb_array.T


@lru_cache(maxsize=1024)
def _gaussian_kernel1d(sigma, order, array_len):
    """
    Produces a 1D Gaussian or Gaussian-derivative filter kernel as a numpy array.

    Args:
        sigma (float): The standard deviation of the filter.
        order (int): The derivative-order to use. 0 indicates a Gaussian function, 1 a 1st order derivative, etc.
        radius (int): The kernel produced will be of length (2*radius+1)

    Returns:
        Array of length (2*radius+1) containing the filter kernel.
    """

    # Choose a radius for the filter kernel large enough to include all significant elements. Using
    # a radius of 4 standard deviations (rounded to int) will only truncate tail values that are of
    # the order of 1e-5 or smaller. For very small sigma values, just use a minimal radius.
    # trapping very small values of sigma to arbitarily 0.00001 to preven div zero crash
    sigma = max(0.00001, sigma)
    radius = max(1, int(round(4.0 * sigma)))
    radius = min(int((array_len - 1) / 2), radius)
    radius = max(radius, 1)

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


def fast_blur_pixels(pixels, sigma):
    if len(pixels) == 0:
        raise ValueError("Cannot smooth an empty array")
    kernel = _gaussian_kernel1d(sigma, 0, len(pixels))
    pixels[:, 0] = np.convolve(pixels[:, 0], kernel, mode="same")
    pixels[:, 1] = np.convolve(pixels[:, 1], kernel, mode="same")
    pixels[:, 2] = np.convolve(pixels[:, 2], kernel, mode="same")
    return pixels


def fast_blur_array(array, sigma):
    if len(array) == 0:
        raise ValueError("Cannot smooth an empty array")
    kernel = _gaussian_kernel1d(sigma, 0, len(array))
    return np.convolve(array, kernel, mode="same")


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
    # over ride in effect children to hide existing keys from UI
    HIDDEN_KEYS = None
    # over ride in effect children AND add an "advanced" bool to schema
    # to show or hide in UI
    ADVANCED_KEYS = None
    # over ride in effect children to allow edit and show others
    PERMITTED_KEYS = None
    _config = None
    _active = False
    _virtual = None

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
                description="Apply a background color",
                default="#000000",
            ): validate_color,
            vol.Optional(
                "background_brightness",
                description="Brightness of the background color",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        }
    )

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self._config = {}
        self.update_config(config)
        self.lock = threading.Lock()

    def __del__(self):
        if self._active:
            self.deactivate()

    def activate(self, virtual):
        """Attaches an output channel to the effect"""
        self._virtual = virtual
        self.pixels = np.zeros((virtual.pixel_count, 3))
        # Iterate all the base classes and check to see if the base
        # class has an on_activate method. If so, call it
        valid_classes = list(type(self).__bases__)
        valid_classes.append(type(self))
        for base in valid_classes:
            if hasattr(base, "on_activate"):
                base.on_activate(self, virtual.pixel_count)

        self._active = True
        _LOGGER.info(f"Effect {self.NAME} activated.")

    def deactivate(self):
        """Detaches an output channel from the effect"""
        self.pixels = None
        self._active = False

        _LOGGER.info(f"Effect {self.NAME} deactivated.")

    def update_config(self, config):
        # TODO: Sync locks to ensure everything is thread safe

        validated_config = type(self).schema()(config)
        prior_config = self._config

        if self._config != {}:
            self._config = {**prior_config, **config}
        else:
            self._config = validated_config

        self._bg_color = (
            np.array(parse_color(self._config["background_color"]))
            * self._config["background_brightness"]
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

        _LOGGER.debug(
            f"Effect {self.NAME} config updated to {validated_config}."
        )

    def config_updated(self, config):
        """
        Optional event for when an effect's config is updated. This
        should be used by the subclass only if they need to build up
        complex properties off the configuration, otherwise the config
        should just be referenced in the effect's loop directly
        """
        pass

    def _render(self):
        self.lock.acquire()
        self.render()
        self.lock.release()

    def render(self):
        """
        To be implemented by child effect
        Must act on self.pixels, setting the values of it
        The effect can use self.pixels to see the previous effect
        frame if it wants to use it for something
        """
        pass

    def get_pixels(self):
        if not hasattr(self, "pixels"):
            return

        pixels = np.copy(self.pixels)
        # Grab the config and store it here for use in the function - we use it a lot
        config = self._config

        # Apply some of the base output filters if necessary
        if config["flip"]:
            pixels = np.flipud(pixels)
        if config["mirror"]:
            pixels = np.concatenate(
                (pixels[-1 + len(pixels) % -2 :: -2], pixels[::2])
            )
        if config["background_color"]:
            pixels += self._bg_color
        if config["brightness"] is not None:
            np.multiply(
                pixels, config["brightness"], out=pixels, casting="unsafe"
            )

        # If the configured blur is greater than 0 and pixel_count > 3, apply blur
        # The matrix math requires > 3 pixels to work properly
        # And blurring with a less than 3 pixels seems... redundant
        # TODO: Handle RGBW properly
        if config["blur"] != 0.0 and self.pixel_count > 3:
            kernel = _gaussian_kernel1d(config["blur"], 0, len(pixels))

            # Blur the R,G,B portions of the pixel array
            # Lots of attempts at vectorisation/performance improvements here
            # This appears to be optimal from a readability/performance point of view
            # TODO: If we ever move to RGBW pixel arrays, uncomment the last line to operate on the W portion

            pixels[:, 0] = np.convolve(pixels[:, 0], kernel, mode="same")  # R
            pixels[:, 1] = np.convolve(pixels[:, 1], kernel, mode="same")  # G
            pixels[:, 2] = np.convolve(pixels[:, 2], kernel, mode="same")  # B
            # pixels[:, 3] = np.convolve(pixels[:, 3], kernel, mode="same") # W
        return pixels

    @property
    def is_active(self):
        """Return if the effect is currently active"""
        return self._active

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
