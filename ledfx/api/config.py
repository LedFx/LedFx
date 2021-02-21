import logging

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class ConfigEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/config"

    PERMITTED_KEYS = [
        "host",
        "port",
        "dev_mode",
        "wled_preferred_mode",
        "scan_on_startup",
    ]

    async def get(self) -> web.Response:
        response = {"config": self._ledfx.config}

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        data = await request.json()

        config = data.get("config")
        if config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=500)

        for key in config.keys():
            if key not in self.PERMITTED_KEYS:
                response = {
                    "status": "failed",
                    "reason": f"Unknown/forbidden config key: '{key}'",
                }
                return web.json_response(data=response, status=500)

        try:
            validated_config = self._ledfx.config.CORE_CONFIG_SCHEMA(config)
        except vol.MultipleInvalid as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        self._ledfx.config |= validated_config

        # should restart ledfx at this point

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
