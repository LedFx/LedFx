import logging

import numpy as np
import voluptuous as vol

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)


COLOR_ORDERS = [
    "RGB",
    "RBG",
    "GRB",
    "BRG",
    "GBR",
    "BGR",
]


class RPI_WS281X(Device):
    """RPi WS281X device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "name", description="Friendly name for the device"
                ): str,
                vol.Required(
                    "gpio_pin",
                    description="Raspberry Pi GPIO pin your LEDs are connected to",
                ): vol.In(list([21, 31])),
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=1,
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Required(
                    "color_order", description="Color order", default="RGB"
                ): vol.In(list(COLOR_ORDERS)),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.LED_FREQ_HZ = 800000
        self.LED_DMA = 10
        self.LED_BRIGHTNESS = 255
        self.LED_INVERT = False
        self.LED_CHANNEL = 0
        self.color_order = self._config["color_order"]

    def activate(self):

        try:
            from rpi_ws281x import PixelStrip
        except ImportError:
            _LOGGER.critical(
                "Unable to load ws281x module - are you on a Raspberry Pi?"
            )
            self.deactivate()

        self.strip = PixelStrip(
            self.pixel_count,
            self.config["gpio_pin"],
            self.LED_FREQ_HZ,
            self.LED_DMA,
            self.LED_INVERT,
            self.LED_BRIGHTNESS,
            self.LED_CHANNEL,
        )
        self.strip.begin()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""
        combined_rgb = np.zeros((len(data),1), dtype=np.int32)

        # # alternative way to rearrange RGB
        # order = list(self.color_order.replace("R","0").replace("G","1").replace("B","2"))
        # combined_rgb[:,0] = (data[:,int(order[0])] << 16) | (data[:,int(order[1])] << 8) | data[:,int(order[2])]

        if self.color_order == "RGB":
            combined_rgb[:,0] = (data[:,0] << 16) | (data[:,1] << 8) | data[:,2]
        elif self.color_order == "GRB":
            combined_rgb[:,0] = (data[:,1] << 16) | (data[:,0] << 8) | data[:,2]
        elif self.color_order == "BGR":
            combined_rgb[:,0] = (data[:,2] << 16) | (data[:,1] << 8) | data[:,0]
        elif self.color_order == "RBG":
            combined_rgb[:,0] = (data[:,0] << 16) | (data[:,2] << 8) | data[:,1]
        elif self.color_order == "BRG":
            combined_rgb[:,0] = (data[:,2] << 16) | (data[:,0] << 8) | data[:,1]
        elif self.color_order == "GBR":
            combined_rgb[:,0] = (data[:,1] << 16) | (data[:,2] << 8) | data[:,0]
        
        out_lights = combined_rgb.tolist()
        strip_range = slice(0,len(data))
        self.strip._led_data.__setitem__(strip_range, out_lights)
        self.strip.show()
