from ledfx.config import save_config
from ledfx.api import RestEndpoint
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/devices/{device_id}/effects"

    async def get(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = { 'not found': 404 }
            return web.Response(text=json.dumps(response), status=404)

        # Get the active effect
        response = { 'effect' : {}}
        if device.active_effect:
            effect_response = {}
            effect_response['config'] = device.active_effect.config
            effect_response['name'] = device.active_effect.name
            effect_response['type'] = device.active_effect.type
            response = { 'effect' : effect_response }

        return web.Response(text=json.dumps(response), status=200)

    async def put(self, device_id, request) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = { 'not found': 404 }
            return web.Response(text=json.dumps(response), status=404)

        data = await request.json()
        effect_type = data.get('type')
        if effect_type is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "type" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        effect_config = data.get('config')
        if effect_config is None:
            effect_config = {}

        # Create the effect and add it to the device
        effect = self._ledfx.effects.create(
            ledfx = self._ledfx,
            type = effect_type,
            config = effect_config)
        device.set_effect(effect)

        # Update and save the configuration
        for device in self._ledfx.config['devices']:
            if (device['id'] == device_id):
                #if not ('effect' in device):
                device['effect'] = {}
                device['effect']['type'] = effect_type
                device['effect']['config'] = effect_config
                break
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        effect_response = {}
        effect_response['config'] = effect.config
        effect_response['name'] = effect.name
        effect_response['type'] = effect.type

        response = { 'status' : 'success', 'effect' : effect_response}
        return web.Response(text=json.dumps(response), status=200)

    async def post(self, device_id, request) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = { 'not found': 404 }
            return web.Response(text=json.dumps(response), status=404)

        data = await request.json()
        effect_type = data.get('type')
        if effect_type is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "type" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        effect_config = data.get('config')
        if effect_config is None:
            effect_config = {}

        # Create the effect and add it to the device
        effect = self._ledfx.effects.create(
            ledfx = self._ledfx,
            type = effect_type,
            config = effect_config)
        device.set_effect(effect)

        # Update and save the configuration
        for device in self._ledfx.config['devices']:
            if (device['id'] == device_id):
                #if not ('effect' in device):
                device['effect'] = {}
                device['effect']['type'] = effect_type
                device['effect']['config'] = effect_config
                break
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        effect_response = {}
        effect_response['config'] = effect.config
        effect_response['name'] = effect.name
        effect_response['type'] = effect.type

        response = { 'status' : 'success', 'effect' : effect_response}
        return web.Response(text=json.dumps(response), status=200)

    async def delete(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = { 'not found': 404 }
            return web.Response(text=json.dumps(response), status=404)

        # Clear the effect
        device.clear_effect()

        for device in self._ledfx.config['devices']:
            if (device['id'] == device_id):
                del device['effect']
                break
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success', 'effect' : {} }
        return web.Response(text=json.dumps(response), status=200)