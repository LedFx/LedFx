import logging

import numpy as np
import voluptuous as vol
from PIL import Image, ImageOps

from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.utils.logsec import LogSec

_LOGGER = logging.getLogger(__name__)

# 1d horizontal stetch


class BlendVirtual:
    def __init__(self, virtual_id, _virtuals, fallback_shape):
        self.target_rows = fallback_shape[0]
        self.target_columns = fallback_shape[1]
        # all virtual grabs are try as they might not exist yet, but may on the next frame
        try:
            virtual = _virtuals.get(virtual_id)
            self.rows = virtual.config["rows"]
            self.columns = int(virtual.pixel_count / self.rows)
            self.matching = (
                self.rows == fallback_shape[0]
                and self.columns == fallback_shape[1]
            )
            if hasattr(virtual.active_effect, "matrix"):
                self.matrix = virtual.active_effect.get_matrix()
            else:
                # Reshape the 1D pixel array into (height, width, 3) for RGB
                reshaped_pixels = virtual.assembled_frame.reshape(
                    (self.rows, self.columns, 3)
                )
                # Convert the numpy array back into a Pillow image
                self.matrix = Image.fromarray(
                    reshaped_pixels.astype(np.uint8), "RGB"
                )
        except Exception as e:
            _LOGGER.info(f"Virtual {virtual_id} {e}")
            self.matrix = Image.new("RGB", fallback_shape, (0, 0, 0))
            self.rows = fallback_shape[0]
            self.columns = fallback_shape[1]
            self.matching = True


def stretch_2d_full(blend_virtual):
    if blend_virtual.matching:
        return blend_virtual.matrix

    # use pillow to strect blend_virtual.matrix to blend_virtual.target_rows, blend_virtual.target_columns
    resized = blend_virtual.matrix.resize(
        (blend_virtual.target_columns, blend_virtual.target_rows)
    )
    return resized


def stretch_2d_tile(blend_virtual):
    if blend_virtual.matching:
        return blend_virtual.matrix

    # Get the source image dimensions
    src_width, src_height = blend_virtual.matrix.size

    # Create a new image with the target dimensions
    target_image = Image.new(
        "RGB", (blend_virtual.target_columns, blend_virtual.target_rows)
    )

    # Tile the source image to fill the new image
    for i in range(0, blend_virtual.target_columns, src_width):
        for j in range(0, blend_virtual.target_rows, src_height):
            # Paste the source image at the current position
            target_image.paste(blend_virtual.matrix, (i, j))

    return target_image


def stretch_1d_vertical(blend_virtual):
    _LOGGER.warning("Stretch 1d vertical not implemented")


def stretch_1d_horizontal(blend_virtual):
    _LOGGER.warning("Stretch 1d horizontal not implemented")


STRETCH_FUNCS_MAPPING = {
    "2d full": stretch_2d_full,
    "2d tile": stretch_2d_tile,
    # "1d vertical": stretch_1d_vertical, TODO Implement
    # "1d horizontal": stretch_1d_horizontal, TODO: Implement
}


class Blender(AudioReactiveEffect, LogSec):
    NAME = "Blender"
    CATEGORY = "Matrix"
    HIDDEN_KEYS = ["background_color", "background_brightness", "blur"]
    ADVANCED_KEYS = LogSec.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "mask_stretch",
                description="How to stretch the mask source pixles to the effect pixels",
                default="2d full",
            ): vol.In(list(STRETCH_FUNCS_MAPPING.keys())),
            vol.Optional(
                "background_stretch",
                description="How to stretch the background source pixles to the effect pixels",
                default="2d full",
            ): vol.In(list(STRETCH_FUNCS_MAPPING.keys())),
            vol.Optional(
                "foreground_stretch",
                description="How to stretch the foreground source pixles to the effect pixels",
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
                "mask_cutoff",
                description="1 default = luminance as alpha, anything below 1 is mask cutoff",
                default=1.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
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
        self.mask_cutoff = self._config["mask_cutoff"]

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
        )
        blend_fore = BlendVirtual(
            self.foreground,
            self._ledfx.virtuals._virtuals,
            (self.rows, self.columns),
        )
        blend_back = BlendVirtual(
            self.background,
            self._ledfx.virtuals._virtuals,
            (self.rows, self.columns),
        )

        mask_image = self.mask_stretch_func(blend_mask).convert("L")
        fore_image = self.foreground_stretch_func(blend_fore)
        back_image = self.background_stretch_func(blend_back)

        if self.mask_cutoff < 1.0:
            cutoff = int(255 * (1 - self.mask_cutoff))
            mask_image = mask_image.point(lambda p: 255 if p > cutoff else 0)

        if self.invert_mask:
            mask_image = ImageOps.invert(mask_image)

        blend_image = Image.composite(fore_image, back_image, mask_image)

        rgb_array = np.frombuffer(blend_image.tobytes(), dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)

        copy_length = min(self.pixels.shape[0], rgb_array.shape[0])
        self.pixels[:copy_length, :] = rgb_array[:copy_length, :]

        self.try_log()
