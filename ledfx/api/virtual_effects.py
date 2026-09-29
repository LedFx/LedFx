import logging
import random
from collections.abc import Collection, Iterable, Mapping
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.effects import DummyEffect

_LOGGER = logging.getLogger(__name__)


def process_fallback(fallback):
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
        if fallback is False:
            fallback = None
        elif fallback is True:
            # set up a long default time for fallback, this is to prevent
            # getting stuck in a temporary effect if the caller forgets to
            # set a time and the effect has not self triggered exit
            fallback = 300.0
    elif isinstance(fallback, (int, float)) and fallback > 0:
        pass
    else:
        fallback = None
    return fallback


def randomize_effect_config(
    schema: Mapping[object, object], ignored: Collection[str]
) -> dict[str, object]:
    """Randomize supported settings without guessing values for unknown schemas."""
    result: dict[str, object] = {}
    for setting, validator in schema.items():
        name = setting.schema if isinstance(setting, vol.Marker) else setting
        if not isinstance(name, str) or name in ignored:
            continue
        if validator is bool:
            result[name] = random.choice([True, False])
        elif isinstance(validator, vol.In):
            container = validator.container
            if isinstance(container, Iterable):
                choices = list(container)
                if choices:
                    result[name] = random.choice(choices)
        elif isinstance(validator, vol.All):
            coerce_type: type[int | float] | None = None
            bounds: vol.Range | None = None
            for item in validator.validators:
                if isinstance(item, vol.Coerce):
                    if item.type is int:
                        coerce_type = int
                    elif item.type is float:
                        coerce_type = float
                elif isinstance(item, vol.Range):
                    bounds = item
            if bounds is None or coerce_type is None:
                continue
            lower, upper = bounds.min, bounds.max
            if not isinstance(lower, (int, float)) or not isinstance(
                upper, (int, float)
            ):
                continue
            if lower > upper:
                continue
            if coerce_type is int:
                if not isinstance(lower, int) or not isinstance(upper, int):
                    continue
                # Draw only from integers inside exclusive bounds.
                if not bounds.min_included:
                    lower += 1
                if not bounds.max_included:
                    upper -= 1
                if lower > upper:
                    continue
                value = random.randint(lower, upper)
            else:
                value = random.uniform(lower, upper)
            # Respect extra validators and exclusive bounds in the schema.
            try:
                result[name] = validator(value)
            except vol.Invalid:
                continue
    return result


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/effects"

    async def get(self, virtual_id) -> web.Response:
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

    async def put(self, virtual_id, request) -> web.Response:
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

        if not virtual.active_effect:
            return await self.invalid_request(
                f"Virtual {virtual_id} has no active effect"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        effect_config = data.get("config")
        effect_type = data.get("type")
        if effect_config is None:
            effect_config = {}
        if effect_config == "RANDOMIZE":
            effect_type = virtual.active_effect.type
            effect = self._ledfx.effects.get_class(effect_type)
            effect_config = randomize_effect_config(
                effect.schema().schema, ["brightness"]
            )

        fallback = process_fallback(data.get("fallback", None))

        if fallback is not None and virtual.streaming:
            error_message = (
                f"Unable to set effect: Virtual {virtual_id} being streamed to"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message, "error", resp_code=409)

        # See if virtual's active effect type matches this effect type,
        # if so update the effect config
        # otherwise, create a new effect and add it to the virtual

        try:
            # handling an effect update. nested if else and repeated code bleh. ain't a looker ;)
            if virtual.active_effect and virtual.active_effect.type == effect_type:
                # substring search to match any key of color
                # this handles special cases where we want to update an effect and also trigger
                # a transition by creating a new effect.
                # add color_blend and set to False in your effect to prevent effect recreation on color change
                # leave as a switch or add to HIDDEN_KEYS
                if virtual.active_effect.config.get("color_blend", True) and next(
                    (key for key in effect_config if "color" in key),
                    None,
                ):
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=effect_type,
                        config={
                            **virtual.active_effect.config,
                            **effect_config,
                        },
                    )
                    virtual.set_effect(effect, fallback=fallback)
                else:
                    effect = virtual.active_effect
                    virtual.active_effect.update_config(effect_config)

            # handling a new effect
            else:
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx, type=effect_type, config=effect_config
                )
                virtual.set_effect(effect, fallback=fallback)

        except (ValueError, RuntimeError) as msg:
            error_message = f"Unable to set effect: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "warning")

        virtual.update_effect_config(effect)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        effect_response = {}
        effect_response["config"] = effect.config
        effect_response["name"] = effect.name
        effect_response["type"] = effect.type

        response = {"status": "success", "effect": effect_response}
        return await self.bare_request_success(response)

    async def post(self, virtual_id, request) -> web.Response:
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

        effect_config = data.get("config")
        if effect_config is None:
            effect_config = virtual.get_effects_config(effect_type)
        elif effect_config == "RANDOMIZE":
            effect = self._ledfx.effects.get_class(effect_type)
            effect_config = randomize_effect_config(
                effect.schema().schema,
                ["brightness", "background_color", "background_brightness"],
            )

        # Create the effect and add it to the virtual
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_type, config=effect_config
        )

        fallback = process_fallback(data.get("fallback", None))

        if fallback is not None and virtual.streaming:
            error_message = (
                f"Unable to set effect: Virtual {virtual_id} is being streamed to"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message, "error", resp_code=409)

        try:
            virtual.set_effect(effect, fallback=fallback)
        except (ValueError, RuntimeError) as msg:
            error_message = f"Unable to set effect {effect} on {virtual_id}: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "error")

        virtual.update_effect_config(effect)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        effect_response = {}
        effect_response["config"] = effect.config
        effect_response["name"] = effect.name
        effect_response["type"] = effect.type

        response = {"status": "success", "effect": effect_response}
        return await self.bare_request_success(response)

    async def delete(self, virtual_id) -> web.Response:
        """
        Deletes a virtual effect with the given ID.

        Args:
            virtual_id (str): The ID of the virtual effect to delete.

        Returns:
            web.Response: The response indicating the success or failure of the deletion.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        virtual.clear_effect()

        virtual.virtual_cfg.pop("effect", None)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "effect": {}}
        return await self.bare_request_success(response)
