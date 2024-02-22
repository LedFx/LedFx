import logging
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import UDPDevice
from ledfx.events import DevicesUpdatedEvent

_LOGGER = logging.getLogger(__name__)


class DDPDevice(UDPDevice):
    """DDP device support"""

    # PORT = 4048
    HEADER_LEN = 0x0A
    # DDP_ID_VIRTUAL     = 1
    # DDP_ID_CONFIG      = 250
    # DDP_ID_STATUS      = 251

    MAX_PIXELS = 480
    MAX_DATALEN = MAX_PIXELS * 3  # fits nicely in an ethernet packet

    VER = 0xC0  # version mask
    VER1 = 0x40  # version=1
    PUSH = 0x01
    QUERY = 0x02
    REPLY = 0x04
    STORAGE = 0x08
    TIME = 0x10
    DATATYPE = 0x01
    SOURCE = 0x01
    TIMEOUT = 1

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                "port",
                description="Port for the UDP device",
                default=4048,
            ): vol.All(int, vol.Range(min=1, max=65535)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "DDP"
        self.frame_count = 0
        self.connection_warning = False

    def flush(self, data):
        self.frame_count += 1
        try:

            DDPDevice.send_out(
                self._sock,
                self.destination,
                self._config["port"],
                data,
                self.frame_count,
            )
            if self.connection_warning:
                # If we have reconnected, log it, come back online, and fire an event to the frontend
                _LOGGER.info(f"DDP connection reestablished to {self.name}")
                self.connection_warning = False
                self._online = True
                self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))
        except AttributeError:
            self.activate()
        except OSError as e:
            # print warning only once until it clears

            if not self.connection_warning:
                # If we have lost connection, log it, go offline, and fire an event to the frontend
                _LOGGER.warning(f"Error in DDP connection to {self.name}: {e}")
                self.connection_warning = True
                self._online = False
                self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))

    @staticmethod
    def send_out(sock, dest, port, data, frame_count):
        sequence = frame_count % 15 + 1
        byteData = data.astype(np.uint8).flatten().tobytes()
        packets, remainder = divmod(len(byteData), DDPDevice.MAX_DATALEN)
        if remainder == 0:
            packets -= 1  # divmod returns 1 when len(byteData) fits evenly in DDPDevice.MAX_DATALEN

        for i in range(packets + 1):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock, dest, port, sequence, i, byteData[data_start:data_end]
            )

    @staticmethod
    def send_packet(sock, dest, port, sequence, packet_count, data):
        bytes_length = len(data)
        udpData = bytearray()
        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1
            | (
                DDPDevice.VER1
                if (bytes_length == DDPDevice.MAX_DATALEN)
                else DDPDevice.PUSH
            ),
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            bytes_length,
        )

        udpData.extend(header)
        udpData.extend(data)

        sock.sendto(
            bytes(udpData),
            (dest, port),
        )
