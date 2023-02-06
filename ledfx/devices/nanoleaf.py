import logging
from typing import Dict, Tuple

import requests
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class NanoleafDevice(NetworkedDevice):
    """
    Dedicated WLED device support
    This class fetches its config (px count, etc) from the WLED device
    at launch, and lets the user choose a sync mode to use.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Optional("port", description="port", default=16021): int,
            vol.Optional(
                "auth_token",
                description="Auth token",
            ): str,
        }
    )

    status: Dict[int, Tuple[int, int, int]]

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)

        self.status = {}

        # moved DEVICE_CONFIGS class var to device_configs instance var as it is manipulated in seperate instances
        # see https://github.com/LedFx/LedFx/pull/237
        self.device_configs = {
            "TCP": {
                "name": None,
                "ip_address": None,
                "auth_token": None,
                "port": 16021,
            }
        }

    def config_updated(self, config):
        self.setup_subdevice()

    def url(self, token: str) -> str:
        return "http://%s:%i/api/v1/%s" % (
            self._config["ip_address"],
            self._config["port"],
            token,
        )

    def setup_subdevice(self):
        self.status = {}

        # nl = Nanoleaf(self._config["ip_address"], self.config["auth_token"])
        # ndt = NanoleafDigitalTwin(nl)
        # ndt.sync()

    # def activate(self):
    #     super().activate()
    #
    # def deactivate(self):
    #     super().deactivate()

    def write(self):
        """Syncs the digital twin's changes to the real Nanoleaf device.

        :returns: True if success, otherwise False
        """
        anim_data = str(len(self.status))

        for key, (r, g, b) in self.status.items():
            anim_data += f" {str(key)} 1 {r} {g} {b} 0 0"

        response = requests.put(
            self.url(self._config["auth_token"]) + "/effects",
            json={
                "write": {
                    "command": "display",
                    "animType": "custom",
                    "loop": True,
                    "palette": [],
                    "animData": anim_data,
                }
            },
        )
        if response.status_code == 400:
            raise Exception("Invalid effect dictionary")

    def flush(self, data):
        for panel, col in zip(
            self.config["pixel_layout"], data.astype(int).clip(None, 255)
        ):
            self.status[panel["panelId"]] = col.tolist()
        self.write()

    def get_token(self):
        response = requests.post(self.url("new"))

        if response and response.status_code == 200:
            data = response.json()
            if "auth_token" in data:
                return data["auth_token"]

        raise Exception("No token, press sync button first")

    async def async_initialize(self):
        await super().async_initialize()

        auth_token = self.config.get("auth_token")

        if not auth_token:
            auth_token = self.get_token()
            self.update_config({"auth_token": auth_token})

        self.setup_subdevice()

        nanoleaf_config = requests.get(
            self.url(self.config["auth_token"])
        ).json()

        panels = [
            {"x": i["x"], "y": i["y"], "panelId": i["panelId"]}
            for i in sorted(
                nanoleaf_config["panelLayout"]["layout"]["positionData"],
                key=lambda x: (x["x"], x["y"]),
            )
            if i["panelId"] != 0
        ]

        config = {
            "name": nanoleaf_config["name"],
            "pixel_count": len(panels),
            "pixel_layout": panels,
        }

        self.update_config(config)
