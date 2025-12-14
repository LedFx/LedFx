"""
API endpoints for managing mood-to-scene mappings.

Provides REST API endpoints for:
- Getting current mood scene mappings
- Adding/updating mood scene mappings
- Removing mood scene mappings

Supports three types of mappings:
- mood: Maps mood categories to scenes
- event: Maps structural events to scenes
- structure: Maps music sections to scenes
"""

import logging
from json import JSONDecodeError
from typing import Any, Dict, Optional

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class MoodScenesEndpoint(RestEndpoint):
    """
    REST API endpoint for managing mood-to-scene mappings.

    GET /api/mood/scenes - Get current mood scene mappings
    POST /api/mood/scenes - Add/update mood scene mapping
    DELETE /api/mood/scenes - Remove mood scene mapping
    """

    ENDPOINT_PATH = "/api/mood/scenes"

    async def get(self, request: web.Request) -> web.Response:
        """
        Get current mood scene mappings.

        Returns:
            {
                "status": "success",
                "mappings": {
                    "mood_scenes": {
                        "energetic_bright": "scene_id_1",
                        ...
                    },
                    "event_scenes": {
                        "beat_drop": "scene_id_2",
                        ...
                    }
                }
            }
        """
        try:
            mood_manager = self._get_mood_manager()

            if mood_manager is None:
                return await self.invalid_request(
                    "Mood manager integration not available"
                )

            mappings = {
                "mood_scenes": mood_manager._config.get("mood_scenes", {}),
                "event_scenes": mood_manager._config.get("event_scenes", {}),
            }

            return await self.bare_request_success({"mappings": mappings})

        except Exception as e:
            _LOGGER.error(f"Error getting mood scenes: {e}", exc_info=True)
            return await self.internal_error(str(e))

    def _get_mood_manager(self) -> Optional[Any]:
        """
        Helper method to get mood manager integration.

        Returns:
            MoodManager instance or None if not found
        """
        if not hasattr(self._ledfx, "integrations"):
            return None

        # Try to get by ID first
        mood_manager = self._ledfx.integrations.get("mood_manager")
        if mood_manager is not None:
            return mood_manager

        # Find by type
        for integration in self._ledfx.integrations.values():
            if (
                hasattr(integration, "type")
                and integration.type == "mood_manager"
            ):
                return integration
            if (
                hasattr(integration, "NAME")
                and integration.NAME == "mood_manager"
            ):
                return integration

        return None

    async def post(self, request: web.Request) -> web.Response:
        """
        Add or update a mood scene mapping.

        Request body:
            {
                "type": "mood" | "event" | "structure",
                "key": str,  # mood category, event name, or structure name
                "scene_id": str
            }

        Returns:
            {
                "status": "success",
                "message": "Mood scene mapping added"
            }
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        try:
            mood_manager = self._get_mood_manager()

            if mood_manager is None:
                return await self.invalid_request(
                    "Mood manager integration not available"
                )

            # Validate required fields
            if (
                "type" not in data
                or "key" not in data
                or "scene_id" not in data
            ):
                return await self.invalid_request(
                    "Required fields: type, key, scene_id"
                )

            mapping_type = data["type"]
            key = data["key"]
            scene_id = data["scene_id"]

            # Validate scene exists
            if hasattr(self._ledfx, "scenes"):
                if not self._ledfx.scenes.get(scene_id):
                    return await self.invalid_request(
                        f"Scene '{scene_id}' does not exist"
                    )

            # Add mapping
            if mapping_type == "mood":
                if "mood_scenes" not in mood_manager._config:
                    mood_manager._config["mood_scenes"] = {}
                mood_manager._config["mood_scenes"][key] = scene_id

            elif mapping_type in ["event", "structure"]:
                if "event_scenes" not in mood_manager._config:
                    mood_manager._config["event_scenes"] = {}
                mood_manager._config["event_scenes"][key] = scene_id

            else:
                return await self.invalid_request(
                    f"Invalid mapping type: {mapping_type}"
                )

            # Save configuration
            if not hasattr(self._ledfx.config, "integrations"):
                self._ledfx.config["integrations"] = {}

            if "mood_manager" not in self._ledfx.config["integrations"]:
                self._ledfx.config["integrations"]["mood_manager"] = {}

            self._ledfx.config["integrations"]["mood_manager"].update(
                mood_manager._config
            )

            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

            return await self.request_success(
                "success", f"Mood scene mapping added: {key} -> {scene_id}"
            )

        except Exception as e:
            _LOGGER.error(
                f"Error adding mood scene mapping: {e}", exc_info=True
            )
            return await self.internal_error(str(e))

    async def delete(self, request: web.Request) -> web.Response:
        """
        Remove a mood scene mapping.

        Request body:
            {
                "type": "mood" | "event" | "structure",
                "key": str
            }

        Returns:
            {
                "status": "success",
                "message": "Mood scene mapping removed"
            }
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        try:
            mood_manager = self._get_mood_manager()

            if mood_manager is None:
                return await self.invalid_request(
                    "Mood manager integration not available"
                )

            # Validate required fields
            if "type" not in data or "key" not in data:
                return await self.invalid_request("Required fields: type, key")

            mapping_type = data["type"]
            key = data["key"]

            # Remove mapping
            removed = False
            if mapping_type == "mood":
                if key in mood_manager._config.get("mood_scenes", {}):
                    del mood_manager._config["mood_scenes"][key]
                    removed = True

            elif mapping_type in ["event", "structure"]:
                if key in mood_manager._config.get("event_scenes", {}):
                    del mood_manager._config["event_scenes"][key]
                    removed = True

            if not removed:
                return await self.invalid_request(
                    f"Mapping not found: {mapping_type}/{key}"
                )

            # Save configuration
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

            return await self.request_success(
                "success", f"Mood scene mapping removed: {key}"
            )

        except Exception as e:
            _LOGGER.error(
                f"Error removing mood scene mapping: {e}", exc_info=True
            )
            return await self.internal_error(str(e))
