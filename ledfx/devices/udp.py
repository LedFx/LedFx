import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import Device
from ledfx.utils import async_fire_and_return, resolve_destination

_LOGGER = logging.getLogger(__name__)


class UDPDevice(Device):
    """Generic UDP device support"""

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
                "pixel_count",
                description="Number of individual pixels",
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                "include_indexes",
                description="Include the index for every LED",
                default=False,
            ): bool,
            vol.Optional(
                "data_prefix",
                description="Data to be appended in hex format",
            ): str,
            vol.Optional(
                "data_postfix",
                description="Data to be prepended in hex format",
            ): str,
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
        super().activate()

    def deactivate(self):
        super().deactivate()
        self._sock = None

    @property
    def pixel_count(self):
        return int(self._config["pixel_count"])

    def flush(self, data):
        udpData = bytearray()
        byteData = data.astype(np.dtype("B"))

        # Append the prefix if provided
        prefix = self._config.get("data_prefix")
        if prefix:
            try:
                udpData.extend(bytes.fromhex(prefix))
            except ValueError:
                _LOGGER.warning(f"Cannot convert prefix {prefix} to hex value")

        # Append all of the pixel data
        if self._config["include_indexes"]:
            for i in range(len(byteData)):
                udpData.extend(bytes([i]))
                udpData.extend(byteData[i].flatten().tobytes())
        else:
            udpData.extend(byteData.flatten().tobytes())

        # Append the postfix if provided
        postfix = self._config.get("data_postfix")
        if postfix:
            try:
                udpData.extend(bytes.fromhex(postfix))
            except ValueError:
                _LOGGER.warning(
                    f"Cannot convert postfix {postfix} to hex value"
                )

        self._sock.sendto(
            bytes(udpData),
            (self.device_ip, self._config["port"]),
        )
