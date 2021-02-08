import logging
import socket
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import async_fire_and_return, resolve_destination

_LOGGER = logging.getLogger(__name__)


class DDP:
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


class WLEDDevice(Device):
    """WLED device support"""

    # Timeout in seconds for wled communication
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

        self.resolved_dest = None
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

    def update_config(self, wled_config):

        _LOGGER.info(f"Received WLED config from {self.resolved_dest}")

        led_info = wled_config["leds"]
        wled_name = wled_config["name"]

        wled_count = led_info["count"]
        wled_rgbmode = led_info["rgbw"]

        wled_config = {
            "name": wled_name,
            "pixel_count": wled_count,
            "rgbw_led": wled_rgbmode,
        }

        # that's a nice operation u got there python
        self._config |= wled_config

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
        byteData = data.astype(np.dtype("B")).flatten().tobytes()
        packets, remainder = divmod(len(byteData), DDP.MAX_DATALEN)

        for i in range(packets):
            data_start = i * DDP.MAX_DATALEN
            data_end = data_start + DDP.MAX_DATALEN
            self.send_ddp(i, DDP.MAX_DATALEN, byteData[data_start:data_end])

        data_start = packets * DDP.MAX_DATALEN
        data_end = data_start + remainder
        self.send_ddp(
            packets, remainder * 3, byteData[data_start:data_end], push=True
        )

    def send_ddp(self, sequence, data_len, data, push=False):
        udpData = bytearray()
        header = struct.pack(
            "BBBBLH",
            DDP.VER1 | DDP.PUSH if push else DDP.VER1,
            sequence,
            DDP.DATATYPE,
            DDP.SOURCE,
            sequence * DDP.MAX_DATALEN,
            data_len,
        )
        udpData.extend(header)
        udpData.extend(data)

        self._sock.sendto(
            bytes(udpData),
            (self.resolved_dest, DDP.PORT),
        )
