import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.events import SceneSetEvent
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class ScenesEndpoint(RestEndpoint):
    """REST end-point for querying and managing scenes"""

    ENDPOINT_PATH = "/api/scenes"

    async def get(self) -> web.Response:
        """Get all scenes"""
        response = {
            "status": "success",
            "scenes": self._ledfx.config["scenes"],
        }
        return web.json_response(data=response, status=200)

    async def delete(self, request) -> web.Response:
        """Delete a scene"""
        data = await request.json()

        scene_id = data.get("id")
        if scene_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "scene_id" was not provided',
            }
            return web.json_response(data=response, status=500)

        if scene_id not in self._ledfx.config["scenes"].keys():
            response = {
                "status": "failed",
                "reason": "Scene {} does not exist".format(scene_id),
            }
            return web.json_response(data=response, status=500)

        # Delete the scene from configuration
        del self._ledfx.config["scenes"][scene_id]

        # Save the config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        """Activate a scene"""
        data = await request.json()

        action = data.get("action")
        if action is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "action" was not provided',
            }
            return web.json_response(data=response, status=500)

        if action not in ["activate", "rename"]:
            response = {
                "status": "failed",
                "reason": 'Invalid action "{}"'.format(action),
            }
            return web.json_response(data=response, status=500)

        scene_id = data.get("id")
        if scene_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "scene_id" was not provided',
            }
            return web.json_response(data=response, status=500)

        if scene_id not in self._ledfx.config["scenes"].keys():
            response = {
                "status": "failed",
                "reason": 'Scene "{}" does not exist'.format(scene_id),
            }
            return web.json_response(data=response, status=500)

        scene = self._ledfx.config["scenes"][scene_id]

        if action == "activate":
            for display in self._ledfx.displays.values():
                # Check display is in scene, make no changes if it isn't
                if display.id not in scene["displays"].keys():
                    _LOGGER.info(
                        ("display with id {} has no data in scene {}").format(
                            display.id, scene_id
                        )
                    )
                    continue

                # Set effect of display to that saved in the scene,
                # clear active effect of display if no effect in scene
                if scene["displays"][display.id]:
                    # Create the effect and add it to the display
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=scene["displays"][display.id]["type"],
                        config=scene["displays"][display.id]["config"],
                    )
                    display.set_effect(effect)
                else:
                    display.clear_effect()

            self._ledfx.events.fire_event(SceneSetEvent(scene["name"]))
            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": f"Activated scene {scene['name']}",
                },
            }

        elif action == "rename":
            name = data.get("name")
            if name is None:
                response = {
                    "status": "failed",
                    "reason": 'Required attribute "name" was not provided',
                }
                return web.json_response(data=response, status=500)

            # Update and save config
            self._ledfx.config["scenes"][scene_id]["name"] = name
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": f"Renamed scene to {name}",
                },
            }
        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """Save current effects of displays as a scene"""
        data = await request.json()

        scene_name = data.get("name")
        if scene_name is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "scene_name" was not provided',
            }
            return web.json_response(data=response, status=500)

        scene_id = generate_id(scene_name)

        scene_config = {}
        scene_config["name"] = scene_name
        scene_config["displays"] = {}
        for display in self._ledfx.displays.values():
            effect = {}
            if display.active_effect:
                effect["type"] = display.active_effect.type
                effect["config"] = display.active_effect.config
                # effect['name'] = display.active_effect.name
            scene_config["displays"][display.id] = effect

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
        return web.json_response(data=response, status=200)
