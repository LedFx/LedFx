import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice, packets
from ledfx.events import DevicesUpdatedEvent

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
                    "openrgb_id",
                    description="ID of OpenRGB device (within OpenRGB).",
                    default=0,
                ): vol.All(int, vol.Range(min=0)),
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
        self._ledfx = ledfx
        self.ip_address = self._config["ip_address"]
        self.port = self._config["port"]
        self.openrgb_device_id = self._config["openrgb_id"]
        self._online = True

    def activate(self):
        try:
            from openrgb import OpenRGBClient

            try:
                self.openrgb_device = OpenRGBClient(
                    self.ip_address,
                    self.port,
                    self.name,
                    3,  # protocol_version
                )
                self.openrgb_device = self.openrgb_device.devices[
                    self.openrgb_device_id
                ]
                self._online = True
            except (ConnectionRefusedError, TimeoutError):
                _LOGGER.warning(
                    f"{self.openrgb_device_id} not reachable. Is the api server running?"
                )
                self._online = False
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
                f"Couldn't find OpenRGB device ID: {self.openrgb_device_id}"
            )
            self._online = False
            self.deactivate()
        except ValueError:
            _LOGGER.critical(
                f"{self.openrgb_device_id} doesn't support direct mode, and isn't suitable for streamed effects from LedFx"
            )
            self.deactivate()
        else:
            self._online = True
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
        except ConnectionAbortedError:
            _LOGGER.warning(f"Device disconnected: {self.openrgb_device_id}")
            self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))
            self._online = False
            self.deactivate()

    @staticmethod
    def send_out(sock: socket.socket, data: np.ndarray, device_id: int):
        packet = packets.build_openrgb_packet(data, device_id)
        sock.send(packet)
