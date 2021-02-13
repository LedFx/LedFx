import logging
import socket
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class DDPDevice(NetworkedDevice):
    """DDP device support"""

    PORT = 4048
    HEADER_LEN = 0x0A
    # DDP_ID_DISPLAY     = 1
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
                "name", description="Friendly name for the device"
            ): str,
        }
    )

    def __init__(self, ledfx, config):
        self.frame_count = 0
        super().__init__(ledfx, config)

    def activate(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        super().activate()

    def deactivate(self):
        super().deactivate()
        self._sock = None

    def flush(self, data):
        self.frame_count += 1
        DDPDevice.send_out(
            self._sock, self.destination, data, self.frame_count
        )

    @staticmethod
    def send_out(sock, dest, data, frame_count):
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
            sequence,
            packets,
            remainder,
            byteData[data_start:data_end],
            push=True,
        )

    @staticmethod
    def send_packet(
        sock, dest, sequence, packet_count, data_len, data, push=False
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
            (dest, DDPDevice.PORT),
        )
