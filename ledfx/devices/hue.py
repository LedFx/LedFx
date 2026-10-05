import logging
import re
import socket
import time

import requests
from ledfx_senders.encoders import encode_hue

# Try to import the optional package
try:
    from mbedtls import tls

    MBEDTLS_AVAILABLE = True
except ImportError:
    MBEDTLS_AVAILABLE = False

from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class HueDevice(NetworkedDevice):
    """
    Philips Hue device support (Entertainment Mode UDP streaming)
    """

    class Config(NetworkedDevice.Config):
        ip_address: str = Field(
            description="Hostname or IP address of the Hue bridge",
            json_schema_extra={X_REQUIRED: True},
        )
        group_name: str = Field(
            description="Entertainment zone group name",
            json_schema_extra={X_REQUIRED: True},
        )
        udp_port: int = Field(2100, description="port")

    config = TypedConfig(Config)

    status: dict[int, tuple[int, int, int]]
    _sock: socket.socket | None = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Hue"
        if not MBEDTLS_AVAILABLE:
            raise Exception(  # noqa: TRY002
                "You need to install the python-mbedtls package for Hue to work."
            )

        if hasattr(self.config, "hue_application_id"):
            # since this is present the init gets called because the device is already known
            self._dtls_client_context = tls.ClientContext(
                tls.DTLSConfiguration(
                    pre_shared_key=(
                        getattr(self.config, "hue_application_id"),  # noqa: B009 - stored extra, not a declared field
                        bytes.fromhex(getattr(self.config, "clientkey")),  # noqa: B009 - stored extra, not a declared field
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
        if (getattr(self.config, "username", None) is None) and (
            getattr(self.config, "clientkey", None) is None
        ):
            # We need to register this device as application at the Hue Bridge.
            request_data = {
                "devicetype": f"LedFx#{self.config.group_name}",
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
                raise Exception(  # noqa: TRY002
                    "You need to press the Bridge Link Button and retry that again."
                )
        else:
            # We need to check if the credentials are still valid for this device.
            username = getattr(self.config, "username")  # noqa: B009 - stored extra, not a declared field
            response, _ = self._hue_request("GET", f"api/{username}")
            if "error" in response[0]:
                # Credentials are no longer valid - need Bridge Link Button to be pressed and LedFx to be restarted.
                # We delete the invalid credentials here - after a restart a fresh registration will be tried.
                self.update_config({"username": None, "clientkey": None})
                raise Exception(  # noqa: TRY002
                    "You need to press the Bridge Link Button and restart LedFx."
                )

    def _check_hue_bridge(self):
        response, _ = self._hue_request("GET", "api/config")
        if response["swversion"] < "1948086000":
            raise Exception(  # noqa: TRY002
                "Your Hue Bridge has an outdated Firmware installed. Update it using the Hue App."
            )

    def _hue_request(self, method, api_endpoint, data=None, ssl=False):
        url = f"{'https' if ssl else 'http'}://{self.config.ip_address}/{api_endpoint}"

        headers = {"hue-application-key": getattr(self.config, "username", None)}

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
            raise Exception(  # noqa: TRY002
                "You did not setup any Entertainment zones. Do that in the Hue App."
            )

        return {group["id"]: group for group in all_groups}

    def _lights_from_entertainment_group(self, entertainment_id):
        response, _ = self._hue_request(
            "GET",
            f"/clip/v2/resource/entertainment_configuration/{entertainment_id}",
            ssl=True,
        )
        lights = dict()  # noqa: C408
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
            raise Exception(f"{len(lights)} lights found. Only 20 are allowed.")  # noqa: TRY002

        return lights

    def _get_application_id(self):
        _, headers = self._hue_request("GET", "/auth/v1", ssl=True)
        return headers.get("hue-application-id")

    def activate(self):
        # activate streaming for entertainment zone
        request_data = {"action": "start"}
        self._hue_request(
            "PUT",
            f"/clip/v2/resource/entertainment_configuration/{getattr(self.config, 'entertainment_id')}",  # noqa: B009 - stored extra, not a declared field
            request_data,
            ssl=True,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.setblocking(False)
        self._sock = self._dtls_client_context.wrap_socket(sock, self.config.ip_address)
        self._sock.connect((self.config.ip_address, self.config.udp_port))

        # Since UDP packets can get lost - we need to try handshaking a couple of times
        handshake_success = False
        for _ in range(10):
            try:
                time.sleep(0.2)
                self._sock.do_handshake()
                handshake_success = True
                break
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to establish TLS handshake when activating the UDP stream. Retrying. %s",
                    e,
                )

        if not handshake_success:
            _LOGGER.warning(
                "Could not connect to the Bridge. Disconnect and reconnect it from power."
            )

        super().activate()

    def deactivate(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

        request_data = {"action": "stop"}
        response, _ = self._hue_request(  # noqa: RUF059
            "PUT",
            f"/clip/v2/resource/entertainment_configuration/{getattr(self.config, 'entertainment_id')}",  # noqa: B009 - stored extra, not a declared field
            request_data,
            ssl=True,
        )

        super().deactivate()

    def flush(self, data):
        # TODO: maybe use the position of the channel to make more sense of the effect

        send_data = encode_hue(
            data,
            getattr(self.config, "entertainment_id"),  # noqa: B009 - stored extra
            tuple(range(len(data))),
            0,
        )

        try:
            self._sock.send(send_data)
        except Exception:  # noqa: BLE001
            self.activate()

    async def async_initialize(self):
        await super().async_initialize()

        # see "self.__init__" why we do this.
        if hasattr(self.config, "hue_application_id"):
            self._hue_register()
            self._check_hue_bridge()
            hue_application_id = getattr(self.config, "hue_application_id")  # noqa: B009 - stored extra, not a declared field
        else:
            hue_application_id = self._get_application_id()
            self._dtls_client_context = tls.ClientContext(
                tls.DTLSConfiguration(
                    pre_shared_key=(
                        hue_application_id,
                        bytes.fromhex(getattr(self.config, "clientkey")),  # noqa: B009 - stored extra, not a declared field
                    ),
                    ciphers=["TLS-PSK-WITH-AES-128-GCM-SHA256"],
                )
            )

        entertainment_groups = self._entertainment_groups()
        entertainment_id = next(
            id
            for id in entertainment_groups
            if entertainment_groups[id].get("name", "").lower()
            == self.config.group_name.lower()
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
