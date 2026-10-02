import logging
from dataclasses import replace
from json import JSONDecodeError
from typing import SupportsFloat

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.api.v1_compat import effect_config as validated_effect_config
from ledfx.api.virtual_effects import process_fallback
from ledfx.color import resolve_gradient, validate_color
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import ApplyConfigResult, GlobalEffectUpdate
from ledfx.errors import Invalid, ensure_writable

_LOGGER = logging.getLogger(__name__)

# The settings apply_global writes, in the order v1 checks them.
GLOBAL_KEYS = (
    "gradient",
    "background_color",
    "background_brightness",
    "brightness",
    "flip",
    "mirror",
)


def _fraction(value: object) -> float:
    """v1's clamp into 0..1, for anything float() takes."""
    if not isinstance(value, str | SupportsFloat):
        raise TypeError(
            "float() argument must be a string or a real number, "
            f"not '{type(value).__name__}'"
        )
    return max(0.0, min(1.0, float(value)))


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

    async def _apply_global(self, data: dict[str, object]) -> web.Response:
        """
        Apply a global configuration update across active effects.

        This was extracted from the PUT handler to keep that method tidy
        while preserving the original behavior.
        """
        # Check if at least one supported key is provided
        provided_keys = [key for key in GLOBAL_KEYS if key in data]
        if not provided_keys:
            return await self.invalid_request(
                f"At least one of the following attributes must be provided: {', '.join(GLOBAL_KEYS)}"
            )

        # Validate each provided key, in GLOBAL_KEYS order
        update = GlobalEffectUpdate()
        toggles: set[str] = set()

        for key in provided_keys:
            value = data[key]
            try:
                if key == "gradient":
                    if not isinstance(value, str):
                        raise TypeError("must be a string")
                    # The manager resolves it again; this keeps v1's error
                    # order and text.
                    resolve_gradient(value, self._ledfx.gradients)
                    update = replace(update, gradient=value)
                elif key in ("flip", "mirror"):
                    # v1-compat: "toggle" is not a manager value; it is resolved
                    # per virtual below.
                    if isinstance(value, bool):
                        update = (
                            replace(update, flip=value)
                            if key == "flip"
                            else replace(update, mirror=value)
                        )
                    elif isinstance(value, str) and value.lower() == "toggle":
                        toggles.add(key)
                    else:
                        return await self.invalid_request(
                            f'Invalid value for "{key}": must be true, false, or "toggle"'
                        )
                elif key == "background_color":
                    if not isinstance(value, (str, list, tuple)):
                        # parse_color's own message for a non-color type
                        raise ValueError(f"Invalid color: {value}")
                    update = replace(update, background_color=validate_color(value))
                elif key == "background_brightness":
                    update = replace(update, background_brightness=_fraction(value))
                else:
                    update = replace(update, brightness=_fraction(value))
            except Exception as e:  # noqa: BLE001
                return await self.invalid_request(f'Invalid value for "{key}": {e}')

        # Optional filter: a list of virtual ids to restrict the update to
        virtuals_filter = None
        if "virtuals" in data:
            vlist = data["virtuals"]
            if not isinstance(vlist, list):
                return await self.invalid_request(
                    'Invalid value for "virtuals": must be a list of virtual ids'
                )
            # v1-compat: v1 ignores ids it does not know; the manager raises NotFound.
            virtuals_filter = [
                VirtualIdStr(str(v))
                for v in vlist
                if self._ledfx.virtuals.get(str(v)) is not None
            ]

        if toggles:
            # v1-compat: "toggle" inverts each effect's own value, so v1 makes
            # one explicit-bool call per virtual and sums the counts.
            ensure_writable(self._ledfx)
            counts = ApplyConfigResult(0, 0, 0)
            for virtual in list(self._ledfx.virtuals.values()):
                effect = virtual.active_effect
                if virtuals_filter is not None and virtual.id not in virtuals_filter:
                    continue
                if effect is None:
                    continue
                per_virtual = replace(
                    update,
                    flip=not getattr(effect.config, "flip", False)
                    if "flip" in toggles
                    else update.flip,
                    mirror=not getattr(effect.config, "mirror", False)
                    if "mirror" in toggles
                    else update.mirror,
                )
                part = self._ledfx.virtuals.apply_global_config(
                    per_virtual, [virtual.id]
                )
                counts = ApplyConfigResult(*(a + b for a, b in zip(counts, part)))
        else:
            counts = self._ledfx.virtuals.apply_global_config(update, virtuals_filter)

        # v1-compat: v1 has one "skipped" count for skipped and refused effects.
        return await self.request_success(
            "success",
            f"Applied global configuration to {counts.updated} effects "
            f"(skipped {counts.skipped + counts.failed})",
        )

    async def _apply_global_effect(self, data: dict[str, object]) -> web.Response:
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
        if vlist is not None and (not isinstance(vlist, list) or not vlist):
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
        if effect_config is not None and not isinstance(effect_config, dict):
            return await self.invalid_request("'config' must be an object")

        # Fallback behaviour (same semantics as virtual endpoint)
        fallback = process_fallback(data.get("fallback", None))

        type_id = str(effect_type)
        virtuals = self._ledfx.virtuals
        try:
            # v1-compat: safe mode answers before a bad config does.
            ensure_writable(self._ledfx)
            # v1-compat: unknown ids are skipped and counted, not refused.
            ids = (
                list(virtuals)
                if vlist is None
                else [VirtualIdStr(str(v)) for v in vlist]
            )
            known = [v for v in ids if virtuals.get(v) is not None]
            skipped = len(ids) - len(known)
            config = None
            # v1-compat: check the config up front; a bad one is counted, below.
            if type_id in self._ledfx.effects.types() and effect_config is not None:
                try:
                    config = validated_effect_config(
                        self._ledfx, type_id, effect_config
                    )
                except ValidationError:
                    # v1-compat: a bad config is one failure per virtual that
                    # would have run it, not an error.
                    blocked = sum(
                        1
                        for v in known
                        if fallback is not None and virtuals.get_or_raise(v).streaming
                    )
                    applied, failed = 0, len(known) - blocked
                    return await self._applied_effect(
                        effect_type, applied, skipped, blocked, failed
                    )
            applied, blocked, failed = virtuals.set_effect_all(
                type_id, config, known, fallback=fallback
            )
        except Invalid as err:
            return await self.invalid_request(err.detail)

        return await self._applied_effect(
            effect_type, applied, skipped, blocked, failed
        )

    async def _applied_effect(
        self, effect_type: object, applied: int, skipped: int, blocked: int, failed: int
    ) -> web.Response:
        return await self.request_success(
            "success",
            f"Applied effect '{effect_type}' to {applied} virtuals (skipped {skipped}, blocked {blocked}, failed {failed})",
        )
