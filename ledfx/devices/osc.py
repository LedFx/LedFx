import logging
from typing import Literal

import numpy as np
from pydantic import Field
from pythonosc.parsing.osc_types import write_string
from pythonosc.udp_client import SimpleUDPClient

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class OSCServerDevice(NetworkedDevice):
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

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "OSC"
        self._client: SimpleUDPClient | None = None
        self._osc_header_key: tuple[int, str, int, str] | None = None
        self._osc_headers: tuple[bytes, ...] = ()
        self.last_frame = np.full((self.config.pixel_count, 3), -1)

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "pixel_count",
        "send_type",
        "starting_addr",
        "path",
    )

    def config_updated(self, config):
        if not self._output_changed():
            return
        self.last_frame = np.full((self.config.pixel_count, 3), -1)
        self.deactivate()
        self.activate()
        self._built_settings = self._output_settings()

    def activate(self):
        self._client = SimpleUDPClient(self.destination, self.config.port)
        _LOGGER.debug(
            "%s sender for %s started.",
            self._device_type,
            self.config.name,
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.debug(
            "%s sender for %s stopped.",
            self._device_type,
            self.config.name,
        )
        if getattr(self, "_client", None) is not None:
            self._client._sock.close()
            self._client = None

    def flush(self, data):
        if np.array_equal(data, self.last_frame):
            return

        if data.size != self.config.pixel_count * 3:
            raise Exception(  # noqa: TRY002
                f"Invalid buffer size. {data.size} != {self.config.pixel_count * 3}"
            )

        # Paths and type tags depend only on output configuration. Keep the
        # exact OSC array tags used by python-osc, including All_To_One's
        # separate RGB arrays, rather than changing receivers' argument shape.
        key = (
            self.config.pixel_count,
            self.config.send_type,
            self.config.starting_addr,
            self.config.path,
        )
        count, mode, start, path = key
        if key != self._osc_header_key:
            if mode == "Three_Addresses":
                addresses, tags = count * 3, ",f"
            elif mode == "All_To_One":
                addresses, tags = 1, "," + "[fff]" * count
            else:
                addresses = count
                tags = ",[fff]" if mode == "One_Argument" else ",fff"
            type_tags = write_string(tags)
            self._osc_headers = tuple(
                write_string(path.format(address=start + i)) + type_tags
                for i in range(addresses)
            )
            self._osc_header_key = key

        # Preserve integer truncation before normalization and OSC's float32
        # rounding, but perform conversion for the whole frame in NumPy.
        payload = (data.astype(int) / 255).astype(">f4").tobytes()
        stride = len(payload) // len(self._osc_headers)
        for index, header in enumerate(self._osc_headers):
            packet = header + payload[index * stride : (index + 1) * stride]
            client = self._client
            if client is None:
                self.activate()
                continue
            try:
                # UDPClient.send simply sends content.dgram through this socket.
                # Avoid constructing/parsing an OscMessage for already encoded
                # bytes; retain its resolved destination and socket lifecycle.
                client._sock.sendto(packet, (client._address, client._port))
            except AttributeError:
                self.activate()
                continue

        self.last_frame = np.copy(data)
