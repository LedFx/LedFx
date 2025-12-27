import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import find_matching_preset, save_config
from ledfx.effects import DummyEffect
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class ScenesEndpoint(RestEndpoint):
    """REST end-point for querying and managing scenes"""

    ENDPOINT_PATH = "/api/scenes"

    async def get(self) -> web.Response:
        """
        Get all scenes with preset detection.

        Returns:
            web.Response: The response containing the scenes.
        """
        scenes_with_state = {}
        for scene_id, scene_config in self._ledfx.config["scenes"].items():
            scene_payload = dict(scene_config)
            scene_payload["active"] = self._ledfx.scenes.is_active(scene_id)

            # Add preset matching for each virtual's effect
            if "virtuals" in scene_payload:
                virtuals_with_presets = {}
                for virtual_id, effect_data in scene_payload[
                    "virtuals"
                ].items():
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

            scenes_with_state[scene_id] = scene_payload

        response = {
            "status": "success",
            "scenes": scenes_with_state,
        }
        return await self.bare_request_success(response)

    async def delete(self, request: web.Request) -> web.Response:
        """Delete a scene"""
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        scene_id = generate_id(data.get("id"))
        if scene_id is None:
            return await self.invalid_request(
                'Required attribute "id" was not provided'
            )

        if scene_id not in self._ledfx.config["scenes"].keys():
            error_message = f"Scene {scene_id} does not exist"
            _LOGGER.warning(error_message)
            return await self.invalid_request()

        # Delete the scene from configuration
        del self._ledfx.config["scenes"][scene_id]

        # Save the config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()

    async def put(self, request: web.Request) -> web.Response:
        """Activate a scene

        Args:
            request (web.Request): The request containing the scene `id` and `action`.

        Returns:
            web.Response: The HTTP response object.

        """

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        action = data.get("action")
        if action is None:
            return await self.invalid_request(
                'Required attribute "action" was not provided'
            )

        if action not in ["activate", "activate_in", "deactivate", "rename"]:
            return await self.invalid_request(f'Invalid action "{action}"')

        scene_id = generate_id(data.get("id"))
        if scene_id is None:
            return await self.invalid_request(
                'Required attribute "id" was not provided'
            )

        if scene_id not in self._ledfx.config["scenes"].keys():
            return await self.invalid_request(
                f"Scene {scene_id} does not exist"
            )

        scene = self._ledfx.config["scenes"][scene_id]

        if action == "activate_in":
            ms = data.get("ms")
            if ms is None:
                return await self.invalid_request(
                    'Required attribute "ms" was not provided'
                )
            self._ledfx.loop.call_later(
                ms, self._ledfx.scenes.activate, scene_id
            )
            return await self.request_success(
                "info", f"Scene {scene['name']} will activate in {ms}ms"
            )

        if action == "activate":
            activated = self._ledfx.scenes.activate(scene_id)
            if not activated:
                return await self.invalid_request(
                    f"Scene {scene_id} could not be activated"
                )
            return await self.request_success(
                "info", f"Activated {scene['name']}"
            )
        elif action == "deactivate":
            deactivated = self._ledfx.scenes.deactivate(scene_id)
            if not deactivated:
                return await self.invalid_request(
                    f"Scene {scene_id} could not be deactivated"
                )
            return await self.request_success(
                "info", f"Deactivated {scene['name']}"
            )

        elif action == "rename":
            name = data.get("name")
            if name is None:
                return await self.invalid_request(
                    'Required attribute "name" was not provided'
                )

            # Update and save config
            self._ledfx.config["scenes"][scene_id]["name"] = name
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
            return await self.request_success(
                "info", f"Renamed {scene['name']} to {name}"
            )

    async def post(self, request: web.Request) -> web.Response:
        """
        Save current effects of virtuals as a scene.

        Args:
            request (web.Request): The request object containing `name`, `scene_tags`, `scene_puturl`, `scene_payload`, `scene_midiactivate` (optional), `scene_image` (optinal), and `virtuals` (optional).

        Returns:
            web.Response: The HTTP response object.
        """

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        scene_name = data.get("name")
        scene_tags = data.get("scene_tags")
        scene_puturl = data.get("scene_puturl")
        scene_payload = data.get("scene_payload")
        scene_midiactivate = data.get("scene_midiactivate")
        scene_image = data.get("scene_image")
        scene_snapshot = data.get("snapshot", False)
        scene_id = data.get("id")

        # Determine operation: update if ID provided, create if not
        if scene_id:
            # ID provided - must be an update
            sanitized_id = generate_id(scene_id)
            if sanitized_id not in self._ledfx.config["scenes"].keys():
                error_message = f"Scene with id '{scene_id}' does not exist. To create a new scene, omit the 'id' field."
                _LOGGER.warning(error_message)
                return await self.invalid_request(error_message)
            is_update = True
        else:
            # No ID - create operation, name is required
            if scene_name is None or scene_name == "":
                error_message = "Required attribute 'name' was not provided"
                _LOGGER.warning(error_message)
                return await self.invalid_request(error_message)
            is_update = False

        if is_update:
            # Update existing scene - sanitize scene_id and preserve existing config
            scene_id = generate_id(scene_id)
            scene_config = dict(self._ledfx.config["scenes"][scene_id])

            # Only update fields that were explicitly provided
            if scene_name is not None:
                scene_config["name"] = scene_name
            if scene_tags is not None:
                scene_config["scene_tags"] = scene_tags
            if scene_puturl is not None:
                scene_config["scene_puturl"] = scene_puturl
            if scene_payload is not None:
                scene_config["scene_payload"] = scene_payload
            if scene_midiactivate is not None:
                scene_config["scene_midiactivate"] = scene_midiactivate
            if scene_image is not None:
                scene_config["scene_image"] = scene_image
        else:
            # Create new scene - generate deduped ID and build fresh config
            dupe_id = generate_id(scene_name)
            dupe_index = 1
            scene_id = dupe_id
            while scene_id in self._ledfx.config["scenes"].keys():
                scene_id = f"{dupe_id}-{dupe_index}"
                dupe_index = dupe_index + 1

            if scene_image is None:
                scene_image = "Wallpaper"

            if data.get("virtuals") is None:
                scene_snapshot = True

            scene_config = {
                "name": scene_name,
                "virtuals": {},
                "scene_image": scene_image,
                "scene_puturl": scene_puturl,
                "scene_tags": scene_tags,
                "scene_payload": scene_payload,
                "scene_midiactivate": scene_midiactivate,
            }

        # handle virtuals
        # if not a snapshot replace with provided, or keep existing
        # if a snapshot grab current
        if not scene_snapshot:
            if data.get("virtuals") is None:
                # preserve existing virtuals if none provided
                pass
            else:
                scene_config["virtuals"] = {}
                virtuals = data.get("virtuals")

                for virtualid in virtuals:
                    virtual_data = virtuals[virtualid]
                    if not isinstance(virtual_data, dict):
                        continue

                    # Preserve the entire virtual config including action field
                    virtual_config = {}

                    # Copy action field if present
                    if "action" in virtual_data:
                        virtual_config["action"] = virtual_data["action"]

                    # Copy type and config if present (for activate action or legacy)
                    if "type" in virtual_data:
                        virtual_config["type"] = virtual_data["type"]
                    if "config" in virtual_data:
                        virtual_config["config"] = virtual_data["config"]

                    # Copy preset if present (for activate action with preset)
                    # Only save preset if type is also present (preset requires type)
                    if "preset" in virtual_data:
                        if "type" in virtual_data:
                            virtual_config["preset"] = virtual_data["preset"]
                        else:
                            _LOGGER.warning(
                                f"Virtual '{virtualid}' has 'preset' field but missing required 'type' field. "
                                "Preset field will not be saved."
                            )

                    scene_config["virtuals"][virtualid] = virtual_config
        else:
            # Force a snapshot of current virtual effects
            scene_config["virtuals"] = {}
            for virtual in self._ledfx.virtuals.values():
                effect = {}
                if virtual.active_effect:
                    # prevent crash from trying to save copy / span transitions
                    # which appear active even when the virtual is not!!!
                    if not isinstance(virtual.active_effect, DummyEffect):
                        effect["type"] = virtual.active_effect.type
                        effect["config"] = virtual.active_effect.config
                    else:
                        _LOGGER.debug(
                            f"Skipping DummyEffect for virtual {virtual.id}"
                        )
                scene_config["virtuals"][virtual.id] = effect

        # Update the scene if it already exists, else create it
        self._ledfx.config["scenes"][scene_id] = scene_config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "scene": {"id": scene_id, "config": scene_config},
        }
        return await self.bare_request_success(response)
