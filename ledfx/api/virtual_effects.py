import logging
import math
import random
from collections.abc import Collection
from json import JSONDecodeError
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin

import annotated_types
from aiohttp import web
from pydantic import BaseModel, BeforeValidator, ValidationError
from pydantic.fields import FieldInfo

from ledfx.api import RestEndpoint
from ledfx.configuration.fields import OneOf
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


def _field_metadata(info: FieldInfo) -> list[object]:
    """Constraints on the field plus those inside an ``Annotated[...] | None``."""
    found = list(info.metadata)
    for arg in get_args(info.annotation):
        found.extend(getattr(arg, "__metadata__", ()))
    return found


def _base_type(info: FieldInfo) -> object:
    """The annotation without ``| None`` and ``Annotated[...]`` wrappers."""
    annotation = info.annotation
    args = [a for a in get_args(annotation) if a is not type(None)]
    if get_origin(annotation) in (Union, UnionType) and len(args) == 1:
        annotation = args[0]
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _choices(info: FieldInfo) -> list[object]:
    for meta in _field_metadata(info):
        if isinstance(meta, OneOf):
            return meta.values()
    base = _base_type(info)
    if get_origin(base) is Literal:
        return list(get_args(base))
    return []


def _bounds(info: FieldInfo) -> tuple[float, bool, float, bool] | None:
    """(lower, lower_exclusive, upper, upper_exclusive), or None if not bounded."""
    lower: float | None = None
    upper: float | None = None
    lower_open = upper_open = False
    for meta in _field_metadata(info):
        if isinstance(meta, (annotated_types.Ge, annotated_types.Gt)):
            value = meta.ge if isinstance(meta, annotated_types.Ge) else meta.gt
            if isinstance(value, (int, float)):
                lower, lower_open = value, isinstance(meta, annotated_types.Gt)
        elif isinstance(meta, (annotated_types.Le, annotated_types.Lt)):
            value = meta.le if isinstance(meta, annotated_types.Le) else meta.lt
            if isinstance(value, (int, float)):
                upper, upper_open = value, isinstance(meta, annotated_types.Lt)
    if lower is None or upper is None or lower > upper:
        return None
    if lower == upper and (lower_open or upper_open):
        return None
    return lower, lower_open, upper, upper_open


def randomize_effect_config(
    model: type[BaseModel], ignored: Collection[str]
) -> dict[str, object]:
    """Randomize supported settings without guessing values for unknown fields.

    Booleans and choices always; numbers only for coerced fields with both
    bounds (CoercedInt/CoercedFloat with ge/le or gt/lt).
    Every value is checked against the field, so exclusive bounds and extra
    validators are respected.
    """
    result: dict[str, object] = {}
    for name, info in model.model_fields.items():
        if name in ignored:
            continue
        base = _base_type(info)
        choices = _choices(info)
        value: object
        if base is bool:
            value = random.choice([True, False])
        elif choices:
            value = random.choice(choices)
        elif base in (int, float) and any(
            isinstance(m, BeforeValidator) for m in _field_metadata(info)
        ):
            bounds = _bounds(info)
            if bounds is None:
                continue
            lower, lower_open, upper, upper_open = bounds
            if base is int:
                low = math.floor(lower) + 1 if lower_open else math.ceil(lower)
                high = math.ceil(upper) - 1 if upper_open else math.floor(upper)
                if low > high:
                    continue
                value = random.randint(low, high)
            else:
                value = random.uniform(lower, upper)
                # uniform() can return an endpoint; step inside an exclusive one.
                if lower_open and value <= lower:
                    value = math.nextafter(lower, upper)
                if upper_open and value >= upper:
                    value = math.nextafter(upper, lower)
        else:
            continue
        try:
            model.model_validate({name: value})
        except ValidationError as err:
            if any(e["loc"][:1] == (name,) for e in err.errors()):
                continue
        result[name] = value
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
                effect.config_model(), ["brightness"]
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
                if getattr(virtual.active_effect.config, "color_blend", True) and next(
                    (key for key in effect_config if "color" in key),
                    None,
                ):
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=effect_type,
                        config={
                            **virtual.active_effect.config.as_dict(),
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

        except ValidationError as err:
            return await self.validation_error(err)
        except (ValueError, RuntimeError) as msg:
            error_message = f"Unable to set effect: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "warning")

        virtual.update_effect_config(effect)

        self._ledfx.config_store.request_save()

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
                effect.config_model(),
                ["brightness", "background_color", "background_brightness"],
            )

        # Create the effect and add it to the virtual
        try:
            effect = self._ledfx.effects.create(
                ledfx=self._ledfx, type=effect_type, config=effect_config
            )
        except ValidationError as err:
            return await self.validation_error(err)

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

        self._ledfx.config_store.request_save()

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

        entry = virtual.entry
        if entry is not None:
            entry.effect = None

        self._ledfx.config_store.request_save()

        response = {"status": "success", "effect": {}}
        return await self.bare_request_success(response)
