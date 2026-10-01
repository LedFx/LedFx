import logging
from enum import Enum
from typing import Annotated, ClassVar

from PIL import Image
from pydantic import Field

from ledfx.configuration.fields import OneOf
from ledfx.configuration.plugin import TypedConfig
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

    RESIZE_METHOD_MAPPING: ClassVar[dict[str, int]] = {
        GIFResizeMethods.NEAREST.value: Image.NEAREST,
        GIFResizeMethods.BILINEAR.value: Image.BILINEAR,
        GIFResizeMethods.BICUBIC.value: Image.BICUBIC,
        GIFResizeMethods.LANCZOS.value: Image.LANCZOS,
    }

    class Config(Effect.Config):
        resize_method: Annotated[
            str, OneOf([resize_method.value for resize_method in GIFResizeMethods])
        ] = Field(
            GIFResizeMethods.BICUBIC.value,
            description="What strategy to use when resizing GIF",
        )

    config = TypedConfig(Config)

    def config_updated(self, config):
        self.resize_method = self.RESIZE_METHOD_MAPPING[self.config.resize_method]
