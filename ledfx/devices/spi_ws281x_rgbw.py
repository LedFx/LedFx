import itertools
from enum import Enum

import numpy as np
import voluptuous as vol

from ledfx.devices.spi_ws281x import SPI_WS281X


class WhiteMode(Enum):
    Replace = "Replace"
    Add = "Add"


class SPI_WS281X_RBGW(SPI_WS281X):
    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "white_mode",
                    description="Whether the white channel should replace the RGB channels' white or should be added to it. "
                    "After the white value is extracted from the RGB values, in 'Replace' mode "
                    "the RGB channels' values are reduced by the white amount. In 'Add' mode the RGB values stay the same and "
                    "the the RGB channels will display the white on top of the White LED. "
                    "If you select 'Add', please make sure your setup is designed to handle the power consumption and heat dissipation of"
                    "all four RGBW channels at maximum brightness.",
                    default="Replace",
                ): vol.In(list(e.value for e in WhiteMode)),
                vol.Required(
                    "color_order", description="Color order", default="RGBW"
                ): vol.In(
                    "".join(p) for p in list(itertools.permutations("RGBW"))
                ),
            }
        )

    def get_ordered_pixel_data(self, data):
        rgb = data

        # Calculate the white value as the minimum of the RGB values, and return it as a [N, 1] array (i.e. a column vector)
        w = np.min(rgb, axis=1)[:, np.newaxis]
        if self._config["white_mode"] == WhiteMode.Replace.value:
            rgb = rgb - w  # Subtract the white value from the RGB values

        # Stack the RGB and W values together, and reorder them according to the color order
        return np.concatenate((rgb, w), axis=1)[:, self.get_rgbw_indices()]

    def get_rgbw_indices(self):
        color_order = self._config["color_order"]
        return ["RGBW".index(c) for c in color_order]
