import itertools
import logging

import numpy as np
import voluptuous as vol

from ledfx.devices import Device

_LOGGER = logging.getLogger(__name__)


class SPI_WS281X(Device):
    """
    RPi WS281X device support via SPI (works with RPi 5). Based on https://github.com/fschrempf/py-neopixel-spidev/
    """

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
                    "spi_bus",
                    description="Raspberry Pi SPI Bus LEDs are connected to (using SPI Bus 1 on a Pi requires special setup).",
                    default=0,
                ): vol.In([0, 1]),
                vol.Required(
                    "color_order", description="Color order", default="RGB"
                ): vol.In(
                    list("".join(p) for p in itertools.permutations("RGB"))
                ),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.LED_FREQ_HZ = 800000
        self.SPI_DEVICE = 0

    def activate(self):
        try:
            import spidev
        except ImportError as e:
            described = ImportError(
                "Unable to load spidev module. If you are on a raspberry pi, or another SPI capable linux device, "
                "you can install spidev with 'pip install spidev' inside the ledfx venv."
            )
            _LOGGER.error(described)
            self.deactivate()
            raise described from e

        self.spi = spidev.SpiDev()
        try:
            self.spi.open(self._config["spi_bus"], self.SPI_DEVICE)
        except OSError as e:
            described = OSError(
                "Unable to open SPI device. If you are on a raspberry pi, "
                "you may need to enable SPI in 'sudo raspi-config'. Otherwise make sure the device is not used by another process."
            )
            _LOGGER.error(described)
            self.deactivate()

            raise described from e
        self.spi.mode = 0
        self.spi.max_speed_hz = int(
            4 * self.LED_FREQ_HZ
        )  # 4 SPI bits for one period
        super().activate()

    def deactivate(self):
        if hasattr(self, "spi"):
            self.spi.close()
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""
        self.spi_write(self.get_ordered_pixel_data(data))

    def get_ordered_pixel_data(self, data):
        return data[:, self.get_rgb_indices()]

    def spi_write(self, data):
        """
        Write data to the SPI bus in the WS281x format
        """

        d = np.asarray(data).ravel()
        tx = np.zeros(len(d) * 4, dtype=np.uint8)
        for ibit in range(4):
            tx[3 - ibit :: 4] = (
                ((d >> (2 * ibit + 1)) & 1) * 0x60
                + ((d >> (2 * ibit + 0)) & 1) * 0x06
                + 0x88
            )
        self.spi.writebytes2(
            tx
        )  # This doesn't convert to a python list, so it's faster than xfer or writebytes

    def get_rgb_indices(self):
        color_order = self._config["color_order"]
        return ["RGB".index(c) for c in color_order]
