import logging
import socket
import struct

import numpy as np
import requests
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import resolve_destination

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
        }
    )

    def identify(self, ip_address):
        """
            Uses a JSON API call to determine if the device is WLED or WLED compatible
            Specifically searches for "WLED" in the brand json - currently all major
            branches/forks of WLED contain WLED in the branch data.

        Returns:
            config: dict, with all wled configuration info
            or None for any error
        """
        try:
            response = requests.get(
                f"http://{ip_address}/json/info", timeout=self.TIMEOUT
            )
        except requests.exceptions.RequestException:
            msg = f"WLED Identifier can't connect to {ip_address}. Likely not a WLED device."
            raise ValueError(msg)

        if not response.ok:
            msg = f"WLED API Error on {ip_address}: {response.status_code}"
            raise ValueError(msg)

        wled_config = response.json()

        if not wled_config["brand"] in "WLED":
            msg = f"{ip_address} is not WLED compatible, brand: {wled_config['brand']}"
            raise ValueError(msg)

        return wled_config

    def __init__(self, ledfx, config):
        # TASK: using just the ip address, get all necessary info from the wled device, fill config, and pass this on to super()
        # check if ip/hostname resolves okay

        self.resolved_dest = resolve_destination(config["ip_address"])
        if not self.resolved_dest:
            _LOGGER.warning(
                f"Cannot resolve destination {config['ip_address']} - Make sure the IP/hostname is correct and device is online."
            )
            return

        try:
            wled_config = self.identify(self.resolved_dest)
        except ValueError as msg:
            _LOGGER.warning(msg)
            return

        led_info = wled_config["leds"]
        wled_name = wled_config["name"]

        wled_count = led_info["count"]
        wled_rgbmode = led_info["rgbw"]

        wled_config = {
            "name": wled_name,
            "pixel_count": wled_count,
            "icon_name": "wled",
            "rgbw_led": wled_rgbmode,
        }

        # that's a nice operation u got there python
        config |= wled_config
        print(config)

        super().__init__(ledfx, config)

    def activate(self):
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
            packets, remainder, byteData[data_start:data_end], push=True
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
