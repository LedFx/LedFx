import logging

import voluptuous as vol

from ledfx.config import (
    configs_match,
    filter_config_for_comparison,
    save_config,
)
from ledfx.events import SceneActivatedEvent, SceneDeletedEvent
from ledfx.utils import generate_default_config, generate_id

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
        """Activate a scene with support for action field"""
        scene = self.get(scene_id)
        if not scene:
            _LOGGER.error(f"No scene found with id: {scene_id}")
            return False

        for virtual_id in scene["virtuals"]:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if not virtual:
                # virtual has been deleted since scene was created
                continue

            virtual_config = scene["virtuals"][virtual.id]
            action = virtual_config.get("action")

            # Legacy support: if no action field, infer from config
            if action is None:
                # Empty dict or no type/config means ignore (legacy behavior)
                if not virtual_config or (
                    "type" not in virtual_config
                    and "config" not in virtual_config
                ):
                    action = "ignore"
                else:
                    action = "activate"

            # Process action
            if action == "ignore":
                # Leave virtual unchanged
                continue

            elif action == "stop":
                # Stop any playing effect
                virtual.clear_effect()

            elif action == "forceblack":
                # Set to Single Color effect with black
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx,
                    type="singleColor",
                    config={"color": "#000000"},
                )
                virtual.set_effect(effect)
                virtual.update_effect_config(effect)

            elif action == "activate":
                # Get effect type (required for both preset and explicit config)
                effect_type = virtual_config.get("type")
                if not effect_type:
                    _LOGGER.warning(
                        f"Invalid activate config for virtual {virtual_id}, missing required 'type' field"
                    )
                    continue

                # Check if using preset
                preset_name = virtual_config.get("preset")
                if preset_name:
                    # Resolve preset from current library for this effect type
                    # (will fall back to reset preset if not found)
                    effect_config = self._resolve_preset(
                        effect_type, preset_name
                    )
                else:
                    # Use explicit config
                    effect_config = virtual_config.get("config")
                    if effect_config is None:
                        _LOGGER.warning(
                            f"Invalid activate config for virtual {virtual_id}, missing 'config' field"
                        )
                        continue

                # Create and apply the effect
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx,
                    type=effect_type,
                    config=effect_config,
                )
                virtual.set_effect(effect)
                virtual.update_effect_config(effect)

        self._ledfx.events.fire_event(SceneActivatedEvent(scene_id))

        try:
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
        except Exception:
            _LOGGER.exception("Failed to save config after scene activation")

        return True

    def _resolve_preset(self, effect_type, preset_name):
        """Resolve a preset name to effect config for a specific effect type.

        Falls back to reset preset (factory defaults) if the requested preset is not found.

        Args:
            effect_type: The effect type to search within
            preset_name: Name of the preset to resolve

        Returns:
            dict: Effect config (always returns a valid config, falling back to reset)
        """
        # Handle special "reset" preset
        if preset_name == "reset":
            return generate_default_config(self._ledfx.effects, effect_type)

        # Check ledfx_presets first
        ledfx_presets = self._ledfx.config.get("ledfx_presets", {})
        if (
            effect_type in ledfx_presets
            and preset_name in ledfx_presets[effect_type]
        ):
            return ledfx_presets[effect_type][preset_name].get("config", {})

        # Check user_presets
        user_presets = self._ledfx.config.get("user_presets", {})
        if (
            effect_type in user_presets
            and preset_name in user_presets[effect_type]
        ):
            return user_presets[effect_type][preset_name].get("config", {})

        # Preset not found, fall back to reset preset
        _LOGGER.warning(
            f"Preset '{preset_name}' not found for effect '{effect_type}', falling back to reset preset"
        )
        return generate_default_config(self._ledfx.effects, effect_type)

    def deactivate(self, scene_id):
        """Deactivate the effects defined in a scene by clearing those virtuals."""
        scene = self.get(scene_id)
        if not scene:
            _LOGGER.error(f"No scene found with id: {scene_id}")
            return False

        for virtual_id in scene["virtuals"]:
            virtual = self._ledfx.virtuals.get(virtual_id)
            if not virtual:
                # virtual has been deleted since scene was created
                continue

            # If the scene has an effect entry for this virtual, clear it
            if scene["virtuals"][virtual.id]:
                virtual.clear_effect()

        # Persist the change so that clearing effects is saved
        try:
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
        except Exception:
            _LOGGER.exception("Failed to save config after scene deactivation")

        return True

    def destroy(self, scene_id):
        """Deletes a scene"""

        if not self._scenes.pop(scene_id, None):
            _LOGGER.error(f"Cannot delete non-existent scene id: {scene_id}")
        self._ledfx.events.fire_event(SceneDeletedEvent(scene_id))
        self.save_to_config()

    def is_active(self, scene_id):
        """Return True when the current virtual state matches the scene definition.

        Handles all action types: ignore, stop, forceblack, activate.
        Also supports legacy format (no action field).
        """

        scene = self.get(scene_id)
        if not scene:
            return False

        virtuals = scene.get("virtuals") or {}
        for virtual_id, virtual_config in virtuals.items():
            virtual = self._ledfx.virtuals.get(virtual_id)
            if virtual is None:
                return False

            current_effect = virtual.active_effect
            action = virtual_config.get("action")

            # Legacy support: if no action field, infer from config
            if action is None:
                # Empty dict or no type/config means ignore (legacy behavior)
                if not virtual_config or (
                    "type" not in virtual_config
                    and "config" not in virtual_config
                ):
                    action = "ignore"
                else:
                    action = "activate"

            # Process action
            if action == "ignore":
                # Virtual should remain unchanged - always matches
                continue

            elif action == "stop":
                # Virtual should have no active effect
                if current_effect is not None:
                    return False

            elif action == "forceblack":
                # Virtual should have singleColor effect with #000000
                if current_effect is None:
                    return False
                if getattr(current_effect, "type", None) != "singleColor":
                    return False
                current_config = getattr(current_effect, "config", None) or {}
                if current_config.get("color") != "#000000":
                    return False

            elif action == "activate":
                # Virtual should have matching effect type and config
                expected_type = virtual_config.get("type")
                if not expected_type:
                    # Invalid config, can't be active
                    return False

                if current_effect is None:
                    return False

                if getattr(current_effect, "type", None) != expected_type:
                    return False

                # For preset-based activation, resolve the preset to compare configs
                preset_name = virtual_config.get("preset")
                if preset_name:
                    expected_config = self._resolve_preset(
                        expected_type, preset_name
                    )
                else:
                    expected_config = virtual_config.get("config")
                    if expected_config is None:
                        # Invalid config, can't be active
                        return False

                current_config = getattr(current_effect, "config", None) or {}
                
                # Normalize the expected config by filling in defaults for missing keys
                # This ensures legacy scenes (with fewer keys) match current effects (with new keys)
                # The current config doesn't need normalization as it's the running effect with all keys
                default_config = generate_default_config(self._ledfx.effects, expected_type)
                normalized_expected = {**default_config, **expected_config}
                
                if not configs_match(current_config, normalized_expected):
                    return False

            # Unknown actions are skipped during activation, so they don't affect active state
            # (treat as "ignore")

        return True

    def __iter__(self):
        return iter(self._scenes)

    def values(self):
        return self._scenes.values()

    def get(self, *args):
        return self._scenes.get(*args)
