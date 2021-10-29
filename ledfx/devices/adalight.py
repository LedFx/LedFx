import logging
from enum import Enum
from struct import pack

import numpy as np
import serial
import serial.tools.list_ports
import voluptuous as vol

from ledfx.devices import Device, packets

_LOGGER = logging.getLogger(__name__)

COLOR_ORDERS = [
    "RGB",
    "RBG",
    "GRB",
    "BRG",
    "GBR",
    "BGR",
]


class AvailableCOMPorts:
    ports = serial.tools.list_ports.comports()

    available_ports = []

    for p in ports:
        available_ports.append(p.device)


class AdalightDevice(Device):
    """Adalight device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "name", description="Friendly name for the device"
                ): str,
                vol.Required(
                    "com_port",
                    description="COM port for Adalight compatible device",
                ): vol.In(list(AvailableCOMPorts.available_ports)),
                vol.Required(
                    "baudrate", description="baudrate", default=500000
                ): vol.All(vol.Coerce(int), vol.Range(min=115200)),
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
        self.serial = None
        self.baudrate = self._config["baudrate"]
        self.com_port = self._config["com_port"]
        self.color_order = self._config["color_order"]

    def activate(self):
        try:
            if self.serial and self.serial.isOpen:
                return

            self.serial = serial.Serial(self.com_port, self.baudrate)
            if self.serial.isOpen:
                super().activate()

        except serial.SerialException:
            _LOGGER.critical(
                "Serial Error: Please ensure your device is connected, functioning and the correct COM port is selected."
            )
            # Todo: Trigger the UI to refresh after the clear effect call. Currently it still shows as active.
            self.deactivate()

    def deactivate(self):
        super().deactivate()
        if self.serial:
            self.serial.close()

    def flush(self, data):
        try:
            self.serial.write(packets.build_adalight_packet(data, self.color_order))

        except serial.SerialException:
            _LOGGER.critical(
                "Serial Connection Interrupted. Please check connections and ensure your device is functioning correctly."
            )
            self.deactivate()
