import logging

import pyaudio
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class AudioDevicesEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/audio/devices"

    _audio = None

    async def get(self) -> web.Response:
        """Get list of audio devices and active audio device WIP"""

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        audio_devices = {}
        audio_devices["devices"] = {}
        audio_config = self._ledfx.config.get(
            "audio", {"api_index": 0, "device_index": 0}
        )
        audio_devices["active_device_index"] = audio_config["device_index"]
        audio_devices["active_host_api"] = audio_config.get("host_api", 0)

        for apiIndex in range(self._audio.get_host_api_count()):
            info = self._audio.get_host_api_info_by_index(apiIndex)

            for i in range(0, info.get("deviceCount")):
                device_info = (
                    self._audio.get_device_info_by_host_api_device_index(
                        apiIndex, i
                    )
                )

                if (device_info.get("maxInputChannels")) > 0:
                    audio_devices["devices"][
                        device_info.get("index")
                    ] = device_info.get("name")

        return web.json_response(data=audio_devices, status=200)

    async def put(self, request) -> web.Response:
        """Set audio device to use as input"""
        data = await request.json()
        index = data.get("index")

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        if index is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "index" was not provided',
            }
            return web.json_response(data=response, status=500)

        try:
            deviceInfo = self._audio.get_device_info_by_index(index)
        except OSError:
            response = {
                "status": "failed",
                "reason": "Invalid device index [{}]".format(index),
            }
            return web.json_response(data=response, status=500)

        # Update and save config
        new_config = self._ledfx.config.get("audio", {})
        new_config["host_api"] = deviceInfo["hostApi"]
        new_config["device_name"] = deviceInfo["name"]
        new_config["device_index"] = int(index)

        if (deviceInfo["defaultSampleRate"]) > 44000.0:
            # if the sample rate is larger then 48000, we need to increase
            # the fft_size and mic_rate otherwise the pipline will not start
            new_config["mic_rate"] = mic = int(deviceInfo["defaultSampleRate"])
            min_size = int((mic / 44000.0) * 1024)
            new_config["fft_size"] = 1 << (min_size - 1).bit_length()

        self._ledfx.config["audio"] = new_config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        if self._ledfx.audio:
            self._ledfx.audio.update_config(new_config)

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
