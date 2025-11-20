import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import find_matching_preset, save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class SceneEndpoint(RestEndpoint):
    """REST end-point for querying and deleting a single scene"""

    ENDPOINT_PATH = "/api/scenes/{scene_id}"

    async def get(self, scene_id: str) -> web.Response:
        """
        Get a single scene by ID.

        Args:
            scene_id (str): The scene ID to retrieve.

        Returns:
            web.Response: The response containing the scene.
        """
        scene_id = generate_id(scene_id)

        if scene_id not in self._ledfx.config["scenes"]:
            return await self.invalid_request(
                f"Scene {scene_id} does not exist"
            )

        scene_config = self._ledfx.config["scenes"][scene_id]
        scene_payload = dict(scene_config)
        scene_payload["active"] = self._ledfx.scenes.is_active(scene_id)

        # Add preset matching for each virtual's effect
        if "virtuals" in scene_payload:
            virtuals_with_presets = {}
            for virtual_id, effect_data in scene_payload["virtuals"].items():
                virtual_payload = dict(effect_data)
                if (
                    "type" in effect_data
                    and "config" in effect_data
                    and effect_data["config"]
                ):
                    effect_type = effect_data["type"]
                    effect_config = effect_data["config"]
                    preset_id, category = find_matching_preset(
                        self._ledfx.config["ledfx_presets"],
                        self._ledfx.config["user_presets"],
                        self._ledfx.effects,
                        effect_type,
                        effect_config,
                    )
                    if preset_id:
                        virtual_payload["preset"] = preset_id
                        virtual_payload["preset_category"] = category
                virtuals_with_presets[virtual_id] = virtual_payload
            scene_payload["virtuals"] = virtuals_with_presets

        response = {
            "status": "success",
            "scene": {
                "id": scene_id,
                "config": scene_payload,
            },
        }
        return await self.bare_request_success(response)

    async def delete(self, scene_id: str) -> web.Response:
        """
        Delete a scene by ID (RESTful endpoint).

        Args:
            scene_id (str): The scene ID to delete.

        Returns:
            web.Response: The response indicating success or failure.
        """
        scene_id = generate_id(scene_id)

        if scene_id not in self._ledfx.config["scenes"]:
            return await self.invalid_request("Scene not found")

        # Delete the scene from configuration
        del self._ledfx.config["scenes"][scene_id]

        # Save the config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return await self.request_success(
            type="success", message=f"Scene '{scene_id}' deleted."
        )
