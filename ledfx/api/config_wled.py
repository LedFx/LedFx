import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import convertToJsonSchema
from ledfx.config import (
    WLED_CONFIG_SCHEMA,
    _default_wled_settings,
    save_config,
)

_LOGGER = logging.getLogger(__name__)


class WLEDConfigEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/config/wled"

    PERMITTED_KEYS = list(_default_wled_settings.keys())

    async def get(self) -> web.Response:
        response = {
            "config": convertToJsonSchema(WLED_CONFIG_SCHEMA),
            "permitted_keys": self.PERMITTED_KEYS,
        }

        return web.json_response(data=response, status=200)

    async def delete(self) -> web.Response:
        self._ledfx.config["melbanks"] = {}

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Audio config reset to default",
            },
        }

        return web.json_response(data={"status": "success"}, status=200)

    async def put(self, request) -> web.Response:

        try:
            config = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        if not config:
            response = {
                "status": "failed",
                "reason": "No config attributes were provided",
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
            validated_config = WLED_CONFIG_SCHEMA(config)
        except vol.MultipleInvalid as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        new_valid_config = {
            key: validated_config[key] for key in config.keys()
        }

        self._ledfx.config["wled_preferences"] |= new_valid_config

        # DO SOMETHING WITH THE NEW WLED SETTINGS
        # if hasattr(self._ledfx, "audio"):
        #     self._ledfx.audio.melbanks.update_config(
        #         self._ledfx.config["melbanks"]
        #     )

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data={"status": "success"}, status=200)
