import asyncio
import logging
from collections.abc import Mapping

from pydantic import ValidationError

from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Scene, SceneVirtual
from ledfx.configuration.presets import configs_match, filter_config_for_comparison
from ledfx.errors import Conflict, Invalid, NotFound, SafeMode, ensure_writable
from ledfx.events import SceneActivatedEvent, SceneDeletedEvent
from ledfx.presets import ledfx_presets
from ledfx.utils import generate_default_config, generate_id

_LOGGER = logging.getLogger(__name__)


def scene_action(virtual_config: SceneVirtual) -> str:
    """The scene action, inferring legacy entries (no action field)."""
    if virtual_config.action is not None:
        return virtual_config.action
    # Empty entry, or neither type nor config: ignore (legacy behaviour).
    if virtual_config.type is None and virtual_config.config is None:
        return "ignore"
    return "activate"


def is_empty(virtual_config: SceneVirtual) -> bool:
    """True for an entry with nothing set (a legacy `{}`)."""
    return not virtual_config.model_dump()


class Scenes:
    """Scenes manager"""

    # Interfaces directly with config - no real need to create Scene objects.

    def __init__(self, ledfx):
        self._ledfx = ledfx
        # Delayed activations from activate_in, by scene id.
        self._pending: dict[str, asyncio.TimerHandle] = {}

    @property
    def _scenes(self) -> dict[str, Scene]:
        return self._ledfx.config.scenes

    def existing_virtual_ids(self, virtual_ids: list[str]) -> list[str]:
        """Drop ids of virtuals that do not exist (was SCENE_SCHEMA's validator)."""
        return [
            virtual_id
            for virtual_id in virtual_ids
            if self._ledfx.virtuals.get(virtual_id)
        ]

    def save_to_config(self):
        self._ledfx.config_store.request_save()

    def create_from_config(self, config):
        # maybe use this to sanitise scenes on startup or smth
        pass

    def create(self, scene_config, scene_id=None):
        """Creates a scene of current effects of specified virtuals if no ID given, else updates one with matching id"""
        ensure_writable(self._ledfx)
        virtual_effects = {}
        for virtual_id in self.existing_virtual_ids(scene_config["virtuals"]):
            virtual = self._ledfx.virtuals.get(virtual_id)
            effect = {}
            if virtual.active_effect:
                effect["type"] = virtual.active_effect.type
                effect["config"] = virtual.active_effect.config.as_dict()
            virtual_effects[virtual_id] = effect
        scene = Scene.model_validate({**scene_config, "virtuals": virtual_effects})
        scene_id = scene_id if scene_id in self._scenes else generate_id(scene.name)

        # Update the scene if it already exists, else create it
        self._scenes[scene_id] = scene
        self.save_to_config()

    def activate_in(self, scene_id: str, delay: float) -> None:
        """Activate a scene after delay seconds, replacing any pending one."""
        ensure_writable(self._ledfx)
        self.cancel_pending(scene_id)
        self._pending[scene_id] = self._ledfx.loop.call_later(
            delay, self._activate_pending, scene_id
        )

    def _activate_pending(self, scene_id: str) -> None:
        del self._pending[scene_id]
        try:
            self.activate(scene_id)
        except SafeMode:
            # Safe mode can begin after the activation was scheduled.
            _LOGGER.debug("Scene %s not activated: safe mode", scene_id)

    def cancel_pending(self, scene_id: str) -> None:
        """Cancel a delayed activation of scene_id, if there is one."""
        if handle := self._pending.pop(scene_id, None):
            handle.cancel()

    def activate(self, scene_id, save_config_after=True):
        """Activate a scene with support for action field

        Args:
            scene_id: The ID of the scene to activate
            save_config_after: If True, the scene also requests a save after the
                              last virtual. Only that final save is optional: the
                              manager saves each effect change it makes either way.
                              Playlists pass False to skip the extra request.
        """
        ensure_writable(self._ledfx)
        self.cancel_pending(scene_id)
        scene = self.get(scene_id)
        if not scene:
            _LOGGER.error("No scene found with id: %s", scene_id)
            return False

        for virtual_id, virtual_config in scene.virtuals.items():
            if self._ledfx.virtuals.get(virtual_id) is None:
                # virtual has been deleted since scene was created
                continue
            try:
                self._apply(VirtualIdStr(virtual_id), virtual_config)
            except (Invalid, NotFound, Conflict) as exc:
                _LOGGER.warning(
                    "Scene %s: virtual %r refused its entry: %s",
                    scene_id,
                    virtual_id,
                    exc,
                )
            except Exception:
                _LOGGER.exception(
                    "Scene %s: failed to apply virtual %r", scene_id, virtual_id
                )

        self._ledfx.events.fire_event(SceneActivatedEvent(scene_id))

        if save_config_after:
            self._ledfx.config_store.request_save()

        return True

    def _apply(self, virtual_id: VirtualIdStr, virtual_config: SceneVirtual) -> None:
        """Apply one scene entry to a virtual, through the manager."""
        virtuals = self._ledfx.virtuals
        action = scene_action(virtual_config)

        if action == "stop":
            virtuals.clear_effect(virtual_id)

        elif action == "forceblack":
            self._start(virtual_id, "singleColor", {"color": "#000000"})

        elif action == "activate":
            # The type is required for both preset and explicit config
            effect_type = virtual_config.type
            if not effect_type:
                _LOGGER.warning(
                    "Invalid activate config for virtual %s, missing required 'type' field",
                    virtual_id,
                )
                return
            if effect_type not in self._ledfx.effects.types():
                raise Invalid(f"Unknown effect type: {effect_type}")

            if virtual_config.preset:
                # Resolve preset from current library for this effect type
                # (will fall back to reset preset if not found)
                effect_config = self._resolve_preset(effect_type, virtual_config.preset)
            else:
                effect_config = virtual_config.config
                if effect_config is None:
                    _LOGGER.warning(
                        "Invalid activate config for virtual %s, missing 'config' field",
                        virtual_id,
                    )
                    return
            self._start(virtual_id, effect_type, effect_config)

        # "ignore" and unknown actions leave the virtual unchanged

    def _start(
        self,
        virtual_id: VirtualIdStr,
        effect_type: str,
        effect_config: Mapping[str, object],
    ) -> None:
        effects = self._ledfx.effects
        try:
            config = (
                effects.get_class(effect_type)
                .config_model()
                .model_validate(effect_config)
            )
        except ValidationError as err:
            raise Invalid(str(err)) from err
        self._ledfx.virtuals.set_effect(virtual_id, effect_type, config, fallback=None)

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
        if effect_type in ledfx_presets and preset_name in ledfx_presets[effect_type]:
            return ledfx_presets[effect_type][preset_name].get("config", {})

        # Check user_presets
        user_presets = self._ledfx.config.user_presets
        if effect_type in user_presets and preset_name in user_presets[effect_type]:
            return user_presets[effect_type][preset_name].config

        # Preset not found, fall back to reset preset
        _LOGGER.warning(
            "Preset '%s' not found for effect '%s', falling back to reset preset",
            preset_name,
            effect_type,
        )
        return generate_default_config(self._ledfx.effects, effect_type)

    def deactivate(self, scene_id):
        """Deactivate the effects defined in a scene by clearing those virtuals."""
        ensure_writable(self._ledfx)
        self.cancel_pending(scene_id)
        scene = self.get(scene_id)
        if not scene:
            _LOGGER.error("No scene found with id: %s", scene_id)
            return False

        for virtual_id, virtual_config in scene.virtuals.items():
            if self._ledfx.virtuals.get(virtual_id) is None:
                # virtual has been deleted since scene was created
                continue

            # If the scene has an effect entry for this virtual, clear it
            if not is_empty(virtual_config):
                try:
                    self._ledfx.virtuals.clear_effect(VirtualIdStr(virtual_id))
                except (Invalid, NotFound, Conflict) as exc:
                    _LOGGER.warning("Scene %s: %s", scene_id, exc)
                except Exception:
                    _LOGGER.exception(
                        "Scene %s: failed to clear virtual %r", scene_id, virtual_id
                    )

        # Persist the change so that clearing effects is saved
        self._ledfx.config_store.request_save()

        return True

    def destroy(self, scene_id):
        """Deletes a scene"""
        ensure_writable(self._ledfx)
        self.cancel_pending(scene_id)
        if not self._scenes.pop(scene_id, None):
            _LOGGER.warning("Cannot delete non-existent scene id: %s", scene_id)
            return
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

        for virtual_id, virtual_config in scene.virtuals.items():
            virtual = self._ledfx.virtuals.get(virtual_id)
            if virtual is None:
                return False

            current_effect = virtual.active_effect
            action = scene_action(virtual_config)

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
                current_config = getattr(current_effect, "config", None)
                if (
                    filter_config_for_comparison(current_config).get("color")
                    != "#000000"
                ):
                    return False

            elif action == "activate":
                # Virtual should have matching effect type and config
                expected_type = virtual_config.type
                if not expected_type:
                    # Invalid config, can't be active
                    return False

                if current_effect is None:
                    return False

                if getattr(current_effect, "type", None) != expected_type:
                    return False

                # For preset-based activation, resolve the preset to compare configs
                preset_name = virtual_config.preset
                if preset_name:
                    expected_config = self._resolve_preset(expected_type, preset_name)
                else:
                    expected_config = virtual_config.config
                    if expected_config is None:
                        # Invalid config, can't be active
                        return False

                current_config = getattr(current_effect, "config", None) or {}

                # Normalize the expected config by filling in defaults for missing keys
                # This ensures legacy scenes (with fewer keys) match current effects (with new keys)
                # The current config doesn't need normalization as it's the running effect with all keys
                default_config = generate_default_config(
                    self._ledfx.effects, expected_type
                )
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
