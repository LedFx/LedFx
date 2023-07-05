import logging
import socket
import time
from typing import Dict, Optional, Tuple

import requests
import voluptuous as vol
from mbedtls import exceptions, tls

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class HueDevice(NetworkedDevice):
    """
    Philips Hue device support (Entertainment Mode UDP streaming)
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the Hue bridge",
            ): str,
            vol.Optional("udp_port", description="port", default=2100): int,
            vol.Required(
                "user_name",
                description="User name",
            ): str,
            vol.Required(
                "client_key",
                description="Client key",
            ): str,
            vol.Required(
                "group_name",
                description="Entertainment zone group name",
            ): str,
        }
    )

    status: Dict[int, Tuple[int, int, int]]
    _sock: Optional[socket.socket] = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        self._dtls_client_context = tls.ClientContext(
            tls.DTLSConfiguration(
                pre_shared_key=(
                    self._config["user_name"],
                    bytes.fromhex(self._config["client_key"]),
                ),
                ciphers=["TLS-PSK-WITH-AES-128-GCM-SHA256"],
            )
        )
        self.status = {}

    def _hue_request(self, method, api_endpoint, data=None):
        return getattr(requests, method.lower())(
            f"http://{self._config['ip_address']}/api/{self._config['user_name']}/{api_endpoint}",
            json=data,
        ).json()

    def _entertainment_groups(self):
        all_groups = self._hue_request("GET", "groups")
        return {
            id: all_groups[id]
            for id in all_groups
            if all_groups[id]["type"] == "Entertainment"
        }

    def activate(self):
        request_data = {"stream": {"active": True}}
        response = self._hue_request(
            "PUT", f"groups/{self._config['group_id']}", request_data
        )[0]
        if "success" in response:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock = self._dtls_client_context.wrap_socket(sock, None)
            self._sock.connect(
                (self._config["ip_address"], self._config["udp_port"])
            )
        else:
            raise Exception("Unable to activate UDP stream mode")

        # I'm a hack, but I seem to be necessary and I work
        for _ in range(10):
            try:
                time.sleep(0.2)
                self._sock.do_handshake()
            except exceptions.TLSError:
                _LOGGER.warning(
                    "Failed to establish TLS handshake when activating the UDP stream.  Retrying."
                )

        super().activate()

    def deactivate(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        request_data = {"stream": {"active": False}}
        self._hue_request(
            "PUT", f"groups/{self._config['group_id']}", request_data
        )

        super().deactivate()

    def flush(self, data):
        pixels = [[int(r), int(g), int(b)] for r, g, b in data]
        send_data = bytearray(b"HueStream")
        send_data.append(1)  # Major version
        send_data.append(0)  # Minor version
        send_data.append(0)  # Sequence Number
        send_data.append(0)  # Reserved
        send_data.append(0)  # Reserved
        send_data.append(0)  # Color Mode (0=RGB, 1=XY)
        send_data.append(0)  # Reserved
        for i in range(len(pixels)):
            light_id = int(self._config["pixel_light_ids"][i])
            send_data.append(0)  # Device Type (0=Light)
            send_data.extend(
                light_id.to_bytes(2, byteorder="big")
            )  # ID of Light
            send_data.append(pixels[i][0])  # Red
            send_data.append(pixels[i][0])  # Red
            send_data.append(pixels[i][1])  # Green
            send_data.append(pixels[i][1])  # Green
            send_data.append(pixels[i][2])  # Blue
            send_data.append(pixels[i][2])  # Blue
        try:
            self._sock.send(send_data)
        except Exception:
            self.activate()

    async def async_initialize(self):
        await super().async_initialize()

        entertainment_groups = self._entertainment_groups()
        group_id = next(
            id
            for id in entertainment_groups
            if entertainment_groups[id].get("name")
            == self._config.get("group_name")
        )
        group = entertainment_groups[group_id]

        config = {
            "group_id": group_id,
            "pixel_count": len(group.get("lights", 0)),
            "pixel_light_ids": group.get("lights", []),
            "refresh_rate": 30,
        }

        self.update_config(config)
