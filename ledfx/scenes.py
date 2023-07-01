import logging

import voluptuous as vol

from ledfx.config import save_config
from ledfx.events import SceneActivatedEvent, SceneDeletedEvent
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class Scenes:
    """Scenes manager"""

    # Interfaces directly with config - no real need to create Scene objects.

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._scenes = self._ledfx.config["scenes"]

        def virtuals_validator(virtual_ids):
            return list(
                virtual_id
                for virtual_id in virtual_ids
                if self._ledfx.virtuals.get(virtual_id)
            )

        self.SCENE_SCHEMA = vol.Schema(
            {
                vol.Required("name", description="Name of the scene"): str,
                vol.Optional(
                    "scene_image",
                    description="Image or icon to display",
                    default="Wallpaper",
                ): str,
                vol.Optional(
                    "scene_tags",
                    description="Tags for filtering",
                ): str,
                vol.Optional(
                    "scene_puturl",
                    description="On Scene Activate, URL to PUT too",
                ): str,
                vol.Optional(
                    "scene_payload",
                    description="On Scene Activate, send this payload to scene_puturl",
                ): str,
                vol.Optional(
                    "scene_midiactivate",
                    description="On MIDI key/note, Activate a scene",
                ): str,
                vol.Required(
                    "virtuals",
                    description="The effects of these virtuals will be saved",
                ): virtuals_validator,
            }
        )

    def save_to_config(self):
        self._ledfx.config["scenes"] = self._scenes
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    def create_from_config(self, config):
        # maybe use this to sanitise scenes on startup or smth
        pass

    def create(self, scene_config, scene_id=None):
        """Creates a scene of current effects of specified virtuals if no ID given, else updates one with matching id"""
        scene_config = self.SCENE_SCHEMA(scene_config)
        scene_id = (
            scene_id
            if scene_id in self._scenes
            else generate_id(scene_config["name"])
        )

        virtual_effects = {}
        for virtual in scene_config["virtuals"]:
            effect = {}
            if virtual.active_effect:
                effect["type"] = virtual.active_effect.type
                effect["config"] = virtual.active_effect.config
            virtual_effects[virtual.id] = effect
        scene_config["virtuals"] = virtual_effects

        # Update the scene if it already exists, else create it
        self._scenes[scene_id] = scene_config
        self.save_to_config()

    def activate(self, scene_id):
        """Activate a scene"""
        scene = self.get(scene_id)
        if not scene:
            _LOGGER.error(f"No scene found with id: {scene_id}")
            return

        for virtual_id in scene["virtuals"]:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if not virtual:
                # virtual has been deleted since scene was created
                # remove from scene?
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

    def destroy(self, scene_id):
        """Deletes a scene"""

        if not self._scenes.pop(scene_id, None):
            _LOGGER.error("Cannot delete non-existent scene id: {scene_id}")
        self._ledfx.events.fire_event(SceneDeletedEvent(scene_id))
        self.save_to_config()

    def __iter__(self):
        return iter(self._scenes)

    def values(self):
        return self._scenes.values()

    def get(self, *args):
        return self._scenes.get(*args)
