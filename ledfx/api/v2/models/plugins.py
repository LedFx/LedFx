"""v2 plugin configs: strict, closed variants derived from the plugin models.

Stored configs and v1 keep the open, coercing plugin models; v2
validates against a variant built from each one on first use:
- the same field names, types, defaults and constraints;
- ``extra="forbid"`` and ``strict=True``;
- the type coercions (``coerce(int)``, ``coerce(float)``, ...) dropped, and
  the other before-validators (colours, gradients, fps) kept as
  after-validators, so they still check the strictly typed value;
- strings with no other bound capped at ``MAX_TEXT`` characters.

Nothing here runs at import: this module may load before the plugin
registries. The unions load the plugin registries themselves, the first time
pydantic needs their schema.
"""

import copy
import operator
import types
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache, reduce
from typing import (
    TYPE_CHECKING,
    Annotated,
    Literal,
    NewType,
    Union,
    cast,
    get_args,
    get_origin,
)

from annotated_types import MaxLen
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    create_model,
)
from pydantic.fields import FieldInfo
from pydantic_core import CoreSchema, PydanticCustomError, core_schema

from ledfx.configuration.fields import Coercion, JsonExtra, OneOf
from ledfx.configuration.plugin import PluginConfig
from ledfx.utils import BaseRegistry

PluginKind = Literal["effect", "device", "integration"]

_PREFIX: Mapping[PluginKind, str] = {
    "effect": "Effect",
    "device": "Device",
    "integration": "Integration",
}
_CONFIG = ConfigDict(extra="forbid", strict=True, frozen=True)
# coerce(<one of these>) converts a type; strict validation replaces it.
_TYPE_COERCIONS: tuple[object, ...] = (int, float, str, bool)
MAX_TEXT = 8192

# Keys the frontend writes into effect configs that no effect model declares.
# Where they come from:
# - ledfx/configuration/presets.py ignores "advanced", "diag" and
#   "gradient_name" when comparing presets; Effect.Config declares the first two;
# - ledfx/utils.py generate_default_config writes "gradient_name" into presets;
# - the frontend (src/) sends only schema keys, plus "gradient_name" through
#   presets.
UI_ONLY_KEYS: Mapping[str, object] = {
    "gradient_name": Annotated[str, MaxLen(MAX_TEXT)] | None
}


def _strict_metadata(metadata: Sequence[object]) -> list[object]:
    kept: list[object] = []
    for item in metadata:
        if isinstance(item, BeforeValidator):
            func = item.func
            if isinstance(func, Coercion) and func.target in _TYPE_COERCIONS:
                continue  # a type coercion: strict validation replaces it
            # A check: run it on the strictly typed value.
            item = AfterValidator(func)
        kept.append(item)
    return kept


def _is_text(annotation: object) -> bool:
    """str, str | None, or a NewType of str (the typed ids)."""
    if get_origin(annotation) in (Union, types.UnionType):
        members = [m for m in get_args(annotation) if m is not type(None)]
        return len(members) == 1 and _is_text(members[0])
    while isinstance(annotation, NewType):
        annotation = annotation.__supertype__
    return annotation is str


def _unbounded_text(info: FieldInfo, metadata: Sequence[object]) -> bool:
    bounded = (MaxLen, OneOf, JsonExtra)
    return _is_text(info.annotation) and not any(
        isinstance(m, bounded) for m in metadata
    )


def _model(name: str, fields: Mapping[str, tuple[object, object]]) -> type[BaseModel]:
    # create_model's overloads can't take fields built at runtime
    build = cast("Callable[..., type[BaseModel]]", create_model)
    return build(name, __config__=_CONFIG, __module__=__name__, **fields)


def strict_variant(
    model: type[BaseModel],
    name: str,
    *,
    extra_fields: Mapping[str, object] | None = None,
    limits: Mapping[str, Sequence[object]] | None = None,
) -> type[BaseModel]:
    """model as a strict, closed model called name.

    extra_fields adds optional fields (None by default); limits adds
    constraints (annotated_types) to the named fields."""
    fields: dict[str, tuple[object, object]] = {}
    for field_name, info in model.model_fields.items():
        metadata = [
            *_strict_metadata(info.metadata),
            *(limits or {}).get(field_name, ()),
        ]
        if _unbounded_text(info, metadata):
            metadata.append(MaxLen(MAX_TEXT))
        variant = copy.copy(info)
        variant.metadata = metadata
        fields[field_name] = (info.annotation, variant)
    for key, annotation in (extra_fields or {}).items():
        fields.setdefault(key, (annotation, None))
    return _model(name, fields)


@cache
def plugin_variant(
    kind: PluginKind, type_id: str, model: type[PluginConfig]
) -> type[BaseModel]:
    """The v2 variant of a plugin's config model: EffectConfig_<type_id>,
    DeviceConfig_<type_id> or IntegrationConfig_<type_id>."""
    extra = UI_ONLY_KEYS if kind == "effect" else None
    return strict_variant(model, f"{_PREFIX[kind]}Config_{type_id}", extra_fields=extra)


class UnknownPlugin(BaseModel):
    """A stored plugin whose type is not registered (its module is gone or
    failed to load). Shown as stored; it cannot run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    config: dict[str, object]
    available: Literal[False] = False


def _registry(kind: PluginKind) -> Mapping[str, type[BaseRegistry]]:
    from ledfx.api.v2.core.registry import load_plugin_registries
    from ledfx.devices import Device
    from ledfx.effects import Effect
    from ledfx.integrations import Integration

    load_plugin_registries()  # idempotent: imports the plugin modules once
    base = {"effect": Effect, "device": Device, "integration": Integration}[kind]
    return base.registry()


@cache
def variants(kind: PluginKind) -> Mapping[str, type[BaseModel]]:
    """Every registered plugin's v2 variant, by type id (sorted)."""
    registry = _registry(kind)
    return {
        type_id: plugin_variant(kind, type_id, registry[type_id].config_model())
        for type_id in sorted(registry)
    }


def _subscript(form: object, key: object) -> object:
    """form[key] for a typing form: Literal[value] with a runtime value is not
    a static type, so the checker is told it is a plain subscript."""
    return cast("Mapping[object, object]", form)[key]


def _literal(value: str) -> object:
    return _subscript(Literal, value)


def _union(members: Sequence[type[BaseModel]]) -> object:
    return reduce(operator.or_, members)


@cache
def state_models(kind: PluginKind) -> Mapping[str, type[BaseModel]]:
    """{type: <Kind>State_<type>}: a model of {type, config} per plugin."""
    return {
        type_id: _model(
            f"{_PREFIX[kind]}State_{type_id}",
            {"type": (_literal(type_id), ...), "config": (variant, ...)},
        )
        for type_id, variant in variants(kind).items()
    }


@cache
def state_union(kind: PluginKind) -> object:
    """The <Kind>State_<type> models as one union, discriminated by type."""
    union = _union(list(state_models(kind).values()))
    return _subscript(Annotated, (union, Field(discriminator="type")))


def effect_state_union() -> object:
    return state_union("effect")


@cache
def effect_config_union() -> object:
    """Any effect's EffectConfig_<type> (no discriminator: configs have no type)."""
    return _union(list(variants("effect").values()))


def _partial(variant: type[BaseModel]) -> type[BaseModel]:
    """variant with every field optional: the same annotations and checks (so
    null stays refused), no null branch in the schema (as Partial[M])."""
    fields: dict[str, tuple[object, object]] = {}
    for name, info in variant.model_fields.items():
        optional = copy.copy(info)
        if optional.is_required():
            optional.default = None
        fields[name] = (info.annotation, optional)
    return _model(f"{variant.__name__}_Partial", fields)


@cache
def effect_config_partial_union() -> object:
    """Any subset of any effect's settings (documents PATCH .../effect)."""
    return _union([_partial(v) for v in variants("effect").values()])


def effect_state(type_id: str, config: Mapping[str, object]) -> BaseModel:
    """A stored or running effect as v2 shows it: EffectState_<type>, or
    UnknownPlugin when the type is not registered. Built without validation,
    so an odd stored value is shown as it is rather than failing the request;
    keys the variant does not declare are left out."""
    model = state_models("effect").get(type_id)
    if model is None:
        return UnknownPlugin(type=type_id, config=dict(config))
    variant = variants("effect")[type_id]
    declared = {k: v for k, v in config.items() if k in variant.model_fields}
    settings = variant.model_construct(_fields_set=None, **declared)
    return model.model_construct(type=type_id, config=settings)


@dataclass(frozen=True)
class _Lazy:
    """Annotated metadata: the schema of build(), made when pydantic first
    needs it (models using it set defer_build=True), not at import."""

    build: Callable[[], object]

    def __get_pydantic_core_schema__(
        self, source: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return handler.generate_schema(self.build())


def _json_object(value: object) -> object:
    if not isinstance(value, dict):
        raise PydanticCustomError("model_type", "Input should be an object")
    return value


@dataclass(frozen=True)
class _ObjectDocumentedAs:
    """Annotated metadata: accept any JSON object, document build()'s schema.

    For a config whose model depends on a sibling field (the effect type): the
    handler validates it against that model, so errors name the real fields."""

    build: Callable[[], object]

    def __get_pydantic_core_schema__(
        self, source: object, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            _json_object,
            json_schema_input_schema=handler.generate_schema(self.build()),
        )


if TYPE_CHECKING:
    EffectState = BaseModel
    EffectConfigBody = dict[str, object]
    EffectConfigPatchBody = dict[str, object]
else:
    EffectState = Annotated[object, _Lazy(effect_state_union)]
    EffectConfigBody = Annotated[
        dict[str, object], _ObjectDocumentedAs(effect_config_union)
    ]
    EffectConfigPatchBody = Annotated[
        dict[str, object], _ObjectDocumentedAs(effect_config_partial_union)
    ]
