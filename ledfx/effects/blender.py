import logging

import numpy as np
import voluptuous as vol

from PIL import Image, ImageOps
from ledfx.effects.audio import AudioReactiveEffect
from ledfx.effects.utils.logsec import LogSec

_LOGGER = logging.getLogger(__name__)

# TODO:look at better alpha blend options on the mask
# TODO: slider for mask
# 1d horizontal stetch

class BlendVirtual:
    def __init__(self, virtual_id, _virtuals, fallback_shape, pixels_shape):
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
                reshaped_pixels = virtual.assembled_frame.reshape((1, virtual.pixel_count, 3))
                # Convert the numpy array back into a Pillow image
                self.matrix = Image.fromarray(reshaped_pixels.astype(np.uint8), 'RGB')
        except Exception as e:
            _LOGGER.warning(f"Virtual {virtual_id} {e}")
            self.matrix = Image.new('RGB', fallback_shape, (0, 0, 0))
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
    target_image = Image.new('RGB', (blend_virtual.target_columns, blend_virtual.target_rows))

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

        mask_image = self.mask_stretch_func(blend_mask).convert('L')
        fore_image = self.foreground_stretch_func(blend_fore)
        back_image = self.background_stretch_func(blend_back)

        # TODO: replace with a slider now we have pillow in the mix
        # if self.bias_black:
        #     # Create a boolean mask where white pixels ([255.0, 255.0, 255.0]) are True, and black pixels are False
        #     mask = (mask_pixels == 255.0).all(axis=-1)
        # else:
        #     # Create a boolean mask where any pixel that is not black ([0, 0, 0]) is True, and black pixels are False
        #     mask = (mask_pixels != 0).any(axis=-1)

        if self.invert_mask:
            mask_image = ImageOps.invert(mask_image)

        blend_image = Image.composite(fore_image, back_image, mask_image)

        rgb_array = np.frombuffer(blend_image.tobytes(), dtype=np.uint8)
        rgb_array = rgb_array.astype(np.float32)
        rgb_array = rgb_array.reshape(int(rgb_array.shape[0] / 3), 3)

        copy_length = min(self.pixels.shape[0], rgb_array.shape[0])
        self.pixels[:copy_length, :] = rgb_array[:copy_length, :]

        self.try_log()
