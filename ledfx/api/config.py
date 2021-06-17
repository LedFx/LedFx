import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import convertToJsonSchema
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
        "visualisation_fps",
        "visualisation_maxlen",
    ]

    async def get(self) -> web.Response:
        response = {
            "config": self._ledfx.config,
            "schema": convertToJsonSchema(CORE_CONFIG_SCHEMA),
            "permitted_keys": self.PERMITTED_KEYS,
        }

        return web.json_response(data=response, status=200)

    async def delete(self) -> web.Response:
        self._ledfx.config = CORE_CONFIG_SCHEMA({})

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Config reset to default values",
            },
        }

        # This is an ugly hack.
        # We probably should have a better way of doing this but o well.
        try:
            return web.json_response(data={"status": "success"}, status=200)
        finally:
            self._ledfx.stop(4)

    async def post(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        try:
            validated_config = CORE_CONFIG_SCHEMA(data)
        except vol.MultipleInvalid as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        self._ledfx.config = validated_config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        # This is an ugly hack.
        # We probably should have a better way of doing this but o well.
        try:
            return web.json_response(data={"status": "success"}, status=200)
        finally:
            self._ledfx.stop(4)

    async def put(self, request) -> web.Response:
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

        # handle special validation for wled_preferences
        if "wled_preferences" in config.keys():
            new_valid_wled_config = {
                key: validated_config["wled_preferences"][key]
                for key in config["wled_preferences"].keys()
            }
            for key, value in new_valid_wled_config.items():
                self._ledfx.config["wled_preferences"][key] |= value
            del new_valid_config["wled_preferences"]

        self._ledfx.config |= new_valid_config

        # should restart ledfx at this point or smth

        if "wled_preferred_mode" in new_valid_config.keys():
            mode = new_valid_config["wled_preferences"]["wled_preferred_mode"][
                "setting"
            ]
            if mode:
                await self._ledfx.devices.set_wleds_sync_mode(mode)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data={"status": "success"}, status=200)
