import logging
import timeit

import numpy as np
import voluptuous as vol

from ledfx.effects.audio import AudioReactiveEffect

_LOGGER = logging.getLogger(__name__)


def stretch_2d_full(
    source_pixels, target_rows, target_columns, source_rows, source_columns
):
    if target_rows == source_rows and target_columns == source_columns:
        return source_pixels

    # Reshape the 1D array into a 2D array (rows, columns, 3)
    source_pixels = source_pixels.reshape((source_rows, source_columns, 3))

    # Create target grid for the new pixel positions
    row_scale = np.linspace(0, source_rows - 1, target_rows)
    col_scale = np.linspace(0, source_columns - 1, target_columns)

    # Get the floor and ceiling indices for the scaled positions
    row_floor = np.floor(row_scale).astype(int)
    row_ceil = np.minimum(np.ceil(row_scale).astype(int), source_rows - 1)
    col_floor = np.floor(col_scale).astype(int)
    col_ceil = np.minimum(np.ceil(col_scale).astype(int), source_columns - 1)

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
    return interpolated.reshape((target_rows * target_columns, 3))


def stretch_2d_repeat(
    source_pixels, target_rows, target_columns, source_rows, source_columns
):
    _LOGGER.warning("Stretch 1d repeat not implemented")


def stretch_1d_vertical(
    source_pixels, target_rows, target_columns, source_rows, source_columns
):
    _LOGGER.warning("Stretch 1d vertical not implemented")


def stretch_1d_horizontal(
    source_pixels, target_rows, target_columns, source_rows, source_columns
):
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
    CATEGORY = "Matrix"
    HIDDEN_KEYS = ["background_color", "background_brightness", "blur"]
    ADVANCED_KEYS = ["diag", "bias_black"]

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
            vol.Optional(
                "diag",
                description="diagnostic enable",
                default=False,
            ): bool,
            vol.Optional(
                "advanced",
                description="enable advanced options",
                default=False,
            ): bool,
        }
    )

    # things you want to do on activation, when pixel count is known
    def on_activate(self, pixel_count):
        self.rows = self._virtual.config["rows"]
        self.columns = int(self.pixel_count / self.rows)
        self.lasttime = 0
        self.frame = 0
        self.fps = 0
        self.last = 0
        self.r_total = 0.0
        self.passed = 0
        self.current_time = timeit.default_timer()

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
        self.diag = self._config["diag"]

    def log_sec(self):
        result = False
        if self.diag:
            nowint = int(self.current_time)
            # if now just rolled over a second boundary
            if nowint != self.lasttime:
                self.fps = self.frame
                self.frame = 0
                result = True
            else:
                self.frame += 1
            self.lasttime = nowint
        self.log = result

    def try_log(self):
        end = timeit.default_timer()
        r_time = end - self.current_time
        self.r_total += r_time
        if self.log is True:
            if self.fps > 0:
                r_avg = self.r_total / self.fps
            else:
                r_avg = 0.0
            _LOGGER.warning(
                f"FPS {self.fps} Render:{r_avg:0.6f} Cycle: {(end - self.last):0.6f} Sleep: {(self.current_time - self.last):0.6f}"
            )
            self.r_total = 0.0
        self.last = end
        return self.log

    def audio_data_updated(self, data):
        pass

    def render(self):

        was = self.current_time
        self.current_time = timeit.default_timer()
        self.passed = self.current_time - was
        self.log_sec()

        # all virtual grabs are try as they might not exist yet, but may on the next frame

        try:
            mask_pixels = self._ledfx.virtuals._virtuals.get(
                self.mask
            ).assembled_frame
            mask_rows = self._ledfx.virtuals._virtuals.get(self.mask).config[
                "rows"
            ]
            mask_columns = int(
                self._ledfx.virtuals._virtuals.get(self.mask).pixel_count
                / mask_rows
            )
        except Exception:
            mask_pixels = np.zeros(np.shape(self.pixels))
            mask_rows = self.rows
            mask_columns = self.columns

        try:
            foreground_pixels = self._ledfx.virtuals._virtuals.get(
                self.foreground
            ).assembled_frame
            foreground_rows = self._ledfx.virtuals._virtuals.get(
                self.foreground
            ).config["rows"]
            foreground_columns = int(
                self._ledfx.virtuals._virtuals.get(self.foreground).pixel_count
                / foreground_rows
            )
        except Exception:
            foreground_pixels = np.zeros(np.shape(self.pixels))
            foreground_rows = self.rows
            foreground_columns = self.columns

        try:
            background_pixels = self._ledfx.virtuals._virtuals.get(
                self.background
            ).assembled_frame
            background_rows = self._ledfx.virtuals._virtuals.get(
                self.background
            ).config["rows"]
            background_columns = int(
                self._ledfx.virtuals._virtuals.get(self.background).pixel_count
                / background_rows
            )
        except Exception:
            background_pixels = np.zeros(np.shape(self.pixels))
            background_rows = self.rows
            background_columns = self.columns

        mask_pixels = self.mask_stretch_func(
            mask_pixels, self.rows, self.columns, mask_rows, mask_columns
        )
        foreground_pixels = self.foreground_stretch_func(
            foreground_pixels,
            self.rows,
            self.columns,
            foreground_rows,
            foreground_columns,
        )
        background_pixels = self.background_stretch_func(
            background_pixels,
            self.rows,
            self.columns,
            background_rows,
            background_columns,
        )

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
