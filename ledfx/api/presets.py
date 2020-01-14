from ledfx.config import save_config
from ledfx.api import RestEndpoint
from ledfx.utils import generate_id
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class PresetsEndpoint(RestEndpoint):
    """REST end-point for querying and managing presets"""

    ENDPOINT_PATH = "/api/presets"

    async def get(self) -> web.Response:
        """Get all presets"""
        response = {
            'status' : 'success' ,
            'presets' : self._ledfx.config['presets'] 
        }
        return web.Response(text=json.dumps(response), status=200)

    async def delete(self, request) -> web.Response:
        """Delete a preset"""
        data = await request.json()

        preset_id = data.get('id')
        if preset_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "preset_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not preset_id in self._ledfx.config['presets'].keys():
            response = { 'status' : 'failed', 'reason': 'Preset {} does not exist'.format(preset_id) }
            return web.Response(text=json.dumps(response), status=500)
        
        # Delete the preset from configuration
        del self._ledfx.config['presets'][preset_id]

        # Save the config
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)

    async def put(self, request) -> web.Response:
        """Activate a preset"""
        data = await request.json()

        action = data.get('action')
        if action is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "action" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if action not in ['activate', 'rename']:
            response = { 'status' : 'failed', 'reason': 'Invalid action "{}"'.format(action) }
            return web.Response(text=json.dumps(response), status=500)

        preset_id = data.get('id')
        if preset_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "preset_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not preset_id in self._ledfx.config['presets'].keys():
            response = { 'status' : 'failed', 'reason': 'Preset "{}" does not exist'.format(preset_id) }
            return web.Response(text=json.dumps(response), status=500)

        preset = self._ledfx.config['presets'][preset_id]

        if action == "activate":
            for device in self._ledfx.devices.values():
                # Check device is in preset, make no changes if it isn't
                if not device.id in preset['devices'].keys():
                    _LOGGER.info(('Device with id {} has no data in preset {}').format(device.id, preset_id))
                    continue

                # Set effect of device to that saved in the preset,
                # clear active effect of device if no effect in preset
                if preset['devices'][device.id]:
                    # Create the effect and add it to the device
                    effect = self._ledfx.effects.create(
                        ledfx = self._ledfx,
                        type = preset['devices'][device.id]['type'],
                        config = preset['devices'][device.id]['config'])
                    device.set_effect(effect)
                else:
                    device.clear_effect()

        elif action == "rename":
            name = data.get('name')
            if name is None:
                response = { 'status' : 'failed', 'reason': 'Required attribute "name" was not provided' }
                return web.Response(text=json.dumps(response), status=500)

            # Update and save config
            self._ledfx.config['presets'][preset_id]['name'] = name
            save_config(
                config = self._ledfx.config, 
                config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)

    async def post(self, request) -> web.Response:
        """Save current effects of devices as a preset"""
        data = await request.json()

        preset_name = data.get('name')
        if preset_name is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "preset_name" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        preset_id = generate_id(preset_name)

        preset_config = {}
        preset_config['name'] = preset_name
        preset_config['devices'] = {}
        for device in self._ledfx.devices.values():
            effect = {}
            if device.active_effect:
                effect['type'] = device.active_effect.type
                effect['config'] = device.active_effect.config
                #effect['name'] = device.active_effect.name
            preset_config['devices'][device.id] = effect

        # Update the preset if it already exists, else create it
        self._ledfx.config['presets'][preset_id] = preset_config 

        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success', 'preset': {'id': preset_id, 'config': preset_config }}
        return web.Response(text=json.dumps(response), status=200)