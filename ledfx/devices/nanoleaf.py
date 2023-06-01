import logging
import socket
import struct
from typing import Dict, Optional, Tuple

import requests
import voluptuous as vol

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)

LightPanelModel = "NL22"
CanvasModel = "NL29"


class NanoleafDevice(NetworkedDevice):
    """
    Dedicated Nanoleaf device support
    This class fetches its config (px count, etc) from the Nanoleaf device
    at launch, and lets the user choose a sync mode to use.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "ip_address",
                description="Hostname or IP address of the device",
            ): str,
            vol.Optional("port", description="port", default=16021): int,
            vol.Optional("udp_port", description="port", default=60222): int,
            vol.Optional(
                "auth_token",
                description="Auth token",
            ): str,
            vol.Optional(
                "sync_mode",
                description="Streaming protocol to Nanoleaf device",
                default="UDP",
            ): vol.In(["TCP", "UDP"]),
        }
    )

    status: Dict[int, Tuple[int, int, int]]
    _sock: Optional[socket.socket] = None

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.status = {}

    def config_updated(self, config):
        self.setup_subdevice()

    def url(self, token: str) -> str:
        return "http://%s:%i/api/v1/%s" % (
            self._config["ip_address"],
            self._config["port"],
            token,
        )

    def setup_subdevice(self):
        _LOGGER.debug("setup_subdevice")
        self.status = {}
        self.deactivate()
        self.activate()

    def activate(self):
        if self.config["sync_mode"] == "UDP":
            _LOGGER.info("Activating UDP stream mode...")
            payload = {
                "write": {
                    "command": "display",
                    "animType": "extControl",
                    "extControlVersion": "v2",
                }
            }
            if self._config["model"] == LightPanelModel:
                payload["write"]["extControlVersion"] = "v1"

            response = requests.put(
                self.url(self._config["auth_token"]) + "/effects",
                json=payload,
            )

            if response.status_code == 400:
                raise Exception("Invalid effect dictionary")

            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.connect(
                (self._config["ip_address"], self._config["udp_port"])
            )

        super().activate()

    def deactivate(self):
        _LOGGER.debug("deactivate")
        if self._sock is not None:
            self._sock.close()
            self._sock = None

        super().deactivate()

    def write_udp(self):
        if self._config["model"] == LightPanelModel:
            send_data = struct.pack(">B", len(self.status.items()))
            w = 0
            transition = 1

            for panel_id, (r, g, b) in self.status.items():
                send_data += struct.pack(
                    ">BBBBBH", panel_id, w, r, g, b, transition
                )
        else:
            send_data = struct.pack(">H", len(self.status))
            w = 0
            transition = 0

            for panel_id, (r, g, b) in self.status.items():
                send_data += struct.pack(
                    ">HBBBBH", panel_id, r, g, b, w, transition
                )

        self._sock.send(send_data)

    def write_tcp(self):
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
            self.config["pixel_layout"], data.astype(int).clip(0, 255)
        ):
            self.status[panel["panelId"]] = col.tolist()

        if self.config["sync_mode"] == "TCP":
            self.write_tcp()
        elif self.config["sync_mode"] == "UDP":
            self.write_udp()

    def get_token(self):
        _LOGGER.info("acquiring nanoleaf auth token...")
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

        _LOGGER.info("fetching nanoleaf's device info...")

        nanoleaf_config = requests.get(
            self.url(self.config["auth_token"])
        ).json()

        _LOGGER.debug(f"nanoleaf config response: {nanoleaf_config}")
        _LOGGER.info("parsing panel layout...")

        panels = [
            {"x": i["x"], "y": i["y"], "panelId": i["panelId"]}
            for i in sorted(
                nanoleaf_config["panelLayout"]["layout"]["positionData"],
                key=lambda panel: (panel["x"], panel["y"]),
            )
            if i["panelId"] != 0
        ]

        config = {
            "name": nanoleaf_config["name"],
            "pixel_count": len(panels),
            "pixel_layout": panels,
            "refresh_rate": 30,  # problems with too fast udp packets
            "model": nanoleaf_config["model"],
        }

        if nanoleaf_config["model"] == LightPanelModel:
            config["udp_port"] = 60221

        self.setup_subdevice()

        self.update_config(config)
