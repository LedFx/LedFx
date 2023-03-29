import logging

import flux_led
import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class ZenggeDevice(NetworkedDevice):
    """Zengge/MagicHome/FluxLED device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Zengge/MagicHome/FluxLED"
        self.bulb = flux_led.WifiLedBulb(config["ip_address"])

    def activate(self):
        super().activate()
        self.bulb.turnOn()

    def deactivate(self):
        super().deactivate()
        self.bulb.turnOff()

    def flush(self, data):
        try:
            byteData = data.astype(np.dtype("B"))
            rgb = byteData.flatten().tolist()
            self.bulb.setRgb(rgb[0], rgb[1], rgb[2])

        except Exception as e:
            _LOGGER.error("Error connecting to bulb: %s", e)
