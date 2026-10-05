import logging

import flux_led
import numpy as np
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class ZenggeDevice(NetworkedDevice):
    """Zengge/MagicHome/FluxLED device support"""

    class Config(NetworkedDevice.Config):
        ip_address: str = Field(
            description="Hostname or IP address of the device",
            json_schema_extra={X_REQUIRED: True},
        )
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Zengge/MagicHome/FluxLED"
        self.bulb = flux_led.WifiLedBulb(self.config.ip_address)

    def activate(self):
        super().activate()
        self.bulb.turnOn()

    def deactivate(self):
        super().deactivate()
        self.bulb.turnOff()

    def flush(self, data):
        try:
            byteData = data[0].astype(np.dtype("B"))
            rgb = byteData.tolist()
            self.bulb.setRgb(rgb[0], rgb[1], rgb[2])

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error connecting to bulb: %s", e)
