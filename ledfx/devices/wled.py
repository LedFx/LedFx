import logging
import socket

import voluptuous as vol

from ledfx.devices import Device
from ledfx.devices.ddp import DDPDevice
from ledfx.utils import async_fire_and_return, resolve_destination

_LOGGER = logging.getLogger(__name__)


class WLEDDevice(Device):
    """Dedicated WLED device support"""

    UDPPort = 21324

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
        self.frame_count = 0

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
        return self._config["pixel_count"]

    def on_resolved_dest(self, dest):
        self.resolved_dest = dest

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

    def flush(self, data):
        self.frame_count += 1
        DDPDevice.send_out(
            self._sock, self.resolved_dest, data, self.frame_count
        )
