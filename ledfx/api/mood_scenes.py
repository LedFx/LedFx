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
from typing import Any, Optional

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

    def _validate_scene_exists(self, scene_id: str) -> bool:
        """
        Validate that a scene exists.

        Args:
            scene_id: The scene ID to validate

        Returns:
            True if scene exists, False otherwise
        """
        if not scene_id or not isinstance(scene_id, str):
            return False

        if not hasattr(self._ledfx, "scenes") or self._ledfx.scenes is None:
            return False

        return self._ledfx.scenes.get(scene_id) is not None

    async def _validate_and_filter_mappings(
        self, mappings: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate scene references in mappings and filter out invalid ones.

        Args:
            mappings: Dictionary of mappings to validate

        Returns:
            Filtered dictionary with only valid scene references
        """
        filtered = {}
        for key, scene_id in mappings.items():
            if self._validate_scene_exists(scene_id):
                filtered[key] = scene_id
            else:
                _LOGGER.warning(
                    f"Scene '{scene_id}' referenced in mapping '{key}' does not exist, skipping"
                )
        return filtered

    async def get(self, _request: web.Request) -> web.Response:
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

            # Get mappings using protected config access
            mood_scenes = await mood_manager._get_config("mood_scenes", {})
            event_scenes = await mood_manager._get_config("event_scenes", {})

            # Validate and filter mappings to ensure all referenced scenes exist
            validated_mood_scenes = await self._validate_and_filter_mappings(
                mood_scenes if isinstance(mood_scenes, dict) else {}
            )
            validated_event_scenes = await self._validate_and_filter_mappings(
                event_scenes if isinstance(event_scenes, dict) else {}
            )

            mappings = {
                "mood_scenes": validated_mood_scenes,
                "event_scenes": validated_event_scenes,
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

            # Validate type and emptiness
            if not isinstance(mapping_type, str) or not mapping_type:
                return await self.invalid_request(
                    "Field 'type' must be a non-empty string"
                )
            if mapping_type not in ["mood", "event", "structure"]:
                return await self.invalid_request(
                    f"Invalid mapping type: {mapping_type}. Must be one of: mood, event, structure"
                )
            if not isinstance(key, str) or not key:
                return await self.invalid_request(
                    "Field 'key' must be a non-empty string"
                )
            if not isinstance(scene_id, str) or not scene_id:
                return await self.invalid_request(
                    "Field 'scene_id' must be a non-empty string"
                )

            # Validate scene exists using helper method
            if not self._validate_scene_exists(scene_id):
                return await self.invalid_request(
                    f"Scene '{scene_id}' does not exist"
                )

            # Add mapping using protected config access
            if mapping_type == "mood":
                mood_scenes = await mood_manager._get_config("mood_scenes", {})
                if not isinstance(mood_scenes, dict):
                    mood_scenes = {}
                mood_scenes[key] = scene_id
                await mood_manager._update_config({"mood_scenes": mood_scenes})

            elif mapping_type == "event":
                event_scenes = await mood_manager._get_config(
                    "event_scenes", {}
                )
                if not isinstance(event_scenes, dict):
                    event_scenes = {}
                event_scenes[key] = scene_id
                await mood_manager._update_config(
                    {"event_scenes": event_scenes}
                )

            elif mapping_type == "structure":
                # Structure mappings need "structure_" prefix for lookup
                event_scenes = await mood_manager._get_config(
                    "event_scenes", {}
                )
                if not isinstance(event_scenes, dict):
                    event_scenes = {}
                structure_key = f"structure_{key}"
                event_scenes[structure_key] = scene_id
                await mood_manager._update_config(
                    {"event_scenes": event_scenes}
                )

            else:
                return await self.invalid_request(
                    f"Invalid mapping type: {mapping_type}"
                )

            # Save configuration - get updated config copy
            config_copy = await mood_manager._get_config_copy()

            # Update LedFx config structure (integrations is a list, not a dict)
            if "integrations" not in self._ledfx.config:
                self._ledfx.config["integrations"] = []

            # Find existing mood_manager integration in the list
            mood_manager_config = None
            for integration in self._ledfx.config["integrations"]:
                if (
                    integration.get("type") == "mood_manager"
                    or integration.get("id") == "mood_manager"
                ):
                    mood_manager_config = integration
                    break

            # Update or create the integration config entry
            if mood_manager_config:
                cfg = mood_manager_config.get("config")
                if not isinstance(cfg, dict):
                    cfg = {}
                    mood_manager_config["config"] = cfg
                cfg.update(config_copy)
                mood_manager_config["active"] = getattr(
                    mood_manager, "_active", True
                )
            else:
                # Create new integration entry
                self._ledfx.config["integrations"].append(
                    {
                        "id": "mood_manager",
                        "type": "mood_manager",
                        "active": mood_manager._active,
                        "config": config_copy,
                    }
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

            # Remove mapping using protected config access
            removed = False
            if mapping_type == "mood":
                mood_scenes = await mood_manager._get_config("mood_scenes", {})
                if isinstance(mood_scenes, dict) and key in mood_scenes:
                    del mood_scenes[key]
                    await mood_manager._update_config(
                        {"mood_scenes": mood_scenes}
                    )
                    removed = True

            elif mapping_type == "event":
                event_scenes = await mood_manager._get_config(
                    "event_scenes", {}
                )
                if isinstance(event_scenes, dict) and key in event_scenes:
                    del event_scenes[key]
                    await mood_manager._update_config(
                        {"event_scenes": event_scenes}
                    )
                    removed = True

            elif mapping_type == "structure":
                # Structure mappings use "structure_" prefix
                event_scenes = await mood_manager._get_config(
                    "event_scenes", {}
                )
                structure_key = f"structure_{key}"
                if (
                    isinstance(event_scenes, dict)
                    and structure_key in event_scenes
                ):
                    del event_scenes[structure_key]
                    await mood_manager._update_config(
                        {"event_scenes": event_scenes}
                    )
                    removed = True

            if not removed:
                return await self.invalid_request(
                    f"Mapping not found: {mapping_type}/{key}"
                )

            # Save configuration - get updated config copy
            config_copy = await mood_manager._get_config_copy()

            # Update LedFx config structure
            if "integrations" not in self._ledfx.config:
                self._ledfx.config["integrations"] = []

            # Find existing mood_manager integration in the list
            mood_manager_config = None
            for integration in self._ledfx.config["integrations"]:
                if (
                    integration.get("type") == "mood_manager"
                    or integration.get("id") == "mood_manager"
                ):
                    mood_manager_config = integration
                    break

            # Update or create the integration config entry
            if mood_manager_config:
                cfg = mood_manager_config.get("config")
                if not isinstance(cfg, dict):
                    cfg = {}
                    mood_manager_config["config"] = cfg
                cfg.update(config_copy)
                mood_manager_config["active"] = getattr(
                    mood_manager, "_active", True
                )
            else:
                # Create new integration entry
                self._ledfx.config["integrations"].append(
                    {
                        "id": "mood_manager",
                        "type": "mood_manager",
                        "active": mood_manager._active,
                        "config": config_copy,
                    }
                )

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
