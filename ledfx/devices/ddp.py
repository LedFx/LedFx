import logging
import socket
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import async_fire_and_return, resolve_destination

_LOGGER = logging.getLogger(__name__)


class DDPDevice(Device):
    """DDP device support"""

    # Timeout in seconds for ddp communication
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
    DATATYPE = 0x00
    SOURCE = 0x01
    TIMEOUT = 1

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Optional(
                "refresh_rate",
                description="Maximum rate that pixels are sent to the device",
                default=60,
            ): int,
            vol.Optional(
                "icon_name",
                description="https://material-ui.com/components/material-icons/",
                default="wled",
            ): str,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        DDPDevice.resolved_dest = None
        self.attempt_resolve_dest()

    def attempt_resolve_dest(self):
        _LOGGER.info(
            f"Attempting to resolve device {self.name} address {self._config['ip_address']} ..."
        )
        async_fire_and_return(
            resolve_destination(self._config["ip_address"]),
            self.on_resolved_dest,
            0.5,
        )

    def on_resolved_dest(self, dest):
        self.resolved_dest = dest

    # async def get_config(self):
    #     # Get all necessary info from the wled device and update configuration
    #     try:
    #         wled_config = await WLED.get_config(self.resolved_dest)
    #     except ValueError as msg:
    #         _LOGGER.warning(msg)
    #         return

    def activate(self):
        if not self.resolved_dest:
            _LOGGER.error(
                f"Cannot activate device {self.name} - destination address {self._config['ip_address']} is not resolved"
            )
            self.attempt_resolve_dest()
            return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        super().activate()

    def deactivate(self):
        super().deactivate()
        self._sock = None

    @property
    def pixel_count(self):
        return int(self._config["pixel_count"])

    def flush(self, data):
        DDPDevice.send_out(self._sock, self.resolved_dest, data)

    @staticmethod
    def send_out(self, sock, dest, data):
        byteData = data.astype(np.uint8).flatten().tobytes()
        packets, remainder = divmod(len(byteData), DDPDevice.MAX_DATALEN)

        for i in range(packets):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock,
                dest,
                i,
                DDPDevice.MAX_DATALEN,
                byteData[data_start:data_end],
            )

        data_start = packets * DDPDevice.MAX_DATALEN
        data_end = data_start + remainder
        DDPDevice.send_packet(
            sock,
            dest,
            packets,
            remainder,
            byteData[data_start:data_end],
            push=True,
        )

    @staticmethod
    def send_packet(
        self, sock, dest, packet_count, data_len, data, push=False
    ):
        udpData = bytearray()
        header = struct.pack(
            "BBBBLH",
            DDPDevice.VER1 | DDPDevice.PUSH if push else DDPDevice.VER1,
            0,
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
