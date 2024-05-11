import logging
from enum import Enum

import numpy as np
import voluptuous as vol

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)

#class ColorOrder(Enum):
#    RGB = 1



#COLOR_ORDERS = {
#    "RGB": ColorOrder.RGB,
#}


class RPI_NEOPIXEL(Device):
    """RPi NEOPIXEL STRIP WS2812 device support using Adafruit-circuitpython-neopixel library"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=144,
                ): vol.All(int, vol.Range(min=1)),                 
                #vol.Required( #Uncomment to test this list in the frontend. PIN is hardcoded later anyway... 
                    #"gpio_pin",
                    #description="Raspberry Pi GPIO pin your LEDs are connected to",
                #): vol.In(list([17, 18, 19])), # [18, 17, 19] Frontend doesn't allow to create a device if the first element in the list is selected
                #vol.Required( 
                #    "color_order", description="Color order", default="RGB"
                #): vol.In(list(COLOR_ORDERS.keys())),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

    def activate(self):
        try:
            import neopixel #Adafruit-circuitpython-neopixel library
            import board
        except ImportError:
            _LOGGER.warning(
                "Unable to load Neopixel module - are you on a Raspberry Pi?"
            )
            self.deactivate()
        self.strip = neopixel.NeoPixel(
            board.D18, #Raspberry Pi GPIO PIN 18, hardcoded
            self.pixel_count, #Number of pixels
        )     
        super().activate()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""    
        pixelData = [tuple(led) for led in data.tolist()] #Convert each row to a tuple. In Neopixel library, colors for each pixel are stored as tuples.
        self.strip[:] = pixelData[:]
        self.strip.show()
