import logging

import sounddevice as sd
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)

""" Work In Progress """


class AudioDevicesEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/audio/devicesv2"

    _audio = None

    async def get(self) -> web.Response:
        """Get list of audio devices and active audio device WIP"""

        if self._audio is None:
            self._audio = sd

        devices = self._audio.query_devices()
        input_devices = []
        for device in devices:
            if device["max_input_channels"] > 0:
                device["index"] = devices.index(device)
                input_devices += [device]

        audio_config = self._ledfx.config.get("audio", {"device_index": 0})

        audio_devices = {}
        audio_devices["devices"] = {}
        audio_devices["active_device_index"] = audio_config["device_index"]

        return web.json_response(data=input_devices, status=200)

    async def put(self, request) -> web.Response:
        """Set audio device to use as input"""
        data = await request.json()
        index = data.get("index")

        info = self._audio.get_host_api_info_by_index(0)
        if index is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "index" was not provided',
            }
            return web.json_response(data=response, status=500)

        if index not in range(0, info.get("deviceCount")):
            response = {
                "status": "failed",
                "reason": "Invalid device index [{}]".format(index),
            }
            return web.json_response(data=response, status=500)

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
