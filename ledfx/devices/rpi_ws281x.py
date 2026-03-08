import logging

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import BaseRegistry

_LOGGER = logging.getLogger(__name__)

try:
    from rpi_ws281x import (
        SK6812_STRIP_BGRW,
        SK6812_STRIP_BRGW,
        SK6812_STRIP_GBRW,
        SK6812_STRIP_GRBW,
        SK6812_STRIP_RBGW,
        SK6812_STRIP_RGBW,
        WS2811_STRIP_BGR,
        WS2811_STRIP_BRG,
        WS2811_STRIP_GBR,
        WS2811_STRIP_GRB,
        WS2811_STRIP_RBG,
        WS2811_STRIP_RGB,
        PixelStrip,
    )

    COLOR_ORDERS = {
        "RGB": WS2811_STRIP_RGB,
        "RBG": WS2811_STRIP_RBG,
        "GRB": WS2811_STRIP_GRB,
        "BRG": WS2811_STRIP_BRG,
        "GBR": WS2811_STRIP_GBR,
        "BGR": WS2811_STRIP_BGR,
        "RGBW": SK6812_STRIP_RGBW,
        "RBGW": SK6812_STRIP_RBGW,
        "GRBW": SK6812_STRIP_GRBW,
        "GBRW": SK6812_STRIP_GBRW,
        "BRGW": SK6812_STRIP_BRGW,
        "BGRW": SK6812_STRIP_BGRW,
    }

    RGBW_MODES = {
        SK6812_STRIP_RGBW,
        SK6812_STRIP_RBGW,
        SK6812_STRIP_GRBW,
        SK6812_STRIP_GBRW,
        SK6812_STRIP_BRGW,
        SK6812_STRIP_BGRW,
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
        "RGBW": 7,
        "RBGW": 8,
        "GRBW": 9,
        "GBRW": 10,
        "BRGW": 11,
        "BGRW": 12,
    }
    rpi_supported = False

WHITE_CORRECTION = {
    "None": 1,
    "Accurate": 2,
    "Brighter": 3,
}


# This wrapper is required to prevent config_update lifecycle breakage
# You cannot inherit from Device directly
@BaseRegistry.no_registration
class DeviceWrapper(Device):
    pass


class RPI_WS281X(DeviceWrapper):
    """RPi WS281X device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "color_correction",
                description="White handling",
                default="None",
            ): vol.In(list(WHITE_CORRECTION.keys())),
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                "gpio_pin",
                description="Raspberry Pi GPIO pin your LEDs are connected to",
                default=18,
            ): vol.In(list([10, 12, 13, 18, 21])),
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
        self._device_type = "RPi_WS281X"
        self.color_correction = WHITE_CORRECTION[
            self._config["color_correction"]
        ]

    def config_updated(self, config):
        self.color_order = COLOR_ORDERS[config["color_order"]]
        self.color_correction = WHITE_CORRECTION[
            self._config["color_correction"]
        ]
        self.deactivate()
        self.activate()

    def activate(self):
        if not rpi_supported:
            _LOGGER.warning(
                "Unable to load ws281x module - are you on a Raspberry Pi?"
            )
            self.set_offline()
            return

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

        if self.color_order in RGBW_MODES:
            for idx, rgb in enumerate(data):
                if self.color_correction != WHITE_CORRECTION["None"]:
                    r, g, b = rgb
                    min_val = min(r, g, b)

                    if self.color_correction == WHITE_CORRECTION["Accurate"]:
                        rgb = np.array(
                            [r - min_val, g - min_val, b - min_val, min_val]
                        )  # W channel from RGB and RGB is reduced
                    elif self.color_correction == WHITE_CORRECTION["Brighter"]:
                        rgb = np.append(
                            rgb, min_val
                        )  # add min_val for W channel and RGB is not reduced
                else:
                    rgb = np.append(rgb, 0)  # add 0 for W channel

                self.strip.setPixelColor(
                    idx,
                    (round(rgb[3]) << 24)
                    | (round(rgb[0]) << 16)
                    | (round(rgb[1]) << 8)
                    | round(rgb[2]),
                )
        else:
            for idx, rgb in enumerate(data):
                self.strip.setPixelColor(
                    idx,
                    (round(rgb[0]) << 16)
                    | (round(rgb[1]) << 8)
                    | round(rgb[2]),
                )
        self.strip.show()
