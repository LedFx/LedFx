"""Shared pydantic field types for LedFx configuration models.

Annotated rule: put Field()/annotated_types constraints BEFORE any
BeforeValidator, or pydantic emits raw ge/le instead of minimum/maximum.
"""

import ipaddress
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    GetJsonSchemaHandler,
    ValidationInfo,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError, core_schema

from ledfx import utils as _utils
from ledfx.color import validate_color, validate_gradient

X_ENUM_SOURCE = "x-ledfx-enum-source"
X_REQUIRED = "x-ledfx-required"  # legacy: key listed as required although defaulted
X_OMIT_DEFAULT = "x-ledfx-omit-default"  # legacy: optional key without a default
X_LEGACY = "x-ledfx-legacy"  # legacy: overrides for the legacy property
X_READONLY = "x-ledfx-readonly"  # core field the API may not write
X_RESTART = "x-ledfx-restart"  # changing this core field requires a restart
BACKEND_ONLY_KEYS = (X_REQUIRED, X_OMIT_DEFAULT, X_LEGACY, X_RESTART)


@dataclass(frozen=True)
class JsonExtra:
    """Annotated metadata: merge keys into the field's JSON Schema."""

    extra: dict[str, object]

    def __get_pydantic_json_schema__(
        self, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema.update(self.extra)
        return json_schema


@dataclass(frozen=True)
class OneOf:
    """Annotated metadata: value must be one of options (re-read on every use)."""

    options: Iterable[object] | Callable[[], Iterable[object]]

    def values(self) -> list[object]:
        source = self.options() if callable(self.options) else self.options
        return list(source)

    def __get_pydantic_core_schema__(
        self, source: object, handler: Callable[[object], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        def check(value: object) -> object:
            allowed = self.values()
            if value not in allowed:
                raise PydanticCustomError(
                    "one_of", "value must be one of {allowed}", {"allowed": allowed}
                )
            return value

        return core_schema.no_info_after_validator_function(check, handler(source))

    def __get_pydantic_json_schema__(
        self, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["enum"] = self.values()
        return json_schema


def coerce(target: Callable[[object], object]) -> BeforeValidator:
    """vol.Coerce(target): call target; TypeError/ValueError become invalid.

    OverflowError too (int(inf), float(10**400)), so it is a validation error.
    """

    def run(value: object) -> object:
        try:
            return target(value)
        except (TypeError, ValueError, OverflowError) as err:
            raise ValueError(str(err)) from err

    return BeforeValidator(run)


@dataclass(frozen=True)
class EnumSource:
    """Runtime-dependent choices (audio devices, virtuals, fps)."""

    options: Callable[[], list[object] | dict[object, str]]
    names: Callable[[], list[str]] | None = None
    validate: Callable[[object], object] | None = None


_ENUM_SOURCES: dict[str, EnumSource] = {}


def register_enum_source(name: str, source: EnumSource) -> None:
    _ENUM_SOURCES[name] = source


def get_enum_source(name: str) -> EnumSource | None:
    return _ENUM_SOURCES.get(name)


RUNTIME_CONTEXT = {"runtime": True}


def _via_source(name: str) -> Callable[[object, ValidationInfo], object]:
    """Apply a source's validate hook only when validating for runtime use.

    Loading config.json must not query hardware or rewrite stored values (the
    old core schema never validated audio at load); runtime sites pass
    context=RUNTIME_CONTEXT (see validate_dict(..., runtime=True)).
    """

    def check(value: object, info: ValidationInfo) -> object:
        source = _ENUM_SOURCES.get(name)
        if source is None or source.validate is None:
            return value
        if not (info.context or {}).get("runtime"):
            return value
        return source.validate(value)

    return check


def fps_validator(value: object) -> int:
    """Clamp an integer fps up to the nearest rate the clock can deliver."""
    if not isinstance(value, int):
        raise ValueError("fps must be an integer")  # noqa: TRY004
    return next(
        (f for f in _utils.AVAILABLE_FPS if f >= value),
        list(_utils.AVAILABLE_FPS.keys())[-1],
    )


def validate_ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as err:
        raise ValueError(f"Invalid IPv4 address: {value}") from err


register_enum_source("fps", EnumSource(options=lambda: list(_utils.AVAILABLE_FPS)))

CoercedInt = Annotated[int, coerce(int)]
CoercedFloat = Annotated[float, coerce(float)]
Color = Annotated[str, coerce(validate_color), JsonExtra({"format": "color"})]
Gradient = Annotated[str, coerce(validate_gradient), JsonExtra({"format": "gradient"})]
IPv4 = Annotated[str, AfterValidator(validate_ipv4), JsonExtra({"format": "ipv4"})]
Fps = Annotated[int, BeforeValidator(fps_validator), JsonExtra({X_ENUM_SOURCE: "fps"})]
VirtualId = Annotated[str, JsonExtra({X_ENUM_SOURCE: "virtuals"})]
AudioDeviceIndex = Annotated[
    int | None,
    BeforeValidator(_via_source("audio_devices")),
    JsonExtra({X_ENUM_SOURCE: "audio_devices"}),
]
