import base64
import json
import logging
import socket
import time

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice
from ledfx.devices.__init__ import fps_validator
from ledfx.devices.utils.socket_singleton import SocketSingleton
from ledfx.utils import AVAILABLE_FPS

_LOGGER = logging.getLogger(__name__)

# this is very much a prototype implementation
# no current known documentation on the protocol
# may be a variant of razer if we cannot find any other info
# use with caution.
#
# Known issues
#


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
                    (f for f in AVAILABLE_FPS if f >= 30),
                    list(AVAILABLE_FPS)[-1],
                ),
            ): fps_validator,
            vol.Optional(
                "byte1", description="injection 1", default=0xB0
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional(
                "byte2", description="injection 2", default=0x00
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
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
        self.udp_server = None

        # this header is reverse engineered and fuzzed to functional
        self.pre_dreams = [
            0xBB,
            0x00,
            0xFA,
            0xB0,
            0x00,
        ]  # original header captured by Schifty but modified stretch to 0
        self.pre_chroma = [
            0xBB,
            0x00,
            0x0E,
            0xB0,
            0x00,
        ]  # captured from razer chroma but modified stetch to 0
        self.pre_goveee = [
            0xBB,
            0x00,
            0x20,
            0xB0,
            0x00,
        ]  # captured from govee screen edge direct control
        # 0 0xbb - unknown
        # 1 0x00 - unknown
        # 2 0x0e - unknown
        # 3 0xb0 - unknown
        # 4 0x00 - unknown
        # 5 0x01 - 0 = segments, 1 = stretch
        # 6 0x04 - color triples to follow
        # Header to here  ST  CN | RGB trip |           |           |           | CHK
        # bb, 00, 0e, b0, 01, 04, fe, 00, 05, 00, 00, 00, 00, 00, 00, 00, 00, 00, fb

    def send_udp(self, message, port=4003):
        data = json.dumps(message).encode("utf-8")
        self.udp_server.send_data(data, (self._config["ip_address"], port))

    # Set Light Brightness
    def set_brightness(self, value):
        self.send_udp({"msg": {"cmd": "brightness", "data": {"value": value}}})

    def send_devstatus_enquiry(self):
        self.send_udp({"msg": {"cmd": "devStatus", "data": {}}})

    def send_activate(self):
        # BB 00 01 B1 01 0A
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": "uwABsQEK"}}})

    def send_deactivate(self):
        # BB 00 01 B1 00 0B
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": "uwABsQAL"}}})

    def send_encoded_packet(self, packet):
        command = base64.b64encode(packet.tobytes()).decode("utf-8")
        self.send_udp({"msg": {"cmd": "razer", "data": {"pt": command}}})

    def create_razer_packet(self, colors):
        header = np.array(self.pre_goveee + [len(colors) // 3], dtype=np.uint8)
        full_packet = np.concatenate((header, colors))
        full_packet = np.append(
            full_packet, self.calculate_xor_checksum_fast(full_packet)
        )
        return full_packet

    def deactivate(self):
        _LOGGER.info(f"Govee {self.name} deactivate")
        if self.udp_server is not None:
            self.send_deactivate()
            self.udp_server.close_socket()
        super().deactivate()

    def activate(self):
        _LOGGER.info(f"Govee {self.name} Activating UDP stream mode...")

        self.udp_server = SocketSingleton(recv_port=self.recv_port)

        # enquiry to status is current used only to check if the device is responding adn set offline if not
        # the response information is of little use
        # example: {"msg":{"cmd":"devStatus","data":{"onOff":1,"brightness":100,"color":{"r":255,"g":255,"b":255},"colorTemInKelvin":0}}}
        _LOGGER.info(f"Fetching govee {self.name} device info...")
        status, active = self.get_device_status()
        _LOGGER.info(f"{self.name} active: {active} {status}")
        if not active:
            self.set_offline()
            return

        # the ordering and delay in this implementation is derived through trial and error only
        # incorrect order can lead to flickering of devices tested if wake from sleep
        # we have not other information as to best practice here
        delay = 0.1
        time.sleep(delay)
        self.set_brightness(100)
        time.sleep(delay)
        self.send_activate()

        super().activate()

    @staticmethod
    def calculate_xor_checksum_fast(packet):
        return np.bitwise_xor.reduce(packet)

    def flush(self, data):
        rgb_data = data.flatten().astype(np.uint8)
        packet = self.create_razer_packet(rgb_data)
        self.send_encoded_packet(packet)

    # Get Device Status
    def get_device_status(self):
        self.send_devstatus_enquiry()
        self.udp_server.settimeout(1.0)
        try:
            # Receive Response from the device
            response, addr = self.udp_server.receive_data(1024)
            if self._config["ip_address"] == addr[0]:
                return f"{response.decode('utf-8')}", True
            else:
                return (
                    f"Discarding packet from unknown {addr[0]} on port {addr[1]}",
                    False,
                )

        except socket.timeout:
            return "No response received within the timeout period.", False

    async def async_initialize(self):
        await super().async_initialize()

        config = {
            "name": self.config["name"],
            "pixel_count": self.config["pixel_count"],
            "refresh_rate": self.config["refresh_rate"],
        }

        self.update_config(config)
