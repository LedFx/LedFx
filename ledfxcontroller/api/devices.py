from ledfxcontroller.config import save_config
from ledfxcontroller.api import RestEndpoint
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class DevicesEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices"

    def __init__(self, ledfx):
        super().__init__(ledfx)

    async def get(self) -> web.Response:
        response = { 'status' : 'success' , 'devices' : {}}
        for device in self.ledfx.devices.values():
            response['devices'][device.id] = {"name": device.name}

        return web.Response(text=json.dumps(response), status=200)

    async def put(self, request) -> web.Response:
        data = await request.json()

        device_config = data.get('config')
        if device_config is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "config" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        # Create the device
        _LOGGER.info("Adding device with config", device_config)
        device = self.ledfx.devices.create(
            config = device_config,
            name = device_config.get('type'))

        # Update and save the configuration
        self.ledfx.config['devices'][device.id] = device_config
        save_config(
            config = self.ledfx.config, 
            config_dir = self.ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)

    async def delete(self, request) -> web.Response:
        data = await request.json()
        device_id = data.get('id')

        if device_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        # Remove the device
        _LOGGER.info(("Removing device with id {}").format(device_id))
        self.ledfx.devices.destroy(device_id)

        # Update and save the configuration
        del self.ledfx.config['devices'][device_id]
        save_config(
            config = self.ledfx.config, 
            config_dir = self.ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)