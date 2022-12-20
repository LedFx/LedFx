# from ledfx.events import Event
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class QLCEndpoint(RestEndpoint):
    """REST end-point for querying and managing a Spotify integration"""

    ENDPOINT_PATH = "/api/integrations/spotify/{integration_id}"

    async def get(self, integration_id) -> web.Response:
        """Get all song triggers"""
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        response = integration.get_triggers()

        return web.json_response(data=response, status=200)

    async def put(self, integration_id, request) -> web.Response:
        """Update a Spotify song trigger"""
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        response = {
            "Ok": "This endpoint does nothing yet",
        }

        return web.json_response(data=response, status=200)

    async def post(self, integration_id, request) -> web.Response:
        """Add Spotify song trigger"""
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        scene_id = data.get("scene_id")
        song_id = data.get("song_id")
        song_name = data.get("song_name")
        song_position = data.get("song_position")

        if scene_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "scene_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if scene_id not in self._ledfx.config["scenes"].keys():
            response = {
                "status": "failed",
                "reason": f"Scene {scene_id} does not exist",
            }
            return web.json_response(data=response, status=400)

        if song_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "song_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        integration.add_trigger(scene_id, song_id, song_name, song_position)

        save_config(
            config=self._ledfx.config, config_dir=self._ledfx.config_dir
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)

    async def delete(self, integration_id, request) -> web.Response:
        """Delete a Spotify song trigger"""
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        trigger_id = data.get("trigger_id")

        if trigger_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "trigger_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        integration.delete_trigger(trigger_id)

        # Update and save the config
        save_config(
            config=self._ledfx.config, config_dir=self._ledfx.config_dir
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
