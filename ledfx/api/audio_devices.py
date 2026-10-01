import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.configuration.models import AudioInputConfig, validate_dict
from ledfx.effects.audio import AudioInputSource

_LOGGER = logging.getLogger(__name__)

""" Work In Progress """


class AudioDevicesEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/audio/devices"

    _audio = None

    async def get(self) -> web.Response:
        """
        Get list of audio devices using sound device

        Returns:
            web.Response: The response containing the list of audio devices and the active device index.
        """
        audio_config = validate_dict(
            AudioInputConfig, self._ledfx.config.audio.model_dump(), runtime=True
        )

        response = {}
        response["active_device_index"] = audio_config["audio_device"]
        response["active_device_name"] = audio_config.get("audio_device_name", "")
        response["devices"] = (
            AudioInputSource.input_devices()
        )  # dict(enumerate(input_devices))
        return await self.bare_request_success(response)

    async def put(self, request: web.Request) -> web.Response:
        """
        Set audio device to use as input.

        Args:
            request (web.Request): The request object containing the new device `index`.

        Returns:
            web.Response: The HTTP response object.

        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        index = data.get("audio_device")
        if index is None:
            return await self.invalid_request(
                "Required attribute 'index' was not provided"
            )

        valid_indexes = AudioInputSource.valid_device_indexes()

        if index not in valid_indexes:
            return await self.invalid_request(f"Invalid device index [{index}]")

        # Update and save config
        # When user explicitly selects a new device via API, replace any stale
        # stored name with the current name for that selected index. This keeps
        # the live selection consistent now and preserves boot-time name-based
        # recovery if indices drift before the next restart.
        cfg = self._ledfx.config
        cfg.audio = cfg.audio.model_copy(
            update={
                "audio_device": int(index),
                "audio_device_name": AudioInputSource.input_devices().get(
                    int(index), ""
                ),
            }
        )

        if self._ledfx.audio:
            self._ledfx.audio.update_config(cfg.audio.model_dump())

        self._ledfx.config_store.request_save()

        return await self.request_success()
