import logging

import numpy as np
from ledfx_senders import DDPSender
from numpy.typing import NDArray
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import UDPDevice
from ledfx.devices.native_packet import NativePacketDevice
from ledfx.events import DevicesUpdatedEvent

_LOGGER = logging.getLogger(__name__)


class DDPDevice(NativePacketDevice):
    """DDP device support"""

    class Config(UDPDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        port: int = Field(
            4048,
            description="Port for the UDP device",
            ge=1,
            le=65535,
            json_schema_extra={X_REQUIRED: True},
        )
        destination_id: int = Field(
            1,
            description="DDP destination ID (1=default, 2-249=custom, 250=config, 251=status, 254=DMX, 255=all)",
            ge=1,
            le=255,
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "DDP"
        self.frame_count = 0
        self.connection_warning = False

    OUTPUT_KEYS = ("ip_address", "pixel_count", "port", "destination_id")

    def _validate_configuration(self) -> None:
        if not 1 <= self.config.pixel_count * 3 <= 2**32 - 1:
            raise ValueError("DDP channel count exceeds offset range")

    def _make_sender(self, destination: str) -> DDPSender:
        return DDPSender(
            self.config.pixel_count * 3,
            destination=destination,
            port=self.config.port,
            destination_id=self.config.destination_id,
        )

    def flush(self, data: NDArray[np.generic]) -> None:
        event = False
        with self.device_lock:
            if not isinstance(self._sender, DDPSender):
                return
            try:
                self._sender.send(data)
                self.frame_count += 1
                if self.connection_warning:
                    _LOGGER.info("DDP connection to %s re-established.", self.name)
                    self.connection_warning = False
                    self._online = True
                    event = True
            except OSError as error:
                # A valid attempted frame advances the native wire sequence too.
                self.frame_count += 1
                if not self.connection_warning:
                    _LOGGER.warning(
                        "Error in DDP connection to %s: %s", self.name, error
                    )
                    self.connection_warning = True
                    self._online = False
                    event = True
        if event:
            self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))
