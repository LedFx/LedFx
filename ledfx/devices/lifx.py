import logging

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice
from ledfx.libraries.lifxdev.devices import (  # Import the lifxdev library
    light,
    multizone,
)

_LOGGER = logging.getLogger(__name__)


class LifxDevice(NetworkedDevice):
    """LIFX device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "LIFX"
        if config["pixel_count"] > 1:
            self.bulb = multizone.LifxMultiZone(
                config["ip_address"], label=config["name"]
            )
        else:
            self.bulb = light.LifxLight(
                config["ip_address"], label=config["name"]
            )

    def activate(self):
        super().activate()
        self.bulb.set_power(True)

    def deactivate(self):
        super().deactivate()
        self.bulb.set_power(False)

    def rgb_to_hsb(self, r, g, b):
        r, g, b = r / 255.0, g / 255.0, b / 255.0
        max_color = max(r, g, b)
        min_color = min(r, g, b)
        brightness = max_color

        delta = max_color - min_color
        saturation = 0 if max_color == 0 else (delta / max_color)

        if delta == 0:
            hue = 0
        elif max_color == r:
            hue = (60 * ((g - b) / delta) + 360) % 360
        elif max_color == g:
            hue = (60 * ((b - r) / delta) + 120) % 360
        elif max_color == b:
            hue = (60 * ((r - g) / delta) + 240) % 360
        hue = float(hue)

        return hue, float(saturation), float(brightness)

    def flush(self, data):
        try:
            byteData = data.astype(np.dtype("B")).reshape(-1, 3)
            zone_colors = []

            for pixel in byteData:
                rgb = pixel.tolist()
                hsb = self.rgb_to_hsb(rgb[0], rgb[1], rgb[2])
                zone_colors.append((hsb[0], hsb[1], hsb[2], 3000))

            if len(zone_colors) > 1:
                # print(zone_colors)
                self.bulb.set_multizone(
                    zone_colors, duration=0, index=0, ack_required=False
                )
            else:
                self.bulb.set_color(
                    zone_colors[0], duration=0, ack_required=False
                )

        except Exception as e:
            _LOGGER.error("Error connecting to bulb: %s", e)
