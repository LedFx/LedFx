import logging

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)


def stretch_2d_full(source, target):
    _LOGGER.warning("Stretch 2d full not implemented")


def stretch_2d_repeat(source, target):
    _LOGGER.warning("Stretch 1d repeat not implemented")


def stretch_1d_vertical(source, target):
    _LOGGER.warning("Stretch 1d vertical not implemented")


def stretch_1d_horizontal(source, target):
    _LOGGER.warning("Stretch 1d horizontal not implemented")


STRETCH_FUNCS_MAPPING = {
    "2d full": stretch_2d_full,
    "2d repeat": stretch_2d_repeat,
    "1d vertical": stretch_1d_vertical,
    "1d horizontal": stretch_1d_horizontal,
}


class Blender(AudioReactiveEffect):
    NAME = "Blender"
    # CATEGORY defines where in the UI the effect will be displayed in the effects list
    # "Classic" is a good default to start with, you can have anything here, but don't go
    # creating new categories without a good reason!
    CATEGORY = "Diagnostic"
    # HIDDEN_KEYS are keys that are not shown in the UI, it is a way to hide settings inherited from
    # the parent class, where you don't make use of them. So it does not confuse the user.
    HIDDEN_KEYS = ["background_color", "background_brightness", "blur"]

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mask_stretch",
                description="How to stretch the mask source pixles to the effect pixels",
                default="2d full",
            ): vol.In(list(STRETCH_FUNCS_MAPPING.keys())),
            vol.Optional(
                "background_stretch",
                description="How to stretch the mask source pixles to the effect pixels",
                default="2d full",
            ): vol.In(list(STRETCH_FUNCS_MAPPING.keys())),
            vol.Optional(
                "foreground_stretch",
                description="How to stretch the mask source pixles to the effect pixels",
                default="2d full",
            ): vol.In(list(STRETCH_FUNCS_MAPPING.keys())),
            vol.Optional(
                "mask",
                description="The virtual from which to source the mask",
                default="",
            ): str,
            vol.Optional(
                "foreground",
                description="The virtual from which to source the foreground",
                default="",
            ): str,
            vol.Optional(
                "background",
                description="The virtual from which to source the background",
                default="",
            ): str,
            vol.Optional(
                "invert_mask",
                description="Switch Foreground and Background",
                default=False,
            ): bool,
            vol.Optional(
                "bias_black",
                description="Treat anything below white as black for mask, default is anything above black is white",
                default=False,
            ): bool,
        }
    )

    # things you want to do on activation, when pixel count is known
    def on_activate(self, pixel_count):
        pass

    # things you want to happen when ever the config is updated
    # the first time through this function pixel_count is not known!
    def config_updated(self, config):
        # TODO: Ensure virtual names are mangled the same as during virtual creation,
        # for now rely on exactness
        self.mask = self._config["mask"]
        self.foreground = self._config["foreground"]
        self.background = self._config["background"]
        self.invert_mask = self._config["invert_mask"]
        self.bias_black = self._config["bias_black"]

        self.mask_stretch_func = STRETCH_FUNCS_MAPPING[
            self._config["mask_stretch"]
        ]
        self.foreground_stretch_func = STRETCH_FUNCS_MAPPING[
            self._config["foreground_stretch"]
        ]
        self.background_stretch_func = STRETCH_FUNCS_MAPPING[
            self._config["background_stretch"]
        ]

    def audio_data_updated(self, data):
        pass

    def render(self):

        # all virtual grabs are try as they might not exist yet, but may on the next frame

        try:
            mask_pixels = self._ledfx.virtuals._virtuals.get(
                self.mask
            ).assembled_frame
        except Exception:
            mask_pixels = np.zeros(np.shape(self.pixels))
            _LOGGER.info(f"Mask virtual not found: {self.mask} set to black")

        try:
            foreground_pixels = self._ledfx.virtuals._virtuals.get(
                self.foreground
            ).assembled_frame
        except Exception:
            foreground_pixels = np.zeros(np.shape(self.pixels))
            _LOGGER.info(
                f"Foreground virtual not found: {self.foreground} set to black"
            )

        try:
            background_pixels = self._ledfx.virtuals._virtuals.get(
                self.background
            ).assembled_frame
        except Exception:
            background_pixels = np.zeros(np.shape(self.pixels))
            _LOGGER.info(
                f"Background virtual not found: {self.background} set to black"
            )

        if self.bias_black:
            # Create a boolean mask where white pixels ([255.0, 255.0, 255.0]) are True, and black pixels are False
            mask = (mask_pixels == 255.0).all(axis=-1)
        else:
            # Create a boolean mask where any pixel that is not black ([0, 0, 0]) is True, and black pixels are False
            mask = (mask_pixels != 0).any(axis=-1)

        if self.invert_mask:
            mask = ~mask

        self.mask_stretch_func(1, 2)
        self.foreground_stretch_func(1, 2)
        self.background_stretch_func(1, 2)

        # Initialize result with zeros (black) of the size of background_pixels
        # TODO: Move all sizing to a stretch model with user options
        # TODO: will support 1d / 2d and various directions of stretch
        blending_pixels = np.zeros_like(self.pixels)

        # Apply the inverse of the mask to source2
        blending_pixels[~mask] = background_pixels[~mask]

        # Apply the mask to source3
        blending_pixels[mask] = foreground_pixels[mask]

        # Assign the final result
        self.pixels = blending_pixels
