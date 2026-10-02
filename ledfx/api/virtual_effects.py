import logging
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.randomize import randomize_effect_config
from ledfx.effects import DummyEffect
from ledfx.errors import Conflict, Invalid
from ledfx.virtuals import EffectRejected

_LOGGER = logging.getLogger(__name__)


def process_fallback(fallback: object) -> float | None:
    """converts the fallback param to a sanitized value

    Args:
        fallback (None, Bool, float, int): Fallback behaviour
            - None: No fallback
            - Bool: True uses a default fallback time, False no fallback
            - float/int: fallback time in seconds

    Returns:
        float:None: Sanitized falback time or None
    """
    if isinstance(fallback, bool):
        # True: a long default, so a caller that forgets a time and an effect
        # that never exits by itself can't leave the virtual stuck.
        return 300.0 if fallback else None
    if isinstance(fallback, (int, float)) and fallback > 0:
        return fallback
    return None


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/effects"

    def _known_effect(self, effect_type: object) -> bool:
        return (
            isinstance(effect_type, str) and effect_type in self._ledfx.effects.types()
        )

    async def get(self, virtual_id: str) -> web.Response:
        """
        Get active effect configuration for a virtual.

        Parameters:
        - virtual_id (str): The ID of the virtual.

        Returns:
        - web.Response: The response containing the active effect configuration.

        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        # Protect from DummyEffect
        response: dict[str, object]
        if virtual.active_effect and not isinstance(virtual.active_effect, DummyEffect):
            response = {
                "effect": {
                    "config": virtual.active_effect.config,
                    "name": virtual.active_effect.name,
                    "type": virtual.active_effect.type,
                }
            }
        else:
            response = {"effect": {}}

        return await self.bare_request_success(response)

    async def put(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Update the config of the active effect of a virtual.

        Args:
            virtual_id (str): The ID of the virtual.
            request (web.Request): The request object with effect `config` and `type`. An empty `config` resets the effect config.

        Returns:
            web.Response: The HTTP response object.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        if not virtual.active_effect or isinstance(virtual.active_effect, DummyEffect):
            return await self.invalid_request(
                f"Virtual {virtual_id} has no active effect"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        effect_config = data.get("config")
        # Without a type, the config updates the active effect.
        effect_type = data.get("type", virtual.active_effect.type)
        if not self._known_effect(effect_type):
            return await self.invalid_request(f"Unknown effect type: {effect_type}")
        if effect_config is None:
            effect_config = dict[str, object]()
        if effect_config == "RANDOMIZE":
            effect_type = virtual.active_effect.type
            effect_class = self._ledfx.effects.get_class(effect_type)
            effect_config = randomize_effect_config(
                effect_class.config_model(), ["brightness"]
            )
        if not isinstance(effect_config, dict):
            return await self.invalid_request("'config' must be an object")

        fallback = process_fallback(data.get("fallback", None))

        if fallback is not None and virtual.streaming:
            error_message = (
                f"Unable to set effect: Virtual {virtual_id} being streamed to"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message, "error", resp_code=409)

        # The same type updates the running effect; another type replaces it.
        virtuals = self._ledfx.virtuals
        try:
            if virtual.active_effect.type == effect_type:
                virtual = virtuals.patch_effect(
                    VirtualIdStr(virtual_id), effect_config, fallback=fallback
                )
            else:
                virtual = virtuals.set_effect(
                    VirtualIdStr(virtual_id),
                    effect_type,
                    effect_config,
                    fallback=fallback,
                )
        except ValidationError as err:
            return await self.validation_error(err)
        except (Invalid, Conflict) as err:
            error_message = f"Unable to set effect: {err.detail}"
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message, "warning")

        effect = virtual.active_effect
        effect_response = {
            "config": effect.config,
            "name": effect.name,
            "type": effect.type,
        }
        response = {"status": "success", "effect": effect_response}
        return await self.bare_request_success(response)

    async def post(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Set the active effect of a virtual.

        Parameters:
        - virtual_id (str): The ID of the virtual.
        - request (web.Request): The request object containing the effect `type` and `config` (optional). An empty config resets the effect config.

        Returns:
        - web.Response: The HTTP response object.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        effect_type = data.get("type")
        if effect_type is None:
            return await self.invalid_request(
                "Required attribute 'type' was not provided"
            )
        if not self._known_effect(effect_type):
            return await self.invalid_request(f"Unknown effect type: {effect_type}")

        effect_config = data.get("config")
        if effect_config == "RANDOMIZE":
            effect_class = self._ledfx.effects.get_class(effect_type)
            effect_config = randomize_effect_config(
                effect_class.config_model(),
                ["brightness", "background_color", "background_brightness"],
            )
        elif effect_config is not None and not isinstance(effect_config, dict):
            return await self.invalid_request("'config' must be an object")

        fallback = process_fallback(data.get("fallback", None))
        try:
            # config None: the manager restores the type's stored config.
            virtual = self._ledfx.virtuals.set_effect(
                VirtualIdStr(virtual_id), effect_type, effect_config, fallback=fallback
            )
        except ValidationError as err:
            return await self.validation_error(err)
        except EffectRejected as err:
            error_message = (
                f"Unable to set effect {err.effect} on {virtual_id}: {err.detail}"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)
        except Conflict as err:
            error_message = f"Unable to set effect: {err.detail}"
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message, "error", resp_code=409)

        effect = virtual.active_effect
        effect_response = {
            "config": effect.config,
            "name": effect.name,
            "type": effect.type,
        }
        response = {"status": "success", "effect": effect_response}
        return await self.bare_request_success(response)

    async def delete(self, virtual_id: str) -> web.Response:
        """
        Deletes a virtual effect with the given ID.

        Args:
            virtual_id (str): The ID of the virtual effect to delete.

        Returns:
            web.Response: The response indicating the success or failure of the deletion.
        """
        if self._ledfx.virtuals.get(virtual_id) is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        self._ledfx.virtuals.clear_effect(VirtualIdStr(virtual_id))
        response: dict[str, object] = {"status": "success", "effect": {}}
        return await self.bare_request_success(response)
