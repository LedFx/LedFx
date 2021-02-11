import logging

import voluptuous as vol

from ledfx.devices.ddp import DDPDevice
from ledfx.utils import WLED

_LOGGER = logging.getLogger(__name__)


class WLEDDevice(DDPDevice):
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
