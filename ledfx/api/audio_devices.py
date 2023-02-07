import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.effects.audio import AudioInputSource

_LOGGER = logging.getLogger(__name__)

""" Work In Progress """


class AudioDevicesEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/audio/devices"

    _audio = None

    async def get(self) -> web.Response:
        """Get list of audio devices using sound device"""

        audio_config = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()(
            self._ledfx.config.get("audio", {})
        )

        response = {}
        response["active_device_index"] = audio_config["device_index"]
        response[
            "devices"
        ] = AudioInputSource.input_devices()  # dict(enumerate(input_devices))

        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        """Set audio device to use as input"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        index = data.get("index")
        if index is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "index" was not provided',
            }
            return web.json_response(data=response, status=400)

        valid_indexes = AudioInputSource.valid_device_indexes()

        if index not in valid_indexes:
            response = {
                "status": "failed",
                "reason": f"Invalid device index [{index}]",
            }
            return web.json_response(data=response, status=400)

        # Update and save config
        new_config = self._ledfx.config.get("audio", {})
        new_config["device_index"] = int(index)
        self._ledfx.config["audio"] = new_config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        if self._ledfx.audio:
            self._ledfx.audio.update_config(new_config)

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
