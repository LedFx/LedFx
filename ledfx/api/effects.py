import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.virtual_effects import process_fallback
from ledfx.color import (
    get_color_at_position,
    resolve_gradient,
    validate_color,
    validate_gradient,
)
from ledfx.config import save_config
from ledfx.effects import DummyEffect
from ledfx.virtuals import Virtuals

_LOGGER = logging.getLogger(__name__)


# color group definitions for applying global color settings to effects
# value is the normalized position on the gradient (0.0 - 1.0) or None if not applicable

color_groups = [
    {
        "value": 0.0,
        "keys": [
            "lows_color",
            "color_lows",
            "color_low",
            "low_band",
            "color_beat",
            "color_min",
            "color",
        ],
    },
    {
        "value": 0.5,
        "keys": [
            "color_mid",
            "color_mids",
            "mid_band",
            "mids_color",
            "hit_color",
            "color_scan",
            "color_bar",
            "text_color",
        ],
    },
    {
        "value": 1.0,
        "keys": [
            "color_high",
            "high_band",
            "high_color",
            "sparks_color",
            "strobe_color",
            "color_max",
        ],
    },
    {
        "value": None,
        "keys": [
            "flash_color",
            "pixel_color",
            "color_peak",
        ],
    },
]


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/effects"

    async def get(self) -> web.Response:
        """
        Retrieves the active effects for each virtual LED strip.

        Returns:
            web.Response: The HTTP response containing the active effects for each virtual LED strip.
        """
        response = {"status": "success", "effects": {}}
        for virtual in self._ledfx.virtuals.values():
            if virtual.active_effect:
                response["effects"][virtual.id] = {
                    "effect_type": virtual.active_effect.type,
                    "effect_config": virtual.active_effect.config,
                }
        return await self.bare_request_success(response)

    async def put(self, request: web.Request) -> web.Response:
        """
        Handle PUT request to clear all effects on all devices.

        Args:
            request (web.Request): The request including the `action` to perform.

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

        if action not in [
            "clear_all_effects",
            "apply_global",
            "apply_global_effect",
        ]:
            return await self.invalid_request(f'Invalid action "{action}"')

        if action == "apply_global":
            return await self._apply_global(data)

        if action == "apply_global_effect":
            return await self._apply_global_effect(data)

        # Clear all effects on all devices
        if action == "clear_all_effects":
            self._ledfx.virtuals.clear_all_effects()
            return await self.request_success(
                "info", "Cleared all effects on all devices"
            )

    async def _apply_global(self, data: dict) -> web.Response:
        """
        Apply a global configuration update across active effects.

        This was extracted from the PUT handler to keep that method tidy
        while preserving the original behavior.
        """
        # Define supported configuration keys and their validation
        SUPPORTED_KEYS = {
            "gradient": {"validator": validate_gradient, "type": "string"},
            "background_color": {
                "validator": validate_color,
                "type": "string",
            },
            "background_brightness": {
                "validator": lambda x: max(0.0, min(1.0, float(x))),
                "type": "number",
            },
            "brightness": {
                "validator": lambda x: max(0.0, min(1.0, float(x))),
                "type": "number",
            },
            "flip": {"validator": None, "type": "boolean"},
            "mirror": {"validator": None, "type": "boolean"},
        }

        # Check if at least one supported key is provided
        provided_keys = [key for key in SUPPORTED_KEYS.keys() if key in data]
        if not provided_keys:
            return await self.invalid_request(
                f'At least one of the following attributes must be provided: {", ".join(SUPPORTED_KEYS.keys())}'
            )

        # Validate and process each provided key
        config_updates = {}

        for key in provided_keys:
            value = data[key]
            key_info = SUPPORTED_KEYS[key]

            try:
                if key == "gradient":
                    # Resolve the gradient into a config-storable string and
                    # a parsed Gradient object for sampling.
                    try:
                        config_val, parsed_gradient = resolve_gradient(
                            value, self._ledfx.gradients
                        )
                        config_updates[key] = config_val
                    except Exception as e:
                        return await self.invalid_request(
                            f'Invalid value for "{key}": {e}'
                        )

                    if parsed_gradient is not None:

                        # now sample and populate color group keys
                        for group in color_groups:
                            if group["value"] is None:
                                continue
                            try:
                                color_at_pos = get_color_at_position(
                                    parsed_gradient, group["value"]
                                )
                            except Exception as e:
                                _LOGGER.warning(
                                    f"Failed to sample gradient at {group['value']}: {e}"
                                )
                                continue
                            for color_key in group["keys"]:
                                if color_key in provided_keys:
                                    # Skip if the user explicitly provided this key
                                    continue
                                config_updates[color_key] = color_at_pos

                elif key_info["type"] == "boolean":
                    # Special handling for boolean keys (True, False, "toggle")
                    if isinstance(value, bool):
                        config_updates[key] = value
                    elif isinstance(value, str) and value.lower() == "toggle":
                        # Mark for toggling - will be resolved per effect
                        config_updates[key] = "toggle"
                    else:
                        return await self.invalid_request(
                            f'Invalid value for "{key}": must be true, false, or "toggle"'
                        )

                else:
                    # Standard validation
                    if key_info["validator"]:
                        validated_value = key_info["validator"](value)
                        config_updates[key] = validated_value
                    else:
                        config_updates[key] = value

            except Exception as e:
                return await self.invalid_request(
                    f'Invalid value for "{key}": {e}'
                )

        # Apply updates to all compatible effects
        # Optional filter: a list of virtual ids to restrict the update to
        virtuals_filter = None
        if "virtuals" in data:
            vlist = data["virtuals"]
            if not isinstance(vlist, list):
                return await self.invalid_request(
                    'Invalid value for "virtuals": must be a list of virtual ids'
                )
            virtuals_filter = {str(v) for v in vlist}

        updated = 0
        skipped = 0

        for virtual in self._ledfx.virtuals.values():
            # If a virtuals filter was provided, skip non-matching virtuals
            if (
                virtuals_filter is not None
                and virtual.id not in virtuals_filter
            ):
                continue
            eff = getattr(virtual, "active_effect", None)
            if eff is None or isinstance(eff, DummyEffect):
                continue

            # Get effect schema and hidden keys
            try:
                schema = type(eff).schema().schema
                hidden_keys = getattr(eff, "HIDDEN_KEYS", []) or []
            except Exception:
                schema = {}
                hidden_keys = []

            # Normalize schema keys to handle voluptuous wrapper objects
            normalized_keys = set()
            for schema_key in schema.keys():
                if hasattr(schema_key, "schema"):
                    # Extract the underlying key from vol.Optional/Required wrappers
                    normalized_keys.add(schema_key.schema)
                else:
                    # Handle string keys directly
                    normalized_keys.add(str(schema_key))

            # Build config update for this specific effect
            effect_config_update = {}

            for key, value in config_updates.items():
                # Skip if key is not in effect schema
                if key not in normalized_keys:
                    continue

                # Skip if key is in HIDDEN_KEYS for this effect
                if key in hidden_keys:
                    continue

                # Handle toggle for boolean keys
                if value == "toggle" and key in ["flip", "mirror"]:
                    current_value = getattr(eff, "_config", {}).get(key, False)
                    effect_config_update[key] = not current_value
                else:
                    effect_config_update[key] = value

            # Apply the update if there are any valid keys
            if effect_config_update:
                try:
                    eff.update_config(effect_config_update)
                    virtual.update_effect_config(eff)
                    updated += 1
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to update config on virtual {getattr(virtual, 'id', '?')}: {e}"
                    )
                    skipped += 1
            else:
                skipped += 1

        # Persist configuration changes
        if updated > 0:
            try:
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to save config after apply_global: {e}"
                )

        return await self.request_success(
            "success",
            f"Applied global configuration to {updated} effects (skipped {skipped})",
        )

    async def _apply_global_effect(self, data: dict) -> web.Response:
        """
        Apply a specific effect (type + config) to a list of virtual ids.

        Expected payload:
        {
            "virtuals": ["id1", "id2", ...],
            "type": "effect_type",
            "config": { ... }    # optional, empty dict resets
        }
        """

        vlist = data.get("virtuals", None)
        if vlist is None:
            vlist = Virtuals.get_virtual_ids()
        elif not isinstance(vlist, list) or not vlist:
            return await self.invalid_request(
                'Invalid value for "virtuals": must be a non-empty list of virtual ids'
            )

        effect_type = data.get("type")
        if not effect_type:
            return await self.invalid_request(
                'Required attribute "type" was not provided'
            )

        # Effect config may be omitted (treated as reset) or provided as a dict
        effect_config = data.get("config")
        if effect_config == "RANDOMIZE":
            return await self.invalid_request(
                "RANDOMIZE is not supported for apply_global_effect"
            )
        if effect_config is None:
            # Reset behavior
            effect_config = {}

        # Fallback behaviour (same semantics as virtual endpoint)
        fallback = process_fallback(data.get("fallback", None))

        applied = 0
        skipped = 0
        blocked = 0
        failed = 0

        for vid in vlist:
            virtual = self._ledfx.virtuals.get(str(vid))
            if virtual is None:
                skipped += 1
                continue

            if fallback is not None and virtual.streaming:
                # Don't interrupt the whole operation; record that this virtual is
                # blocked due to an active stream and skip it.
                blocked += 1
                _LOGGER.debug(
                    "Skipping virtual %s: streaming active and fallback provided",
                    vid,
                )
                continue

            # Create the effect and set it on the virtual. If config is empty, this
            # effectively resets to defaults (effects.create will handle defaulting).
            try:
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx, type=effect_type, config=effect_config
                )
                # apply effect with provided fallback (may be None)
                virtual.set_effect(effect, fallback=fallback)
                virtual.update_effect_config(effect)
                applied += 1
            except (ValueError, RuntimeError) as msg:
                _LOGGER.warning(
                    f"Unable to set effect on virtual {vid}: {msg}"
                )
                failed += 1

        # Persist configuration changes if anything applied
        if applied > 0:
            try:
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to save config after apply_global_effect: {e}"
                )

        return await self.request_success(
            "success",
            f"Applied effect '{effect_type}' to {applied} virtuals (skipped {skipped}, blocked {blocked}, failed {failed})",
        )
