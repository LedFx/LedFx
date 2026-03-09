import logging

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.devices.utils.rgbw_conversion import (
    RGB_MAPPING,
    WHITE_FUNCS_MAPPING,
    OutputMode,
)
from ledfx.utils import BaseRegistry

RGB_MAPPING = RGB_MAPPING + [color + "W" for color in RGB_MAPPING]

_LOGGER = logging.getLogger(__name__)

try:
    from rpi_ws281x import (
        SK6812_STRIP_RGBW,
        WS2811_STRIP_RGB,
        PixelStrip,
    )

    rpi_supported = True
except ImportError:
    rpi_supported = False


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
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                "gpio_pin",
                description="Raspberry Pi GPIO pin your LEDs are connected to",
                default=10,
            ): vol.In(list([10, 12, 13, 18, 21])),
            vol.Optional(
                "rgb_order",
                description="RGB data order mode, supported for physical hardware that just doesn't play by the rules",
                default="RGB",
            ): vol.All(str, vol.In(RGB_MAPPING)),
            vol.Optional(
                "white_mode",
                description="White channel handling mode, if RGB leave as None. Commonly written as RGBW or RGBA",
                default="None",
            ): vol.All(str, vol.In(WHITE_FUNCS_MAPPING.keys())),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.LED_FREQ_HZ = 800000
        self.LED_DMA = 10
        self.LED_BRIGHTNESS = 255
        self.LED_INVERT = False
        self.LED_CHANNEL = 0
        self._device_type = "RPi_WS281X"
        self.rgb_order = config.get("rgb_order")
        self.white_mode = config.get("white_mode")
        self.output_mode = OutputMode(
            self.rgb_order.strip("W"), self.white_mode
        )
        self.config = config
        self.activate()

    def config_updated(self, config):
        self.rgb_order = config.get("rgb_order")
        self.white_mode = config.get("white_mode")
        self.output_mode = OutputMode(
            self.rgb_order.strip("W"), self.white_mode
        )
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

        if "W" in self.rgb_order:
            strip_type = SK6812_STRIP_RGBW
        else:
            strip_type = WS2811_STRIP_RGB

        self.strip = PixelStrip(
            self.pixel_count,
            self.config["gpio_pin"],
            self.LED_FREQ_HZ,
            self.LED_DMA,
            self.LED_INVERT,
            self.LED_BRIGHTNESS,
            self.LED_CHANNEL,
            strip_type,
        )

        self.strip.begin()
        super().activate()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""

        data = self.output_mode.apply(data)
        if "W" not in self.rgb_order:
            for idx, rgb in enumerate(data):
                self.strip.setPixelColor(
                    idx,
                    (round(rgb[0]) << 16)
                    | (round(rgb[1]) << 8)
                    | round(rgb[2]),
                )
        else:
            if self.white_mode == "None":
                data_rgbw = np.zeros((data.shape[0], 4), dtype=data.dtype)
                data_rgbw[:, :3] = data
            else:
                data_rgbw = data

            for idx, rgbw in enumerate(data_rgbw):
                self.strip.setPixelColor(
                    idx,
                    (round(rgbw[3]) << 24)
                    | (round(rgbw[0]) << 16)
                    | (round(rgbw[1]) << 8)
                    | round(rgbw[2]),
                )
        self.strip.show()
