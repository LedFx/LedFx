"""Random settings for an effect: the v1 and v2 "randomize" actions."""

import math
import random
from collections.abc import Collection
from types import UnionType
from typing import Annotated, Literal, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel, BeforeValidator, ValidationError
from pydantic.fields import FieldInfo

from ledfx.configuration.fields import OneOf


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
