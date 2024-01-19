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
        """
        Get all song triggers

        Args:
            integration_id (str): The ID of the integration

        Returns:
            web.Response: The response containing the song triggers

        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            return await self.invalid_request(
                f"{integration} was not found or was not type spotify"
            )

        response = integration.get_triggers()
        return await self.bare_request_success(response)

    async def put(self, integration_id, request) -> web.Response:
        """
        Update a Spotify song trigger

        Args:
            integration_id (str): The ID of the Spotify integration
            request (web.Request): The request object. Not currently used.

        Returns:
            web.Response: The response object

        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            return await self.invalid_request(
                f"{integration} was not found or was not type spotify"
            )

        return await self.request_success(
            "info", "This endpoint does nothing yet"
        )

    async def post(self, integration_id, request) -> web.Response:
        """
        Add Spotify song trigger

        Args:
            integration_id (str): The ID of the Spotify integration.
            request (web.Request): The HTTP request object containing `scene_id`, `song_id`, `song_name`, and `song_position`.

        Returns:
            web.Response: The HTTP response object.
        """
        if integration_id is None:
            return await self.invalid_request(
                'Required attribute "integration_id" was not provided'
            )
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            return await self.invalid_request(
                f"{integration} was not found or was not type spotify"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        scene_id = data.get("scene_id")
        song_id = data.get("song_id")
        song_name = data.get("song_name")
        song_position = data.get("song_position")
        missing_attributes = []
        if scene_id is None:
            missing_attributes.append("scene_id")
        if song_id is None:
            missing_attributes.append("song_id")
        if song_name is None:
            missing_attributes.append("song_name")
        if song_position is None:
            missing_attributes.append("song_position")
        if missing_attributes:
            return await self.invalid_request(
                f'Required attributes {", ".join(missing_attributes)} were not provided'
            )

        if scene_id not in self._ledfx.config["scenes"].keys():
            return await self.invalid_request(
                f"Scene {scene_id} does not exist"
            )

        integration.add_trigger(scene_id, song_id, song_name, song_position)

        save_config(
            config=self._ledfx.config, config_dir=self._ledfx.config_dir
        )
        return await self.request_success()

    async def delete(self, integration_id, request) -> web.Response:
        """Delete a Spotify song trigger

        Args:
            integration_id (str): The ID of the integration.
            request (web.Request): The request object containing `trigger_id`.

        Returns:
            web.Response: The response object.
        """
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "spotify"):
            return await self.invalid_request(
                f"{integration} was not found or was not type spotify"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        trigger_id = data.get("trigger_id")

        if trigger_id is None:
            return await self.invalid_request(
                'Required attribute "trigger_id" was not provided'
            )

        integration.delete_trigger(trigger_id)

        # Update and save the config
        save_config(
            config=self._ledfx.config, config_dir=self._ledfx.config_dir
        )
        return await self.request_success()
