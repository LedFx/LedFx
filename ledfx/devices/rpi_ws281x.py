import logging
from enum import Enum

import numpy as np
import voluptuous as vol

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)


class ColorOrder(Enum):
    RGB = 1
    RBG = 2
    GRB = 3
    BRG = 4
    GBR = 5
    BGR = 6


COLOR_ORDERS = {
    "RGB": ColorOrder.RGB,
    "RBG": ColorOrder.RBG,
    "GRB": ColorOrder.GRB,
    "BRG": ColorOrder.BRG,
    "GBR": ColorOrder.GBR,
    "BGR": ColorOrder.BGR,
}


class RPI_WS281X(Device):
    """RPi WS281X device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=1,
                ): vol.All(int, vol.Range(min=1)),
                vol.Required(
                    "gpio_pin",
                    description="Raspberry Pi GPIO pin your LEDs are connected to",
                ): vol.In(list([21, 31])),
                vol.Required(
                    "color_order", description="Color order", default="RGB"
                ): vol.In(list(COLOR_ORDERS.keys())),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.LED_FREQ_HZ = 800000
        self.LED_DMA = 10
        self.LED_BRIGHTNESS = 255
        self.LED_INVERT = False
        self.LED_CHANNEL = 0
        self.color_order = COLOR_ORDERS[self._config["color_order"]]

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
        byteData = data.astype(np.dtype("B"))

        i = 3
        for rgb in byteData:
            i += 3
            rgb_bytes = rgb.tobytes()
            self.buffer[i], self.buffer[i + 1], self.buffer[i + 2] = (
                rgb_bytes[0],
                rgb_bytes[1],
                rgb_bytes[2],
            )

            if self.color_order == ColorOrder.RGB:
                continue
            elif self.color_order == ColorOrder.GRB:
                self.swap(self.buffer, i, i + 1)
            elif self.color_order == ColorOrder.BGR:
                self.swap(self.buffer, i, i + 2)
            elif self.color_order == ColorOrder.RBG:
                self.swap(self.buffer, i + 1, i + 2)
            elif self.color_order == ColorOrder.BRG:
                self.swap(self.buffer, i, i + 1)
                self.swap(self.buffer, i + 1, i + 2)
            elif self.color_order == ColorOrder.GBR:
                self.swap(self.buffer, i, i + 1)
                self.swap(self.buffer, i, i + 2)
            for led in len(self.pixel_count):
                self.strip.setPixelColor(
                    led,
                    self.buffer[led],
                    self.buffer[led + 1],
                    self.buffer[led + 2],
                )
            self.strip.show()

    def swap(self, array, pos1, pos2):
        array[pos1], array[pos2] = array[pos2], array[pos1]
