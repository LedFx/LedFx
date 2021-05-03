import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class UDPDevice(NetworkedDevice):
    """Generic UDP device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Friendly name for the device"
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
                description="Data to be prepended in hex format. Use 0201 for WLED devices",
            ): str,
            vol.Optional(
                "data_postfix",
                description="Data to be appended in hex format",
            ): str,
        }
    )

    def activate(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _LOGGER.info(f"UDP sender for {self.config['name']} started.")
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.info(f"UDP sender for {self.config['name']} stopped.")
        self._sock = None

    def flush(self, data):
        try:
            UDPDevice.send_out(
                self._sock,
                self.destination,
                self._config["port"],
                data,
                self._config.get("data_prefix"),
                self._config.get("data_postfix"),
                self._config["include_indexes"],
            )
        except AttributeError:
            self.activate()

    @staticmethod
    def send_out(
        sock,
        dest,
        port,
        data,
        prefix=None,
        postfix=None,
        include_indexes=False,
    ):
        udpData = bytearray()
        byteData = data.astype(np.dtype("B"))

        # Append the prefix if provided
        if prefix:
            try:
                udpData.extend(bytes.fromhex(prefix))

            except ValueError:
                _LOGGER.warning(f"Cannot convert prefix {prefix} to hex value")

        # Append all of the pixel data
        if include_indexes:
            for i in range(len(byteData)):
                udpData.extend(bytes([i]))
                udpData.extend(byteData[i].flatten().tobytes())
        else:
            udpData.extend(byteData.flatten().tobytes())

        # Append the postfix if provided
        if postfix:
            try:
                udpData.extend(bytes.fromhex(postfix))
            except ValueError:
                _LOGGER.warning(
                    f"Cannot convert postfix {postfix} to hex value"
                )

        sock.sendto(
            bytes(udpData),
            (dest, port),
        )
