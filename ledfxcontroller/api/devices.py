from ledfxcontroller.config import save_config
from ledfxcontroller.api import RestEndpoint
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class DevicesEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices"

    async def get(self) -> web.Response:
        response = { 'status' : 'success' , 'devices' : {}}
        for device in self.ledfx.devices.values():
            response['devices'][device.id] = device.config

        return web.Response(text=json.dumps(response), status=200)

    async def put(self, request) -> web.Response:
        data = await request.json()

        device_config = data.get('config')
        if device_config is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "config" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        device_id = data.get('id')
        if device_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        # Remove the device it if already exist
        try:
            self.ledfx.devices.destroy(device_id)
        except AttributeError:
            pass

        # Create the device
        _LOGGER.info("Adding device with config", device_config)
        device = self.ledfx.devices.create(
            config = device_config,
            id = device_id,
            name = device_config.get('type'))

        # Update and save the configuration
        self.ledfx.config['devices'][device.id] = device_config
        save_config(
            config = self.ledfx.config, 
            config_dir = self.ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)