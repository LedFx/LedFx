import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice, packets

_LOGGER = logging.getLogger(__name__)


class OpenRGB(NetworkedDevice):
    """OpenRGB protocol device support"""

    @staticmethod
    @property
    def CONFIG_SCHEMA():
        return vol.Schema(
            {
                vol.Required(
                    "name", description="Friendly name for the device"
                ): str,
                vol.Required(
                    "openrgb_name",
                    description="Exact name of openRGB device (within openRGB).",
                ): str,
                vol.Required(
                    "pixel_count",
                    description="Number of individual pixels",
                    default=1,
                ): vol.All(int, vol.Range(min=1)),
                vol.Required(
                    "port",
                    description="Port for the UDP device",
                    default=6742,
                ): vol.All(int, vol.Range(min=1, max=65535)),
            }
        )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.ip_address = self._config["ip_address"]
        self.port = self._config["port"]
        self.openrgb_device_name = self._config["openrgb_name"]

    def activate(self):
        try:
            from openrgb import OpenRGBClient
            try:
                self.openrgb_device = OpenRGBClient(
                    self.ip_address, self.port, "LedFx", 2  # protocol_version
                ).get_devices_by_name(f"{self.openrgb_device_name}")[0]
            except (ConnectionRefusedError, TimeoutError):
                _LOGGER.error(
                    f"{self.openrgb_device_name} not reachable. Is the api server running?"
                )
                return
            # check for eedevice
            
            device_supports_direct = False
            for mode in self.openrgb_device.modes:
                if mode.name.lower() == "direct":
                    device_supports_direct = True
            if not device_supports_direct:
                raise ValueError()
        except ImportError:
            _LOGGER.critical("Unable to load openrgb library")
            self.deactivate()
        except IndexError:
            _LOGGER.critical(
                f"Couldn't find openRGB device named: {self.openrgb_device_name}"
            )
            self.deactivate()
        except ValueError:
            _LOGGER.critical(
                f"{self.openrgb_device_name} doesn't support direct mode, and isn't suitable for streamed effects from LedFx"
            )
            self.deactivate()
        else:
            super().activate()

    def deactivate(self):
        super().deactivate()

    def flush(self, data):
        """Flush LED data to the strip"""
        try:
            OpenRGB.send_out(
                self.openrgb_device.comms.sock,
                data,
                self.openrgb_device.id,
            )
        except AttributeError:
            self.activate()

    @staticmethod
    def send_out(sock: socket.socket, data: np.ndarray, device_id: int):
        packet = packets.build_openrgb_packet(data, device_id)
        sock.send(packet)
