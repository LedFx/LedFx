"""v2 virtuals models: closed and bounded.

Request bodies are strict. Responses are built from the manager's objects
with model_construct (Virtual.of), and Virtual.config is a view without the
request bounds, so a stored value that breaks a v2 bound is shown as it is
(and still passes response validation) instead of failing the request.
"""

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Annotated, Self

from annotated_types import Ge, Le, MaxLen, MinLen
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from pydantic_core import InitErrorDetails, PydanticCustomError

from ledfx.api.v2.core.partial import PatchValidationError
from ledfx.api.v2.core.problem import validation_errors
from ledfx.api.v2.models.ids import DeviceIdParam, VirtualIdParam
from ledfx.api.v2.models.plugins import (
    EffectConfigBody,
    EffectConfigPatchBody,
    EffectState,
    UnknownPlugin,
    effect_state,
    strict_variant,
    variants,
)
from ledfx.color import validate_color
from ledfx.configuration.models import VirtualConfig as StoredVirtualConfig
from ledfx.effects import DummyEffect
from ledfx.errors import Invalid

if TYPE_CHECKING:
    from ledfx.virtuals import Virtual as VirtualObject

_CLOSED = ConfigDict(extra="forbid", frozen=True)
# Models holding an effect union: its schema is built on first use, after the
# plugin registries have loaded (see ledfx.api.v2.models.plugins).
_LAZY = ConfigDict(extra="forbid", frozen=True, defer_build=True)

MAX_PIXEL = 1_000_000
MAX_SEGMENTS = 4096
MAX_TARGETS = 1024

if TYPE_CHECKING:
    VirtualConfig = StoredVirtualConfig
    VirtualConfigView = StoredVirtualConfig
else:
    _VirtualConfigFields = strict_variant(
        StoredVirtualConfig,
        "VirtualConfig",
        limits={
            "name": (MinLen(1), MaxLen(128)),
            "grouping": (Le(4096),),
            "center_offset": (Ge(-MAX_PIXEL), Le(MAX_PIXEL)),
            "rows": (Ge(1), Le(4096)),
        },
    )

    class VirtualConfig(_VirtualConfigFields):
        """A virtual's settings. frequency_min must be below frequency_max,
        and rotate needs more than one row; neither is adjusted."""

        @model_validator(mode="after")
        def _consistent(self) -> Self:
            # The type and text of the manager's Invalid, which answers a
            # change that breaks a rule against a stored value.
            problems = []
            if self.frequency_min >= self.frequency_max:
                problems.append(
                    (
                        "frequency_min",
                        self.frequency_min,
                        "frequency_min must be below frequency_max",
                    )
                )
            if self.rotate != 0 and self.rows <= 1:
                problems.append(
                    ("rotate", self.rotate, "rotate needs more than one row")
                )
            if problems:
                raise ValidationError.from_exception_data(
                    "VirtualConfig",
                    [
                        InitErrorDetails(
                            type=PydanticCustomError("validation", msg),
                            loc=(field,),
                            input=value,
                        )
                        for field, value, msg in problems
                    ],
                )
            return self


# What a response holds: strict and closed, without the request bounds, so a
# config stored by v1 or an old file still validates.
if not TYPE_CHECKING:
    VirtualConfigView = strict_variant(StoredVirtualConfig, "VirtualConfigView")

ColorStr = Annotated[
    str, Field(min_length=1, max_length=256), AfterValidator(validate_color)
]
TypeId = Annotated[str, Field(min_length=1, max_length=128)]
Seconds = Annotated[float, Field(gt=0, le=86400)]
Millis = Annotated[float, Field(ge=0, le=60000)]
Fraction = Annotated[float, Field(ge=0, le=1)]
Pixel = Annotated[int, Field(ge=0, le=MAX_PIXEL)]
VirtualIds = Annotated[
    list[VirtualIdParam], Field(min_length=1, max_length=MAX_TARGETS)
]

# One entry of GET /virtuals/{virtual_id}/effects: a registered type's
# settings, or an UnknownPlugin for a type that is gone.
EffectHistoryItem = EffectState | UnknownPlugin


class VirtualSegment(BaseModel):
    """A run of one device's pixels, start and end inclusive."""

    model_config = _CLOSED

    device_id: DeviceIdParam
    start: Pixel
    end: Pixel
    invert: bool = False

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start > self.end:
            raise ValidationError.from_exception_data(
                "VirtualSegment",
                [
                    InitErrorDetails(
                        type=PydanticCustomError(
                            "inconsistent", "start must not be after end"
                        ),
                        loc=("start",),
                        input=self.start,
                    )
                ],
            )
        return self


class VirtualCreate(BaseModel):
    """POST /virtuals. The id comes from the name (made unique)."""

    model_config = _CLOSED

    config: VirtualConfig


def _segments(virtual: "VirtualObject") -> list[VirtualSegment]:
    return [
        VirtualSegment.model_construct(
            device_id=device_id, start=start, end=end, invert=invert
        )
        for device_id, start, end, invert in virtual.segments
    ]


class VirtualUpdate(BaseModel):
    """PATCH /virtuals/{virtual_id} (as Partial[VirtualUpdate]): any of these."""

    model_config = _CLOSED

    config: VirtualConfig
    segments: Annotated[list[VirtualSegment], Field(max_length=MAX_SEGMENTS)]
    active: bool

    @classmethod
    def of(cls, virtual: "VirtualObject") -> Self:
        """The virtual's current state: what a PATCH is applied to."""
        return cls.model_construct(
            config=VirtualConfig.model_construct(**virtual.config.model_dump()),
            segments=_segments(virtual),
            active=virtual.active,
        )


class VirtualUpdateView(VirtualUpdate):
    """VirtualUpdate with the config's request bounds left out: what a PATCH is
    checked against for the settings it does not change."""

    config: VirtualConfigView


def current_effect(virtual: "VirtualObject") -> BaseModel | None:
    """The running effect; else a stored effect whose type is not registered
    (which cannot run, so only the config shows it); else None."""
    effect = virtual.active_effect
    if effect is not None and not isinstance(effect, DummyEffect):
        return effect_state(effect.type, effect.config.as_dict(mode="json"))
    entry = virtual.entry
    if entry is not None and entry.effect is not None:
        state = effect_state(entry.effect.type, entry.effect.config)
        if isinstance(state, UnknownPlugin):
            return state
    return None


class Virtual(BaseModel):
    """A virtual: its settings, where its pixels go and what it shows."""

    model_config = _LAZY

    id: str
    name: str
    config: VirtualConfigView
    is_device: str | None = Field(
        description="The device's id when this is a device's own virtual"
    )
    auto_generated: bool
    segments: list[VirtualSegment]
    pixel_count: int
    active: bool
    streaming: bool
    last_effect: str | None
    effect: EffectState | UnknownPlugin | None

    @classmethod
    def of(cls, virtual: "VirtualObject") -> Self:
        entry = virtual.entry
        return cls.model_construct(
            id=virtual.id,
            name=virtual.name,
            config=VirtualConfigView.model_construct(**virtual.config.model_dump()),
            is_device=virtual.is_device or None,
            auto_generated=virtual.auto_generated,
            segments=_segments(virtual),
            pixel_count=virtual.pixel_count,
            active=virtual.active,
            streaming=virtual.streaming,
            last_effect=entry.last_effect if entry is not None else None,
            effect=current_effect(virtual),
        )


class EffectPut(BaseModel):
    """PUT /virtuals/{virtual_id}/effect: start an effect.

    config is checked against the type's settings; without it the type's
    stored settings are used. With fallback_s the current effect comes back
    after that many seconds."""

    model_config = _LAZY

    type: TypeId
    config: EffectConfigBody | None = None
    fallback_s: Seconds | None = None


class EffectPatch(BaseModel):
    """PATCH /virtuals/{virtual_id}/effect: change some settings of the
    running effect (checked against its type's settings)."""

    model_config = _LAZY

    config: EffectConfigPatchBody


class ClearEffects(BaseModel):
    """POST /virtuals/clear-effects: blank these virtuals (default: all)."""

    model_config = _CLOSED

    virtual_ids: VirtualIds | None = None


_GLOBAL_SETTINGS = (
    "gradient",
    "background_color",
    "background_brightness",
    "brightness",
    "flip",
    "mirror",
)


class ApplyConfig(BaseModel):
    """POST /virtuals/apply-config: write these settings into every running
    effect that has them (default: on all virtuals). flip and mirror are
    explicit booleans: v2 has no "toggle"."""

    model_config = _CLOSED

    virtual_ids: VirtualIds | None = None
    gradient: Annotated[str, Field(min_length=1, max_length=4096)] | None = None
    background_color: ColorStr | None = None
    background_brightness: Fraction | None = None
    brightness: Fraction | None = None
    flip: bool | None = None
    mirror: bool | None = None

    @model_validator(mode="after")
    def _one_setting(self) -> Self:
        if all(getattr(self, name) is None for name in _GLOBAL_SETTINGS):
            raise ValueError(f"Give at least one of {', '.join(_GLOBAL_SETTINGS)}")
        return self


class ApplyConfigCounts(BaseModel):
    """Effects updated, skipped (they have none of the settings) and failed
    (they refused the settings)."""

    model_config = _CLOSED

    updated: int
    skipped: int
    failed: int


class SetEffectAll(BaseModel):
    """POST /virtuals/set-effect: start one effect on these virtuals
    (default: all). Without config, the type's defaults start."""

    model_config = _LAZY

    type: TypeId
    config: EffectConfigBody | None = None
    virtual_ids: VirtualIds | None = None
    fallback_s: Seconds | None = None


class SetEffectAllCounts(BaseModel):
    """Per virtual: applied; blocked (streamed to, with a fallback); failed
    (refused the effect, e.g. no segments)."""

    model_config = _CLOSED

    applied: int
    blocked: int
    failed: int


class Oneshot(BaseModel):
    """A flash: ramp up, hold, fade out (milliseconds)."""

    model_config = _CLOSED

    color: ColorStr = "white"
    ramp_ms: Millis = 0
    hold_ms: Millis = 0
    fade_ms: Millis = 0
    brightness: Fraction = 1.0


class ForceColor(BaseModel):
    model_config = _CLOSED

    color: ColorStr


class Calibration(BaseModel):
    model_config = _CLOSED

    enabled: bool


class Highlight(BaseModel):
    """Light a device's pixels start..end (inclusive) on a calibrating virtual."""

    model_config = _CLOSED

    device_id: DeviceIdParam
    start: Pixel
    end: Pixel
    flip: bool = False

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start > self.end:
            raise ValueError("start must not be after end")
        return self


class CopyEffect(BaseModel):
    """POST /virtuals/{virtual_id}/copy-effect: start this virtual's effect,
    with its settings, on the targets."""

    model_config = _CLOSED

    targets: VirtualIds


def effect_variant(type_id: str) -> type[BaseModel]:
    """The v2 settings model of a registered effect type; Invalid (422 at
    body.type) for any other."""
    variant = variants("effect").get(type_id)
    if variant is None:
        raise Invalid(f"Unknown effect type: {type_id}", loc=("body", "type"))
    return variant


# Pydantic error types for a value outside a bound, as opposed to the wrong type.
_BOUNDS = frozenset(
    {
        "greater_than",
        "greater_than_equal",
        "less_than",
        "less_than_equal",
        "multiple_of",
        "too_short",
        "too_long",
        "string_too_short",
        "string_too_long",
        "string_pattern_mismatch",
        "finite_number",
    }
)


def checked_config(
    variant: type[BaseModel],
    config: Mapping[str, object],
    sent: Mapping[str, object],
) -> dict[str, object]:
    """Validate config strictly as variant; return the sent settings, as
    validated (colours normalised). A failing sent setting is the client's
    error (422 at body.config.<name>). A stored setting of the wrong type is a
    409; one outside its bounds is kept as it is (the response shows it)."""
    try:
        valid = variant.model_validate_json(json.dumps(config), strict=True)
    except ValidationError as err:
        errors = validation_errors(err, prefix=("body", "config"))
        mine = [e for e in errors if len(e.loc) < 3 or e.loc[2] in sent]
        if mine:
            raise PatchValidationError(mine, None) from None
        wrong = [e for e in errors if e.type not in _BOUNDS]
        if wrong:
            stored = ".".join(str(part) for part in wrong[0].loc[1:])
            raise PatchValidationError([], stored) from None
        # Only stored settings are out of bounds: check the rest without them.
        # No effect variant has a rule between settings, so the rest cannot
        # fail on a sent key (those are in mine above); a failure is stored.
        beyond = {e.loc[2] for e in errors}
        rest = {name: value for name, value in config.items() if name not in beyond}
        try:
            valid = variant.model_validate_json(json.dumps(rest), strict=True)
        except ValidationError:
            stored = ".".join(str(part) for part in errors[0].loc[1:])
            raise PatchValidationError([], stored) from None
    values = valid.model_dump()
    return {name: values[name] for name in sent}
