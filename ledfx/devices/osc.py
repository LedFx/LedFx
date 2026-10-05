import logging
import time
from typing import Literal

import numpy as np
from ledfx_senders import OSCSender
from numpy.typing import NDArray
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice
from ledfx.devices.native_packet import NativePacketDevice

_LOGGER = logging.getLogger(__name__)


class OSCServerDevice(NativePacketDevice):
    """OSC Server 'device' support"""

    class Config(NetworkedDevice.Config):
        port: int = Field(
            9000,
            description="Port of the OSC server",
            ge=1,
            le=65535,
            json_schema_extra={X_REQUIRED: True},
        )
        pixel_count: int = Field(
            1,
            description="The amount of channels OR if address_type == Three_addresses then this is the amount of RGB subsequent addresses (set to 3 if your addresses are defined like R,G,B,R,G,B)",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        send_type: Literal[
            "One_Argument", "Three_Arguments", "Three_Addresses", "All_To_One"
        ] = Field(
            "One_Argument",
            description="One_Argument -> <addr> [R, G, B]; Three_Arguments -> <addr> R G B; Three_Addresses -> <addr> R, <addr+1> G, <addr+2> B; All_To_One -> <addr> [[R, G, B], [R, G, B], [R, G, B]]",
            json_schema_extra={X_REQUIRED: True},
        )
        starting_addr: int = Field(
            0,
            description="Starting address/id of the OSC device",
            ge=0,
            json_schema_extra={X_REQUIRED: True},
        )
        path: str = Field(
            "/0/dmx/{address}",
            description="The OSC Path to send to - Placeholders: {address} -> this will start at the starting_addr and count up",
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "pixel_count",
        "send_type",
        "starting_addr",
        "path",
    )

    @override
    def _validate_configuration(self) -> None:
        # The native constructor validates formatted path lengths and framing.
        probe = OSCSender._test_sender(
            destination="127.0.0.1",
            port=self.config.port,
            pixel_count=self.config.pixel_count,
            path=self.config.path,
            starting_addr=self.config.starting_addr,
            send_type=self.config.send_type,
            mode="discard",
        )
        probe.close()

    @override
    def _make_sender(self, destination: str) -> OSCSender:
        return OSCSender(
            destination=destination,
            port=self.config.port,
            pixel_count=self.config.pixel_count,
            path=self.config.path,
            starting_addr=self.config.starting_addr,
            send_type=self.config.send_type,
        )

    @override
    def flush(self, data: NDArray[np.generic]) -> None:
        with self.device_lock:
            if isinstance(self._sender, OSCSender):
                self._sender.send(data, now=time.monotonic())
