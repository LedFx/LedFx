import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.scenes import scene_payload
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class SceneEndpoint(RestEndpoint):
    """REST end-point for querying and deleting a single scene"""

    ENDPOINT_PATH = "/api/scenes/{scene_id}"

    async def get(self, scene_id) -> web.Response:
        """
        Get a single scene by ID.

        Args:
            scene_id (str): The scene ID from the URL path.

        Returns:
            web.Response: The response containing the scene.
        """
        scene_id = generate_id(scene_id)

        if scene_id not in self._ledfx.config.scenes:
            return await self.invalid_request(f"Scene {scene_id} does not exist")

        scene = self._ledfx.config.scenes[scene_id]
        payload = scene_payload(self._ledfx, scene_id, scene)

        response = {
            "status": "success",
            "scene": {
                "id": scene_id,
                "config": payload,
            },
        }
        return await self.bare_request_success(response)

    async def delete(self, scene_id) -> web.Response:
        """
        Delete a scene by ID (RESTful endpoint).

        Args:
            scene_id (str): The scene ID from the URL path.

        Returns:
            web.Response: The response indicating success or failure.
        """
        scene_id = generate_id(scene_id)

        if scene_id not in self._ledfx.config.scenes:
            return await self.invalid_request("Scene not found")

        # Delete the scene from configuration
        self._ledfx.scenes.cancel_pending(scene_id)
        del self._ledfx.config.scenes[scene_id]

        # Save the config
        self._ledfx.config_store.request_save()

        return await self.request_success(
            type="success", message=f"Scene '{scene_id}' deleted."
        )
