import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import validate_gradient
from ledfx.config import save_config
from ledfx.effects import DummyEffect

_LOGGER = logging.getLogger(__name__)


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

        if action not in ["clear_all_effects", "apply_global_gradient"]:
            return await self.invalid_request(f'Invalid action "{action}"')

        # Apply a single gradient to all active effects that support 'gradient'
        if action == "apply_global_gradient":
            gradient = data.get("gradient")
            if not isinstance(gradient, str) or not gradient.strip():
                return await self.invalid_request(
                    'Required attribute "gradient" was not provided'
                )

            try:
                # Validates keys and full gradient strings alike
                validate_gradient(gradient)
            except Exception as e:
                return await self.invalid_request(f"Invalid gradient: {e}")

            updated = 0
            for virtual in self._ledfx.virtuals:
                eff = getattr(virtual, "active_effect", None)
                if eff is None or isinstance(eff, DummyEffect):
                    continue
                try:
                    schema = type(eff).schema().schema
                except Exception:
                    schema = {}

                if "gradient" not in schema:
                    continue

                try:
                    eff.update_config({"gradient": gradient})
                    virtual.update_effect_config(eff)
                    updated += 1
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to update gradient on virtual {getattr(virtual, 'id', '?')}: {e}"
                    )

            # Persist once
            try:
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
            except Exception as e:
                _LOGGER.warning(
                    f"Failed to save config after apply_global_gradient: {e}"
                )

            return await self.request_success(
                "success",
                f"Applied gradient to {updated} active effects with gradient support",
            )

        # Clear all effects on all devices
        if action == "clear_all_effects":
            self._ledfx.virtuals.clear_all_effects()
            return await self.request_success(
                "info", "Cleared all effects on all devices"
            )
