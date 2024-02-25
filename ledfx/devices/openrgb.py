import logging
import socket

import numpy as np
import voluptuous as vol
from openrgb import OpenRGBClient

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
        """
        Initializes an OpenRGB device.

        Args:
            ledfx (LedFx): The main LedFx instance.
            config (dict): The configuration for the OpenRGB device.

        Attributes:
            _ledfx (LedFx): The main LedFx instance.
            ip_address (str): The IP address of the OpenRGB device.
            port (int): The port number of the OpenRGB device.
            openrgb_device_id (int): The ID of the OpenRGB device.
        """
        super().__init__(ledfx, config)
        self._ledfx = ledfx
        self.ip_address = self._config["ip_address"]
        self.port = self._config["port"]
        self.openrgb_device_id = self._config["openrgb_id"]

    def activate(self):
        """
        Activates the OpenRGB device.

        This method establishes a connection with the OpenRGB server and checks if the device supports direct mode.
        If the device is not reachable or the device ID is not found, it deactivates the device and sets the online status to False.
        If the device does not support direct mode, it deactivates the device and sets the online status to False.
        Otherwise, it sets the online status to True and calls the superclass's activate method.

        Raises:
            ConnectionRefusedError: If the OpenRGB server is not running or the device is not reachable.
            TimeoutError: If the connection to the OpenRGB server times out.
            IndexError: If the OpenRGB device ID is not found.
        """
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

        except (ConnectionRefusedError, TimeoutError):
            _LOGGER.warning(
                f"{self.openrgb_device_id} not reachable. Is OpenRGB server running?"
            )
            self.set_offline()
            return

        except IndexError:
            _LOGGER.warning(
                f"Couldn't find OpenRGB device ID: {self.openrgb_device_id}"
            )
            self.set_offline()
            return

        device_supports_direct = False
        for mode in self.openrgb_device.modes:
            if mode.name.lower() == "direct":
                device_supports_direct = True
        if not device_supports_direct:
            _LOGGER.warning(
                f"{self.openrgb_device_id} doesn't support direct mode - not supported by LedFx."
            )
            self.set_offline()
            return
        else:
            self._online = True
            super().activate()

    def deactivate(self):
        """
        Deactivates the OpenRGB device.

        This method overrides the deactivate method of the base class.
        """
        super().deactivate()

    def flush(self, data: np.ndarray):
        """
        Flush LED data to the OpenRGB device.

        Args:
            data (ndarray): The LED data to be flushed.

        Raises:
            AttributeError: If the OpenRGB device is not activated.
            ConnectionAbortedError: If the device connection is aborted.
            ConnectionResetError: If the device connection is reset.
            BrokenPipeError: If there is a broken pipe in the device connection.
        """
        try:
            OpenRGB.send_out(
                self.openrgb_device.comms.sock,
                data,
                self.openrgb_device.id,
            )
        except AttributeError:
            self.activate()

        except (
            ConnectionAbortedError,
            ConnectionResetError,
            BrokenPipeError,
        ) as e:
            # Unexpected device disconnect - deactivate and tell the frontend
            _LOGGER.warning(
                f"Device {self.name} connection issue ({type(e).__name__}): {e}"
            )
            self.set_offline()

    @staticmethod
    def send_out(sock: socket.socket, data: np.ndarray, device_id: int):
        """
        Sends the given data to the specified device using the provided socket.

        Args:
            sock (socket.socket): The socket to send the data through.
            data (np.ndarray): The data to be sent.
            device_id (int): The ID of the device to send the data to.
        """
        packet = packets.build_openrgb_packet(data, device_id)
        sock.send(packet)
