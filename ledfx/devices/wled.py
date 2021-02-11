import logging
import socket

import voluptuous as vol

from ledfx.devices import NetworkedDevice
from ledfx.devices.ddp import DDPDevice
from ledfx.utils import WLED

_LOGGER = logging.getLogger(__name__)


class WLEDDevice(NetworkedDevice):
    """Dedicated WLED device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "timeout",
                description="Time between LedFx effect off and WLED effect activate",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(0, 10)),
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

    async def async_initialize(self):
        await super().async_initialize()
        wled_config = await WLED.get_config(self.destination)

        _LOGGER.info(f"Received WLED config from {self.destination}")

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

        await WLED.set_sync_mode(self.destination, "ddp")
        await WLED.set_inactivity_timeout(
            self.destination, self._config["timeout"]
        )
