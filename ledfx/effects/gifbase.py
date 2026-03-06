import logging
from enum import Enum

import voluptuous as vol
from PIL import Image

from ledfx.effects import Effect

_LOGGER = logging.getLogger(__name__)


class GIFResizeMethods(Enum):
    # https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters-comparison-table
    NEAREST = "Fastest"
    BILINEAR = "Fast"
    BICUBIC = "Slow"
    LANCZOS = "Slowest"


@Effect.no_registration
class GifBase(Effect):
    """
    Simple Gif base class that supplies basic gif and resize capability.
    """

    RESIZE_METHOD_MAPPING = {
        GIFResizeMethods.NEAREST.value: Image.NEAREST,
        GIFResizeMethods.BILINEAR.value: Image.BILINEAR,
        GIFResizeMethods.BICUBIC.value: Image.BICUBIC,
        GIFResizeMethods.LANCZOS.value: Image.LANCZOS,
    }

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "resize_method",
                description="What strategy to use when resizing GIF",
                default=GIFResizeMethods.BICUBIC.value,
            ): vol.In(
                [resize_method.value for resize_method in GIFResizeMethods]
            ),
        }
    )

    def config_updated(self, config):
        self.resize_method = self.RESIZE_METHOD_MAPPING[
            self._config["resize_method"]
        ]
