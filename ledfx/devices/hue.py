import logging
import re
import socket
import time
from typing import Dict, Optional, Tuple

import requests
import voluptuous as vol

# Try to import the optional package
try:
    import mbedtls.tls as tls

    MBEDTLS_AVAILABLE = True
except ImportError:
    MBEDTLS_AVAILABLE = False

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
            vol.Required(
                "group_name",
                description="Entertainment zone group name",
            ): str,
            vol.Optional("udp_port", description="port", default=2100): int,
        }
    )

    status: Dict[int, Tuple[int, int, int]]
    _sock: Optional[socket.socket] = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        if not MBEDTLS_AVAILABLE:
            raise Exception(
                "You need to install the python-mbedtls package for Hue to work."
            )

        if "hue_application_id" in self._config:
            # since this is present the init gets called because the device is already known
            self._dtls_client_context = tls.ClientContext(
                tls.DTLSConfiguration(
                    pre_shared_key=(
                        self._config["hue_application_id"],
                        bytes.fromhex(self._config["clientkey"]),
                    ),
                    ciphers=["TLS-PSK-WITH-AES-128-GCM-SHA256"],
                    validate_certificates=False,
                )
            )
        else:
            # The device gets setup for the first time.
            # We call these functions here so the device does only get added if they both succeed!
            # If we won't do that then the device would already be added and a second try wouldn't work
            # until "ledfx" is restartet.
            # But this can't be called if the device is already setup since it would block and the event loop
            # would throw an error. In this case this would get executed in the "async_initialize"
            self._hue_register()
            self._check_hue_bridge()

        self.status = {}

    def _hue_register(self):
        if (self._config.get("username") is None) and (
            self._config.get("clientkey") is None
        ):
            # We need to register this device as application at the Hue Bridge.
            request_data = {
                "devicetype": f"LedFx#{self._config['group_name']}",
                "generateclientkey": True,
            }
            response, _ = self._hue_request("POST", "api", request_data)
            if "success" in response[0]:
                # We successfully registerd
                clientdata = response[0]["success"]
                self.update_config(
                    {
                        "username": clientdata["username"],
                        "clientkey": clientdata["clientkey"],
                    }
                )
            else:
                # The Bridge Link Button needs to be pressed
                raise Exception(
                    "You need to press the Bridge Link Button and retry that again."
                )
        else:
            # We need to check if the credentials are still valid for this device.
            response, _ = self._hue_request(
                "GET", f"api/{self._config['username']}"
            )
            if "error" in response[0]:
                # Credentials are no longer valid - need Bridge Link Button to be pressed and LedFx to be restarted.
                # We delete the invalid credentials here - after a restart a fresh registration will be tried.
                self.update_config({"username": None, "clientkey": None})
                raise Exception(
                    "You need to press the Bridge Link Button and restart LedFx."
                )

    def _check_hue_bridge(self):
        response, _ = self._hue_request("GET", "api/config")
        if response["swversion"] < "1948086000":
            raise Exception(
                "Your Hue Bridge has an outdated Firmware installed. Update it using the Hue App."
            )

    def _hue_request(self, method, api_endpoint, data=None, ssl=False):
        url = f"{'https' if ssl else 'http'}://{self._config['ip_address']}/{api_endpoint}"

        headers = {"hue-application-key": self._config.get("username")}

        # SSL is somehow necessary for some Hue requests but we need to skip the verification since there are no valid certs
        response = getattr(requests, method.lower())(
            url, json=data, verify=not ssl, headers=headers
        )

        return response.json(), response.headers

    def _entertainment_groups(self):
        response, _ = self._hue_request(
            "GET", "/clip/v2/resource/entertainment_configuration", ssl=True
        )

        all_groups = response["data"]
        entertainmentZonesCount = len(all_groups)

        if entertainmentZonesCount == 0:
            raise Exception(
                "You did not setup any Entertainment zones. Do that in the Hue App."
            )

        return {group["id"]: group for group in all_groups}

    def _lights_from_entertainment_group(self, entertainment_id):
        response, _ = self._hue_request(
            "GET",
            f"/clip/v2/resource/entertainment_configuration/{entertainment_id}",
            ssl=True,
        )
        lights = dict()
        for channel in response["data"][0]["channels"]:
            lights.update(
                {
                    str(channel["channel_id"]): [
                        channel["position"]["x"],
                        channel["position"]["y"],
                        channel["position"]["z"],
                    ]
                }
            )

        if len(lights) > 20:
            raise Exception(
                f"{len(lights)} lights found. Only 20 are allowed."
            )

        return lights

    def _get_application_id(self):
        _, headers = self._hue_request("GET", "/auth/v1", ssl=True)
        return headers.get("hue-application-id")

    def activate(self):
        # activate streaming for entertainment zone
        request_data = {"action": "start"}
        self._hue_request(
            "PUT",
            f"/clip/v2/resource/entertainment_configuration/{self._config['entertainment_id']}",
            request_data,
            ssl=True,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.setblocking(False)
        self._sock = self._dtls_client_context.wrap_socket(
            sock, self._config["ip_address"]
        )
        self._sock.connect(
            (self._config["ip_address"], self._config["udp_port"])
        )

        # Since UDP packets can get lost - we need to try handshaking a couple of times
        handshake_success = False
        for _ in range(10):
            try:
                time.sleep(0.2)
                self._sock.do_handshake()
                handshake_success = True
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to establish TLS handshake when activating the UDP stream. Retrying. {e}"
                )

        if not handshake_success:
            raise Exception(
                "Could not connect to the Bridge. Disconnect and reconnect it from power."
            )

        super().activate()

    def deactivate(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

        request_data = {"action": "stop"}
        response, _ = self._hue_request(
            "PUT",
            f"/clip/v2/resource/entertainment_configuration/{self._config['entertainment_id']}",
            request_data,
            ssl=True,
        )

        super().deactivate()

    def flush(self, data):
        # TODO: maybe use the position of the channel to make more sense of the effect

        pixels = [[int(r), int(g), int(b)] for r, g, b in data]
        send_data = bytearray(b"HueStream")
        send_data.append(2)  # Major version
        send_data.append(0)  # Minor version
        send_data.append(0)  # Sequence ID
        send_data.append(0)  # Reserved
        send_data.append(0)  # Reserved
        send_data.append(0)  # Color Mode (0=RGB, 1=XY)
        send_data.append(0)  # Reserved
        send_data.extend(self._config["entertainment_id"].encode("utf-8"))
        for i in range(len(pixels)):
            send_data.append(i)  # channel ID
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

        # see "self.__init__" why we do this.
        if "hue_application_id" in self._config:
            self._hue_register()
            self._check_hue_bridge()
            hue_application_id = self._config["hue_application_id"]
        else:
            hue_application_id = self._get_application_id()
            self._dtls_client_context = tls.ClientContext(
                tls.DTLSConfiguration(
                    pre_shared_key=(
                        hue_application_id,
                        bytes.fromhex(self._config["clientkey"]),
                    ),
                    ciphers=["TLS-PSK-WITH-AES-128-GCM-SHA256"],
                )
            )

        entertainment_groups = self._entertainment_groups()
        entertainment_id = next(
            id
            for id in entertainment_groups
            if entertainment_groups[id].get("name", "").lower()
            == self._config.get("group_name", "").lower()
        )
        entertainment_group = entertainment_groups[entertainment_id]
        group_id = re.findall(r"\d+", entertainment_group["id_v1"])[0]

        lights = self._lights_from_entertainment_group(entertainment_id)

        config = {
            "group_id": group_id,
            "entertainment_id": entertainment_id,
            "hue_application_id": hue_application_id,
            "pixel_count": len(lights),
            "pixel_lights": lights,  # currently not used but could be used to make better effects respecting the position
            "refresh_rate": 30,
        }

        self.update_config(config)
