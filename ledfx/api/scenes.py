import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.events import SceneActivatedEvent
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
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        scene_id = data.get("id")
        if scene_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if scene_id not in self._ledfx.config["scenes"].keys():
            response = {
                "status": "failed",
                "reason": f"Scene {scene_id} does not exist",
            }
            return web.json_response(data=response, status=400)

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
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        action = data.get("action")
        if action is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "action" was not provided',
            }
            return web.json_response(data=response, status=400)

        if action not in ["activate", "activate_in", "deactivate", "rename"]:
            response = {
                "status": "failed",
                "reason": f'Invalid action "{action}"',
            }
            return web.json_response(data=response, status=400)

        scene_id = data.get("id")
        if scene_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if scene_id not in self._ledfx.config["scenes"].keys():
            response = {
                "status": "failed",
                "reason": f'Scene "{scene_id}" does not exist',
            }
            return web.json_response(data=response, status=400)

        scene = self._ledfx.config["scenes"][scene_id]

        if action == "activate_in":
            ms = data.get("ms")
            if ms is None:
                response = {
                    "status": "failed",
                    "reason": 'Required attribute "ms" was not provided',
                }
                return web.json_response(data=response, status=400)
            self._ledfx.loop.call_later(
                ms, self._ledfx.scenes.activate, scene_id
            )
            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": f"Activated scene {scene['name']}",
                },
            }
            return web.json_response(data=response, status=200)

        if action == "activate":
            for virtual in self._ledfx.virtuals.values():
                # Check virtual is in scene, make no changes if it isn't
                if virtual.id not in scene["virtuals"].keys():
                    # _LOGGER.info(
                    #     ("virtual with id {} has no data in scene {}").format(
                    #         virtual.id, scene_id
                    #     )
                    # )
                    continue

                # Set effect of virtual to that saved in the scene,
                # clear active effect of virtual if no effect in scene
                if scene["virtuals"][virtual.id]:
                    # Create the effect and add it to the virtual
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=scene["virtuals"][virtual.id]["type"],
                        config=scene["virtuals"][virtual.id]["config"],
                    )
                    virtual.set_effect(effect)
                else:
                    virtual.clear_effect()

            self._ledfx.events.fire_event(SceneActivatedEvent(scene_id))
            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": f"Activated scene {scene['name']}",
                },
            }

        elif action == "deactivate":
            for virtual in self._ledfx.virtuals.values():
                # Check virtual is in scene, make no changes if it isn't
                if virtual.id not in scene["virtuals"].keys():
                    _LOGGER.info(
                        ("virtual with id {} has no data in scene {}").format(
                            virtual.id, scene_id
                        )
                    )
                    continue

                # Clear the effect of virtual,
                if scene["virtuals"][virtual.id]:
                    virtual.clear_effect()

            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": f"Deactivated scene {scene['name']}",
                },
            }

        elif action == "rename":
            name = data.get("name")
            if name is None:
                response = {
                    "status": "failed",
                    "reason": 'Required attribute "name" was not provided',
                }
                return web.json_response(data=response, status=400)

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
        """Save current effects of virtuals as a scene"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        scene_name = data.get("name")
        scene_tags = data.get("scene_tags")
        scene_puturl = data.get("scene_puturl")
        scene_payload = data.get("scene_payload")
        scene_midiactivate = data.get("scene_midiactivate")
        scene_image = data.get("scene_image")
        if scene_image is None:
            scene_image = "Wallpaper"
        if scene_name is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "scene_name" was not provided',
            }
            return web.json_response(data=response, status=400)

        scene_id = generate_id(scene_name)

        scene_config = {}
        scene_config["name"] = scene_name
        scene_config["virtuals"] = {}
        scene_config["scene_image"] = scene_image
        scene_config["scene_puturl"] = scene_puturl
        scene_config["scene_tags"] = scene_tags
        scene_config["scene_payload"] = scene_payload
        scene_config["scene_midiactivate"] = scene_midiactivate

        if "virtuals" not in data.keys():
            for virtual in self._ledfx.virtuals.values():
                effect = {}
                if virtual.active_effect:
                    effect["type"] = virtual.active_effect.type
                    effect["config"] = virtual.active_effect.config
                    # effect['name'] = virtual.active_effect.name
                scene_config["virtuals"][virtual.id] = effect
        else:
            virtuals = data.get("virtuals")

            for virtualid in virtuals:
                virtual = data.get("virtuals")[virtualid]
                if bool(virtual):
                    effect = {}
                    effect["type"] = virtual["type"]
                    effect["config"] = virtual["config"]
                    scene_config["virtuals"][virtualid] = effect

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
