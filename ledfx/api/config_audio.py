import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import convertToJsonSchema
from ledfx.config import save_config
from ledfx.effects.audio import AudioInputSource

_LOGGER = logging.getLogger(__name__)


class AudioConfigEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/config/audio"

    PERMITTED_KEYS = [
        "min_volume",
        "device_index",
    ]

    async def get(self) -> web.Response:
        response = {
            "config": convertToJsonSchema(
                AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
            ),
            "permitted_keys": self.PERMITTED_KEYS,
        }

        return web.json_response(data=response, status=200)

    async def delete(self) -> web.Response:
        self._ledfx.config["audio"] = {}

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
            validated_config = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()(
                config
            )
        except vol.MultipleInvalid as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        new_valid_config = {
            key: validated_config[key] for key in config.keys()
        }

        self._ledfx.config["audio"] |= new_valid_config

        if hasattr(self._ledfx, "audio"):
            self._ledfx.audio.update_config(self._ledfx.config["audio"])

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return web.json_response(data={"status": "success"}, status=200)
