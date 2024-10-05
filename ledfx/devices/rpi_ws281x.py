import logging
from enum import Enum

import numpy as np
import voluptuous as vol

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)

try:
    from rpi_ws281x import PixelStrip, WS2811_STRIP_RGB, WS2811_STRIP_RBG, WS2811_STRIP_GRB, WS2811_STRIP_GBR, WS2811_STRIP_BRG, WS2811_STRIP_BGR

    COLOR_ORDERS = {
        "RGB": WS2811_STRIP_RGB,
        "RBG": WS2811_STRIP_RBG,
        "GRB": WS2811_STRIP_GRB,
        "BRG": WS2811_STRIP_GBR,
        "GBR": WS2811_STRIP_BRG,
        "BGR": WS2811_STRIP_BGR,
    }
    rpi_supported = True
except ImportError:
    # dummy values to stop things going bang
    COLOR_ORDERS = {
        "RGB": 1,
        "RBG": 2,
        "GRB": 3,
        "BRG": 4,
        "GBR": 5,
        "BGR": 6,
    }
    rpi_supported = False

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
                    default=10,
                ): vol.In(list([10,12,13,18,21])),
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

    def config_updated(self, config):
        self.color_order = COLOR_ORDERS[self._config["color_order"]]
        self.deactivate()
        self.activate()

    def activate(self):
        if not rpi_supported:
            _LOGGER.warning(
                "Unable to load ws281x module - are you on a Raspberry Pi?"
            )
            self.set_offline()
            _LOGGER.warning(f"You chose {self.color_order}")
            return

        self.buffer = bytearray(self.pixel_count * 4)

        # following configuration is based on the example from the rpi-ws281x library
        # https://github.com/rpi-ws281x/rpi-ws281x-python/blob/50cc48bbb5d6ab2d205e58606892514a29571f5e/examples/strandtest.py#L20
        if self.config["gpio_pin"] == 13:
            self.LED_CHANNEL = 1

        self.strip = PixelStrip(
            self.pixel_count,
            self.config["gpio_pin"],
            self.LED_FREQ_HZ,
            self.LED_DMA,
            self.LED_INVERT,
            self.LED_BRIGHTNESS,
            self.LED_CHANNEL,
            self.color_order,
        )
        self.strip.begin()
        super().activate()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""

        for idx, rgb in enumerate(data):
            self.strip.setPixelColor(
                idx,
                (round(rgb[0]) << 16) | (round(rgb[1]) << 8) | round(rgb[2])
            )
        self.strip.show()