import logging

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.utils.logsec import LogSec

_LOGGER = logging.getLogger(__name__)


class BlendVirtual:
    def __init__(self, virtual_id, _virtuals, fallback_shape, pixels_shape):
        self.target_rows = fallback_shape[0]
        self.target_columns = fallback_shape[1]
        # all virtual grabs are try as they might not exist yet, but may on the next frame
        try:
            virtual = _virtuals.get(virtual_id)
            self.pixels = virtual.assembled_frame
            self.rows = virtual.config["rows"]
            self.columns = int(virtual.pixel_count / self.rows)
            self.matching = (
                self.rows == fallback_shape[0]
                and self.columns == fallback_shape[1]
            )
        except Exception:
            self.pixels = np.zeros(pixels_shape)
            self.rows = fallback_shape[0]
            self.columns = fallback_shape[1]
            self.matching = True


def stretch_2d_full(blend_virtual):
    if blend_virtual.matching:
        return blend_virtual.pixels

    # Reshape the 1D array into a 2D array (rows, columns, 3)
    source_pixels = blend_virtual.pixels.reshape(
        (blend_virtual.rows, blend_virtual.columns, 3)
    )

    # Create target grid for the new pixel positions
    row_scale = np.linspace(
        0, blend_virtual.rows - 1, blend_virtual.target_rows
    )
    col_scale = np.linspace(
        0, blend_virtual.columns - 1, blend_virtual.target_columns
    )

    # Get the floor and ceiling indices for the scaled positions
    row_floor = np.floor(row_scale).astype(int)
    row_ceil = np.minimum(
        np.ceil(row_scale).astype(int), blend_virtual.rows - 1
    )
    col_floor = np.floor(col_scale).astype(int)
    col_ceil = np.minimum(
        np.ceil(col_scale).astype(int), blend_virtual.columns - 1
    )

    # Get the fractional parts for interpolation
    row_frac = row_scale - row_floor
    col_frac = col_scale - col_floor

    # Perform bilinear interpolation using broadcasting
    top_left = source_pixels[np.ix_(row_floor, col_floor)]
    top_right = source_pixels[np.ix_(row_floor, col_ceil)]
    bottom_left = source_pixels[np.ix_(row_ceil, col_floor)]
    bottom_right = source_pixels[np.ix_(row_ceil, col_ceil)]

    top = top_left * (1 - col_frac[:, None]) + top_right * col_frac[:, None]
    bottom = (
        bottom_left * (1 - col_frac[:, None])
        + bottom_right * col_frac[:, None]
    )
    interpolated = (
        top * (1 - row_frac[:, None, None]) + bottom * row_frac[:, None, None]
    )

    # Reshape to a 2D array with shape (target_rows * target_columns, 3)
    return interpolated.reshape(
        (blend_virtual.target_rows * blend_virtual.target_columns, 3)
    )


def stretch_2d_tile(blend_virtual):
    if blend_virtual.matching:
        return blend_virtual.pixels

    # Reshape the 1D array into a 2D array (rows, columns, 3)
    source_pixels = blend_virtual.pixels.reshape(
        (blend_virtual.rows, blend_virtual.columns, 3)
    )

    # Calculate how many times each row and column should be repeated to fill the target size
    row_repeats = blend_virtual.target_rows // blend_virtual.rows + 1
    col_repeats = blend_virtual.target_columns // blend_virtual.columns + 1

    # Tile the pixels by repeating the array in both row and column dimensions
    tiled_pixels = np.tile(source_pixels, (row_repeats, col_repeats, 1))

    # Slice the tiled pixels to match the exact target shape
    tiled_pixels = tiled_pixels[
        : blend_virtual.target_rows, : blend_virtual.target_columns, :
    ]

    # Reshape to a 2D array with shape (target_rows * target_columns, 3)
    return tiled_pixels.reshape(
        (blend_virtual.target_rows * blend_virtual.target_columns, 3)
    )


def stretch_1d_vertical(blend_virtual):
    _LOGGER.warning("Stretch 1d vertical not implemented")


def stretch_1d_horizontal(blend_virtual):
    _LOGGER.warning("Stretch 1d horizontal not implemented")


STRETCH_FUNCS_MAPPING = {
    "2d full": stretch_2d_full,
    "2d tile": stretch_2d_tile,
    "1d vertical": stretch_1d_vertical,
    "1d horizontal": stretch_1d_horizontal,
}


class Blender(AudioReactiveEffect, LogSec):
    NAME = "Blender"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = ["background_color", "background_brightness", "blur"]
    ADVANCED_KEYS = LogSec.ADVANCED_KEYS + ["bias_black"]

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

    def on_activate(self, pixel_count):
        # TODO: refactor to shape tuples instead of rows and columns
        self.rows = self._virtual.config["rows"]
        self.columns = int(self.pixel_count / self.rows)
        self.pixels_shape = np.shape(self.pixels)

    def config_updated(self, config):
        # TODO: Ensure virtual names are mangled the same as during virtual creation,
        # for now rely on exactness from user or front end
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

        self.log_sec()

        blend_mask = BlendVirtual(
            self.mask,
            self._ledfx.virtuals._virtuals,
            (self.rows, self.columns),
            self.pixels_shape,
        )
        blend_fore = BlendVirtual(
            self.foreground,
            self._ledfx.virtuals._virtuals,
            (self.rows, self.columns),
            self.pixels_shape,
        )
        blend_back = BlendVirtual(
            self.background,
            self._ledfx.virtuals._virtuals,
            (self.rows, self.columns),
            self.pixels_shape,
        )

        mask_pixels = self.mask_stretch_func(blend_mask)
        foreground_pixels = self.foreground_stretch_func(blend_fore)
        background_pixels = self.background_stretch_func(blend_back)

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

        self.try_log()
