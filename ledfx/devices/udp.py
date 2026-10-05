import logging
import time
from typing import Annotated

import numpy as np
from ledfx_senders import UDPRealtimeSender
from numpy.typing import NDArray
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import X_REQUIRED, OneOf
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice
from ledfx.devices.native_packet import NativePacketDevice

_LOGGER = logging.getLogger(__name__)

RGB_HYPERHDR_PACKET = "RGB (HyperHDR)"
SUPPORTED_PACKETS = [
    "DRGB",
    "WARLS",
    "DRGBW",
    "DNRGB",
    "adaptive_smallest",
    RGB_HYPERHDR_PACKET,
]


class UDPRealtimeDevice(NativePacketDevice):
    """Generic UDP Realtime device support"""

    class Config(NetworkedDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        port: int = Field(
            21324,
            description="Port for the UDP device",
            ge=1,
            le=65535,
            json_schema_extra={X_REQUIRED: True},
        )
        udp_packet_type: Annotated[str, OneOf(list(SUPPORTED_PACKETS))] = Field(
            "DRGB",
            description="RGB packet encoding",
            json_schema_extra={X_REQUIRED: True},
        )
        timeout: int = Field(
            1,
            description="Seconds to wait after the last received packet to yield device control",
            ge=1,
            le=255,
        )
        minimise_traffic: bool = Field(
            True,
            description="Won't send updates if nothing has changed on the LED device",
        )

    config = TypedConfig(Config)

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "pixel_count",
        "udp_packet_type",
        "timeout",
        "minimise_traffic",
        "refresh_rate",
    )

    @override
    def _validate_configuration(self) -> None:
        if not 1 <= self.config.pixel_count <= 65536:
            raise ValueError("Realtime pixel count exceeds 16-bit pixel index range")

    def _keepalive_interval(self) -> float:
        return (
            (self.config.timeout * self.config.refresh_rate - 1) // 2
        ) / self.config.refresh_rate

    @override
    def _make_sender(self, destination: str) -> UDPRealtimeSender:
        return UDPRealtimeSender(
            destination=destination,
            port=self.config.port,
            pixel_count=self.config.pixel_count,
            packet_type=self.config.udp_packet_type,
            timeout=self.config.timeout,
            minimise_traffic=self.config.minimise_traffic,
            keepalive_interval=self._keepalive_interval(),
        )

    @override
    def flush(self, data: NDArray[np.generic]) -> None:
        with self.device_lock:
            if isinstance(self._sender, UDPRealtimeSender):
                self._sender.send(data, now=time.monotonic())
