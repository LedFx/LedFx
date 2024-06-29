import logging

import voluptuous as vol
from numpy import ndarray

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)


class DummyDevice(Device):
    """Dummy device for brower render only"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Dummy"

    def flush(self, data: ndarray) -> None:
        """
        Throw pixels into the abyss

        Args:
            data (ndarray): The LED data to be flushed.

        Raises:
            AttributeError: If an attribute error occurs during the flush.
            OSError: If an OS error occurs during the flush.
        """
        pass
