from ledfx.config import save_config
from ledfx.api import RestEndpoint
from ledfx.utils import generate_id
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class PresetsEndpoint(RestEndpoint):
    """REST end-point for querying and managing presets"""

    ENDPOINT_PATH = "/api/effects/{effect_id}/presets"

    async def get(self, effect_id) -> web.Response:
        """Get all presets for an effect"""
        response = {
            'status' : 'success' ,
            'presets' : self._ledfx.config['presets'][effect_id]
        }
        return web.Response(text=json.dumps(response), status=200)

    async def put(self, effect_id, request) -> web.Response:
        """Rename a preset"""
        data = await request.json()

        preset_id = data.get('preset_id')
        name = data.get('name')

        if effect_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "effect_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not effect_id in self._ledfx.config['presets'].keys():
            response = { 'status' : 'failed', 'reason': 'Effect {} does not exist'.format(preset_id) }
            return web.Response(text=json.dumps(response), status=500)

        if preset_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "preset_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not preset_id in self._ledfx.config['presets'][effect_id].keys():
            response = { 'status' : 'failed', 'reason': 'Preset {} does not exist for effect {}'.format(preset_id, effect_id) }
            return web.Response(text=json.dumps(response), status=500)

        if name is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "name" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        # Update and save config
        self._ledfx.config['presets'][effect_id][preset_id]['name'] = name
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)

    async def delete(self, effect_id, request) -> web.Response:
        """Delete a preset"""
        data = await request.json()
        preset_id = data.get('preset_id')

        if effect_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "effect_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not effect_id in self._ledfx.config['presets'].keys():
            response = { 'status' : 'failed', 'reason': 'Effect {} does not exist'.format(preset_id) }
            return web.Response(text=json.dumps(response), status=500)

        if preset_id is None:
            response = { 'status' : 'failed', 'reason': 'Required attribute "preset_id" was not provided' }
            return web.Response(text=json.dumps(response), status=500)

        if not preset_id in self._ledfx.config['presets'][effect_id].keys():
            response = { 'status' : 'failed', 'reason': 'Preset {} does not exist for effect {}'.format(preset_id, effect_id) }
            return web.Response(text=json.dumps(response), status=500)
        
        # Delete the preset from configuration
        del self._ledfx.config['presets'][effect_id][preset_id]

        # Save the config
        save_config(
            config = self._ledfx.config, 
            config_dir = self._ledfx.config_dir)

        response = { 'status' : 'success' }
        return web.Response(text=json.dumps(response), status=200)