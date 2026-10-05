import logging

import numpy as np
from ledfx_senders import OPCSender
from numpy.typing import NDArray
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice
from ledfx.devices.native_packet import NativePacketDevice

_LOGGER = logging.getLogger(__name__)


class OpenPixelControl(NativePacketDevice):
    """OpenPixelControl device support"""

    class Config(NetworkedDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        channel: int = Field(
            0,
            description="Channel to send pixel data",
            ge=0,
            le=255,
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    OUTPUT_KEYS = ("ip_address", "pixel_count", "channel")

    def _validate_configuration(self) -> None:
        if not 1 <= self.config.pixel_count <= 21834:
            raise ValueError("OPC frame exceeds UDP payload ceiling")

    def _make_sender(self, destination: str) -> OPCSender:
        return OPCSender(
            self.config.pixel_count,
            destination=destination,
            channel=self.config.channel,
        )

    def flush(self, data: NDArray[np.generic]) -> None:
        with self.device_lock:
            if isinstance(self._sender, OPCSender):
                self._sender.send(data)
