from ledfx.api import RestEndpoint
from aiohttp import web
import logging
import json
import aubio

_LOGGER = logging.getLogger(__name__)

class AudioDevicesEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/audio/devices"

    async def get(self) -> web.Response:
        """Get list of audio devices and active audio device"""
        info = self._ledfx.audio.get_host_api_info_by_index(0)

        audio_devices = {}
        audio_devices['active_device_index'] = self._ledfx.audio.config['device_index']
        audio_devices['devices'] = {}
        for i in range(0, info.get('deviceCount')):
            if (self._ledfx._audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                audio_devices['devices'][i] = self._ledfx._audio.get_device_info_by_host_api_device_index(0, i).get('name')

        return web.Response(text=json.dumps(audio_devices), status=200)

    async def put(self, request) -> web.Response:
        """Set audio device to use as input. Requires restart for changes to take effect"""
        data = await request.json()
        index = data.get('index')

        info = self._ledfx._audio.get_host_api_info_by_index(0)
        if index is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "index" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if index not in range(0, info.get('deviceCount')):
            response = { 'status' : 'failed', 'reason': 'Invalid device index [{}]'.format(index) }
            return web.Response(text=json.dumps(response), status=500)

        # Update and save config
        self._ledfx.config['audio']['device_index'] = int(index)
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status': 'success' }
        return web.Response(text=json.dumps(response), status=200)
