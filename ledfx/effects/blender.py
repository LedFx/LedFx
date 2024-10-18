import logging

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)


def stretch_2d_full(source_pixels, target_rows, target_columns, source_rows, source_columns):
    if target_rows == source_rows and target_columns == source_columns:
        return source_pixels

    # Reshape the 1D array into a 2D array (rows, columns, 3)
    source_pixels = source_pixels.reshape((source_rows, source_columns, 3))

    # Create target grid for the new pixel positions
    row_scale = np.linspace(0, source_rows - 1, target_rows)
    col_scale = np.linspace(0, source_columns - 1, target_columns)

    # Initialize the stretched pixel array
    stretched_pixels = np.zeros((target_rows, target_columns, 3))

    # Perform interpolation for each channel (RGB)
    for i in range(3):  # Iterate over the RGB channels
        for row_idx, row in enumerate(row_scale):
            for col_idx, col in enumerate(col_scale):
                # Get the floor and ceiling of the scaled positions
                row_floor = int(np.floor(row))
                row_ceil = min(int(np.ceil(row)), source_rows - 1)
                col_floor = int(np.floor(col))
                col_ceil = min(int(np.ceil(col)), source_columns - 1)

                # Get the fractional parts for interpolation
                row_frac = row - row_floor
                col_frac = col - col_floor

                # Bilinear interpolation
                top_left = source_pixels[row_floor, col_floor, i]
                top_right = source_pixels[row_floor, col_ceil, i]
                bottom_left = source_pixels[row_ceil, col_floor, i]
                bottom_right = source_pixels[row_ceil, col_ceil, i]

                top = top_left * (1 - col_frac) + top_right * col_frac
                bottom = bottom_left * (1 - col_frac) + bottom_right * col_frac
                value = top * (1 - row_frac) + bottom * row_frac

                # Assign the interpolated value to the stretched array
                stretched_pixels[row_idx, col_idx, i] = value

    # Reshape to a 2D array with shape (target_rows * target_columns, 3)
    return stretched_pixels.reshape((target_rows * target_columns, 3))

def stretch_2d_repeat(source_pixels, target_rows, target_columns, source_rows, source_columns):
    _LOGGER.warning("Stretch 1d repeat not implemented")


def stretch_1d_vertical(source_pixels, target_rows, target_columns, source_rows, source_columns):
    _LOGGER.warning("Stretch 1d vertical not implemented")


def stretch_1d_horizontal(source_pixels, target_rows, target_columns, source_rows, source_columns):
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
        self.rows = self._virtual.config["rows"]
        self.columns = int(self.pixel_count / self.rows)

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
            mask_rows = self._ledfx.virtuals._virtuals.get(self.mask).config["rows"]
            mask_columns = int(self._ledfx.virtuals._virtuals.get(self.mask).pixel_count / mask_rows)
        except Exception:
            mask_pixels = np.zeros(np.shape(self.pixels))
            mask_rows = self.rows
            mask_columns = self.columns
            _LOGGER.info(f"Mask virtual not found: {self.mask} set to black")

        try:
            foreground_pixels = self._ledfx.virtuals._virtuals.get(
                self.foreground
            ).assembled_frame
            foreground_rows = self._ledfx.virtuals._virtuals.get(self.foreground).config["rows"]
            foreground_columns = int(self._ledfx.virtuals._virtuals.get(self.foreground).pixel_count / foreground_rows)
        except Exception:
            foreground_pixels = np.zeros(np.shape(self.pixels))
            foreground_rows = self.rows
            foreground_columns = self.columns
            _LOGGER.info(
                f"Foreground virtual not found: {self.foreground} set to black"
            )

        try:
            background_pixels = self._ledfx.virtuals._virtuals.get(
                self.background
            ).assembled_frame
            background_rows = self._ledfx.virtuals._virtuals.get(self.background).config["rows"]
            background_columns = int(self._ledfx.virtuals._virtuals.get(self.background).pixel_count / background_rows)
        except Exception:
            background_pixels = np.zeros(np.shape(self.pixels))
            background_rows = self.rows
            background_columns = self.columns
            _LOGGER.info(
                f"Background virtual not found: {self.background} set to black"
            )

        mask_pixels = self.mask_stretch_func(mask_pixels, self.rows, self.columns, mask_rows, mask_columns)
        foreground_pixels = self.foreground_stretch_func(foreground_pixels, self.rows, self.columns, foreground_rows, foreground_columns)
        background_pixels = self.background_stretch_func(background_pixels, self.rows, self.columns, background_rows, background_columns)

        if self.bias_black:
            # Create a boolean mask where white pixels ([255.0, 255.0, 255.0]) are True, and black pixels are False
            mask = (mask_pixels == 255.0).all(axis=-1)
        else:
            # Create a boolean mask where any pixel that is not black ([0, 0, 0]) is True, and black pixels are False
            mask = (mask_pixels != 0).any(axis=-1)

        if self.invert_mask:
            mask = ~mask

        # Initialize result with zeros (black) of the size of self as target
        # by now, our data sets should all be manipulated to the same size
        blending_pixels = np.zeros_like(self.pixels)

        # Apply the inverse of the mask to source2
        blending_pixels[~mask] = background_pixels[~mask]

        # Apply the mask to source3
        blending_pixels[mask] = foreground_pixels[mask]

        # Assign the final result
        self.pixels = blending_pixels
