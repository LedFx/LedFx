import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import CORE_CONFIG_SCHEMA, save_config

_LOGGER = logging.getLogger(__name__)


class ConfigEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/config"

    PERMITTED_KEYS = [
        "host",
        "port",
        "dev_mode",
        "wled_preferences",
        "scan_on_startup",
    ]

    async def get(self) -> web.Response:
        response = {"config": self._ledfx.config}

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        config = data.get("config")
        if config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=400)

        for key in config.keys():
            if key not in self.PERMITTED_KEYS:
                response = {
                    "status": "failed",
                    "reason": f"Unknown/forbidden config key: '{key}'",
                }
                return web.json_response(data=response, status=400)

        try:
            validated_config = CORE_CONFIG_SCHEMA(config)
        except vol.MultipleInvalid as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        new_valid_config = {
            key: validated_config[key] for key in config.keys()
        }
        self._ledfx.config |= new_valid_config

        # should restart ledfx at this point or smth

        if "wled_preferred_mode" in new_valid_config.keys():
            mode = new_valid_config["wled_preferences"]["wled_preferred_mode"]
            if mode:
                await self._ledfx.devices.set_wleds_sync_mode(mode)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data={"status": "success"}, status=200)
