import logging

import sounddevice as sd
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)

""" Work In Progress """


class AudioDevicesEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/audio/devices"

    _audio = None

    async def get(self) -> web.Response:
        """Get list of audio devices using sound device"""
        # Need to map out what host API actually means - however for now, just display it
        if self._audio is None:
            self._audio = sd
        hostapis = self._audio.query_hostapis()

        devices = self._audio.query_devices()
        input_devices = []
        for device in devices:
            if device["max_input_channels"] > 0:
                device["index"] = devices.index(device)
                input_devices += [device]

        audio_config = self._ledfx.config.get("audio", {"device_index": 0})
        input_device_count = len(input_devices)

        audio_devices = {}
        audio_devices["devices"] = {}
        audio_devices["active_device_index"] = audio_config["device_index"]
        for i in range(0, input_device_count):
            audio_devices["devices"][i] = (
                input_devices[i]["name"]
                + " using host API : "
                + str(input_devices[i]["hostapi"])
            )
        return web.json_response(data=audio_devices, status=200)

    async def put(self, request) -> web.Response:
        """Set audio device to use as input"""
        data = await request.json()
        index = data.get("index")

        devices = self._audio.query_devices()
        input_devices = []
        for device in devices:
            if device["max_input_channels"] > 0:
                device["index"] = devices.index(device)
                input_devices += [device]

        if index is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "index" was not provided',
            }
            return web.json_response(data=response, status=500)

        if index not in range(0, len(input_devices)):
            response = {
                "status": "failed",
                "reason": f"Invalid device index [{index}]",
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
