import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import async_fire_and_return, resolve_destination

_LOGGER = logging.getLogger(__name__)


class FXMatrix(Device):
    """FXMatrix device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Friendly name for the device"
            ): str,
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Required(
                "port", description="Port for the UDP device"
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                "width", description="Number of pixels width"
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                "height", description="Number of pixels height"
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        self.resolved_dest = None
        self.attempt_resolve_dest()

    def attempt_resolve_dest(self):
        _LOGGER.info(
            f"Attempting to resolve device {self.name} address {self._config['ip_address']} ..."
        )
        async_fire_and_return(
            resolve_destination(self._config["ip_address"]),
            self.on_resolved_dest,
            0.5,
        )

    def on_resolved_dest(self, dest):
        self.resolved_dest = dest

    def activate(self):
        if not self.resolved_dest:
            _LOGGER.error(
                f"Cannot activate device {self.name} - destination address {self._config['ip_address']} is not resolved"
            )
            self.attempt_resolve_dest()
            return

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._config["pixel_count"] = int(
            self._config["width"] * self._config["height"]
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        self._sock = None

    @property
    def pixel_count(self):
        return int(self._config["width"] * self._config["height"])

    def flush(self, data):
        udpData = bytearray()
        byteData = data.astype(np.dtype("B"))
        # Append all of the pixel data
        udpData.extend(byteData.flatten().tobytes())

        self._sock.sendto(
            bytes(udpData),
            (self.resolved_dest, self._config["port"]),
        )
