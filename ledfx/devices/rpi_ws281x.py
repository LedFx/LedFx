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

# These pins implement hardware PWM which results in a more responsive
# experience. However, these pins require root privileges.
HARDWARE_PWM_PINS = [12, 13, 18, 19]

# These pins are software-based and rely on the timing of the Linux Kernel. This
# results in noticeable glitches and delays.
SPI_PINS = [21, 10]


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
                ): vol.In(list(HARDWARE_PWM_PINS + SPI_PINS)),
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
            from rpi_ws281x import PixelStrip, ws
        except ImportError:
            _LOGGER.warning(
                "Unable to load ws281x module - are you on a Raspberry Pi?"
            )
            self.deactivate()
        
        pin = self.config["gpio_pin"]
        if pin in HARDWARE_PWM_PINS:
            _LOGGER.WARNING("Pin %d is a PWM pin and requires root privileges. If the program crashes with permission errors, try running with 'sudo'.")

        strip_types = {
            ColorOrder.RGB: ws.WS2811_STRIP_RGB,
            ColorOrder.RBG: ws.WS2811_STRIP_RBG,
            ColorOrder.GRB: ws.WS2811_STRIP_GRB,
            ColorOrder.BRG: ws.WS2811_STRIP_BRG,
            ColorOrder.GBR: ws.WS2811_STRIP_GBR,
            ColorOrder.BGR: ws.WS2811_STRIP_BGR,
        }
        strip_type = strip_types[self.color_order]

        self.strip = PixelStrip(
            num=self.pixel_count,
            pin=self.config["gpio_pin"],
            freq_hz=self.LED_FREQ_HZ,
            dma=self.LED_DMA,
            invert=self.LED_INVERT,
            brightness=self.LED_BRIGHTNESS,
            channel=self.LED_CHANNEL,
            strip_type=strip_type,
        )
        self.strip.begin()

        # We must call the parent active() method to finish setting up this
        # device.
        super().activate()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""
        byteData = data.astype(np.dtype("B"))

        pixel = 0
        for rgb in byteData:
            rgb_bytes = rgb.tobytes()
            self.strip.setPixelColor(
                pixel,
                rgb_bytes[0],
                rgb_bytes[1],
                rgb_bytes[2],
            )
            pixel += 1
        self.strip.show()
