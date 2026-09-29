import logging
from typing import Annotated

import serial
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import SerialDevice, packets
from ledfx.events import DevicesUpdatedEvent

_LOGGER = logging.getLogger(__name__)

COLOR_ORDERS = [
    "RGB",
    "RBG",
    "GRB",
    "BRG",
    "GBR",
    "BGR",
]


class AdalightDevice(SerialDevice):
    """Adalight device support"""

    class Config(SerialDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        color_order: Annotated[str, OneOf(list(COLOR_ORDERS))] = Field(
            "RGB", description="Color order", json_schema_extra={X_REQUIRED: True}
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Adalight"
        self.color_order = self.config.color_order

    def flush(self, data):
        try:
            self.serial.write(packets.build_adalight_packet(data, self.color_order))

        except serial.SerialException:
            # If we have lost connection, log it, go offline, and fire an event to the frontend
            _LOGGER.warning(
                "Serial Connection Interrupted. Please check connections and ensure your device is functioning correctly."
            )
            self.deactivate()
            self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))
