import base64
import json
import logging
import socket
import time

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice
from ledfx.devices.__init__ import fps_validator
from ledfx.utils import AVAILABLE_FPS

_LOGGER = logging.getLogger(__name__)


class Govee(NetworkedDevice):
    """
    Support for Govee devices with local API control
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Required(
                "pixel_count",
                description="Number of segments (seen in app)",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "refresh_rate",
                description="Target rate that pixels are sent to the device",
                default=next(
                    (f for f in AVAILABLE_FPS if f >= 40),
                    list(AVAILABLE_FPS)[-1],
                ),
            ): fps_validator,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Govee"
        self.status = {}
        self.port = 4003  # Control Port
        self.multicast_group = "239.255.255.250"  # Multicast Address
        self.send_response_port = 4001  # Send Scanning
        self.recv_port = 4002  # Responses
        self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # this might be a problem when using multiple devices, disabling for now
        # self.udp_server.bind(('', self.recv_port))

    def send_udp(self, message, port=4003):
        data = json.dumps(message).encode("utf-8")
        self.udp_server.sendto(data, (self._config["ip_address"], port))

    # Set Light Brightness
    def set_brightness(self, value):
        self.send_udp({"msg": {"cmd": "brightness", "data": {"value": value}}})

    def activate(self):
        _LOGGER.info(f"Govee {self.name} Activating UDP stream mode...")
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": "uwABsQEK"}}})
        time.sleep(0.1)
        self.set_brightness(100)
        time.sleep(0.1)
        super().activate()

    def deactivate(self):
        _LOGGER.info(f"Govee {self.name} deactivate")
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": "uwABsQAL"}}})

        super().deactivate()

    @staticmethod
    def calculate_xor_checksum_fast(packet):
        return np.bitwise_xor.reduce(packet)

    def create_dream_view_packet(self, colors):
        header = np.array(
            [0xBB, 0x00, 250, 0xB0, 0x00, len(colors) // 3], dtype=np.uint8
        )
        full_packet = np.concatenate((header, colors))
        full_packet = np.append(
            full_packet, self.calculate_xor_checksum_fast(full_packet)
        )
        return full_packet

    def send_encoded_packet(self, packet):
        command = base64.b64encode(packet.tobytes()).decode("utf-8")
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": command}}})

    def flush(self, data):
        rgb_data = data.flatten().astype(np.uint8)
        packet = self.create_dream_view_packet(rgb_data)
        self.send_encoded_packet(packet)

    # Get Device Status
    def get_device_status(self):
        self.send_udp({"msg": {"cmd": "devStatus", "data": {}}})
        self.udp_server.settimeout(1.0)
        try:
            # Receive Response from the device
            response, addr = self.udp_server.recvfrom(1024)
            return f"{response.decode('utf-8')}"

        except socket.timeout:
            return "No response received within the timeout period."

    async def async_initialize(self):
        await super().async_initialize()

        _LOGGER.info(f"Fetching govee {self.name} device info...")

        _LOGGER.info(self.get_device_status())

        config = {
            "name": self.config["name"],
            "pixel_count": self.config["pixel_count"],
            "refresh_rate": self.config["refresh_rate"],
        }

        self.update_config(config)
