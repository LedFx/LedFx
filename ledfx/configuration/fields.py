"""Shared pydantic field types for LedFx configuration models.

Annotated rule: put Field()/annotated_types constraints BEFORE any
BeforeValidator, or pydantic emits raw ge/le instead of minimum/maximum.
"""

import ipaddress
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
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
X_READONLY = "readOnly"  # JSON Schema 2020-12: shown in the UI, not editable
X_RESTART = "x-ledfx-restart"  # changing this core field requires a restart
X_LEGACY_SOURCE = "x-ledfx-legacy-source"  # legacy: list this EnumSource's options
BACKEND_ONLY_KEYS = (X_REQUIRED, X_OMIT_DEFAULT, X_LEGACY, X_RESTART, X_LEGACY_SOURCE)


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
        # What pydantic emits for Literal[*options]: enum, or const for one option.
        return handler(core_schema.literal_schema(self.values()))


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
    """Runtime-dependent choices, read by validation and the legacy /api/schema."""

    options: Callable[[], Sequence[object] | dict[object, str]]
    names: Callable[[], list[str]] | None = None  # legacy /api/schema only
    validate: Callable[[object], object] | None = None


_ENUM_SOURCES: dict[str, EnumSource] = {}


def register_enum_source(name: str, source: EnumSource) -> None:
    _ENUM_SOURCES[name] = source


def get_enum_source(name: str) -> EnumSource | None:
    return _ENUM_SOURCES.get(name)


RUNTIME_CONTEXT = {"runtime": True}


@dataclass(frozen=True)
class FromSource:
    """Annotated metadata: the value is one of the live instances named name.

    JSON Schema: the base type plus x-ledfx-enum-source; the frontend reads the
    options from that instance's own endpoint, so the schema never depends on
    the running system. Validation runs only the source's validate hook, and only
    for runtime use: loading config.json must not query hardware or reject a
    stored value that is absent now (an unplugged port, a removed sound card);
    API writes pass context=RUNTIME_CONTEXT (see validate_dict(..., runtime=True));
    an update adds "fields" (the keys it changes) so stored values stay unchecked.
    The hook sees the value after type validation ("4" arrives as 4).
    legacy=True: the legacy /api/schema lists the source's options, as it did.
    """

    name: str
    legacy: bool = False

    def __get_pydantic_core_schema__(
        self, source: object, handler: Callable[[object], core_schema.CoreSchema]
    ) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            self._validate, handler(source)
        )

    def _validate(self, value: object, info: ValidationInfo) -> object:
        source = _ENUM_SOURCES.get(self.name)
        if source is None or source.validate is None:
            return value
        context = info.context or {}
        if not context.get("runtime"):
            return value
        # An update checks only the keys it changes, not stored ones. "fields"
        # holds top-level keys only: a sourced field nested inside another model
        # would need a path-aware rule.
        if info.field_name not in context.get("fields", (info.field_name,)):
            return value
        return source.validate(value)

    def __get_pydantic_json_schema__(
        self, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = {**handler(schema), X_ENUM_SOURCE: self.name}
        if self.legacy:
            json_schema[X_LEGACY_SOURCE] = self.name
        return json_schema


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
# A platform constant, not an instance: any int is accepted and clamped up, so
# the rates are examples (slider marks), not an enum.
Fps = Annotated[
    int,
    BeforeValidator(fps_validator),
    Field(examples=list(_utils.AVAILABLE_FPS)),
    JsonExtra({X_LEGACY_SOURCE: "fps"}),
]
VirtualId = Annotated[str, FromSource("virtuals")]
AudioDeviceIndex = Annotated[int | None, FromSource("audio_devices", legacy=True)]
SceneId = Annotated[str, FromSource("scenes")]
PlaylistId = Annotated[str, FromSource("playlists")]
DeviceId = Annotated[str, FromSource("devices")]
