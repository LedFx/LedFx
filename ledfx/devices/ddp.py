import logging
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import UDPDevice

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
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                "port",
                description="Port for the UDP device",
                default=4048,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "DDP"
        self.frame_count = 0

    def flush(self, data):
        self.frame_count += 1
        try:
            DDPDevice.send_out(
                self._sock, self.destination, self._config["port"], data, self.frame_count
            )
        except AttributeError:
            self.activate()

    @staticmethod
    def send_out(sock, dest, port, data, frame_count):
        sequence = frame_count % 15 + 1
        byteData = data.astype(np.uint8).flatten().tobytes()
        packets, remainder = divmod(len(byteData), DDPDevice.MAX_DATALEN)

        for i in range(packets):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock,
                dest,
                sequence,
                i,
                DDPDevice.MAX_DATALEN,
                byteData[data_start:data_end],
            )

        data_start = packets * DDPDevice.MAX_DATALEN
        data_end = data_start + remainder
        DDPDevice.send_packet(
            sock,
            dest,
            port,
            sequence,
            packets,
            remainder,
            byteData[data_start:data_end],
            push=True,
        )

    @staticmethod
    def send_packet(
        sock, dest, port, sequence, packet_count, data_len, data, push=False
    ):
        udpData = bytearray()
        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1 | DDPDevice.PUSH if push else DDPDevice.VER1,
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            data_len,
        )

        udpData.extend(header)
        udpData.extend(data)

        sock.sendto(
            bytes(udpData),
            (dest, port),
        )
