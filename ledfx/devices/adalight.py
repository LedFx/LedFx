import logging
from enum import Enum

import numpy as np
import serial
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


class AdalightDevice(Device):
    """Adalight device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "com_port",
                description="COM port",
            ): str,
            vol.Required(
                "baudrate", description="baudrate", default=500000
            ): vol.All(vol.Coerce(int), vol.Range(min=115200)),
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                "color_order", description="Color order", default="RGB"
            ): vol.In(list(COLOR_ORDERS.keys())),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.serial = None
        self.baudrate = self._config["baudrate"]
        self.com_port = self._config["com_port"]
        self.color_order = COLOR_ORDERS[self._config["color_order"]]

        # adalight header
        # Byte   Value
        # 0     'A' (0x41)
        # 1     'd' (0x64)
        # 2     'a' (0x61)
        # 3     pixel count, high byte
        # 4     pixel count, low byte
        # 5     Checksum (high byte XOR low byte XOR 0x55)

        buffer_size = 6 + self.pixel_count * 3
        self.buffer = bytearray(buffer_size)

        self.buffer[0] = ord("A")
        self.buffer[1] = ord("d")
        self.buffer[2] = ord("a")
        pixel_count_in_bytes = (self.pixel_count).to_bytes(2, byteorder="big")
        self.buffer[3] = pixel_count_in_bytes[0]
        self.buffer[4] = pixel_count_in_bytes[1]
        self.buffer[5] = self.buffer[3] ^ self.buffer[4] ^ 0x55

    def activate(self):
        try:
            self.serial = serial.Serial(self.com_port, self.baudrate)
            if self.serial.isOpen:
                super().activate()

        except serial.SerialException:
            _LOGGER.critical(
                "Serial Error: Please ensure your device is connected, functioning and the correct COM port is selected."
            )
            # Todo: Trigger the UI to refresh after the clear effect call. Currently it still shows as active.
            self.clear_effect()

    def deactivate(self):
        super().deactivate()
        self.serial.close()

    @property
    def pixel_count(self):
        return int(self._config["pixel_count"])

    def flush(self, data):

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
        try:
            self.serial.write(self.buffer)

        except serial.SerialException:
            _LOGGER.critical(
                "Serial Connection Interrupted. Please check connections and ensure your device is functioning correctly."
            )
            self.deactivate()

    def swap(self, array, pos1, pos2):
        array[pos1], array[pos2] = array[pos2], array[pos1]
