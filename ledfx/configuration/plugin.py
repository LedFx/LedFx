"""Plugin (effect/device/integration) config models.

vol_to_model and the mapping shim on PluginConfig are transitional: layers
10-12 replace auto-converted models with source-declared ``Config`` classes
and layer 13 deletes both.
"""

import inspect
from collections.abc import Iterable
from typing import (
    Annotated,
    Any,
    Generic,
    Literal,
    NoReturn,
    Self,
    TypeVar,
    get_args,
    get_origin,
    overload,
)

import voluptuous as vol
from pydantic import ConfigDict, Field, create_model
from pydantic.json_schema import JsonDict
from typing_extensions import override

from ledfx.configuration.fields import (
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    AudioDeviceIndex,
    Color,
    Fps,
    Gradient,
    IPv4,
    OneOf,
    VirtualId,
    coerce,
)
from ledfx.configuration.models import LedFxModel, omits_default


class PluginConfig(LedFxModel):
    """Base for plugin config models: frozen, and keeps unknown (UI-only) keys."""

    # defer_build: ~100 plugin models are defined at import; build each on first use.
    model_config = ConfigDict(extra="allow", frozen=True, defer_build=True)

    @classmethod
    @override
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        # voluptuous Schema.extend semantics: a redeclared key moves to the
        # subclass position (pydantic would keep the parent's slot). Field order
        # is user-visible in /api/schema and the frontend forms.
        super().__pydantic_init_subclass__(**kwargs)
        own = [n for n in inspect.get_annotations(cls) if n in cls.__pydantic_fields__]
        inherited = {n: f for n, f in cls.__pydantic_fields__.items() if n not in own}
        if list(cls.__pydantic_fields__) != [*inherited, *own]:
            cls.__pydantic_fields__ = {
                **inherited,
                **{n: cls.__pydantic_fields__[n] for n in own},
            }
            cls.model_rebuild(force=True)

    def _present(self, key: str) -> bool:
        fields = type(self).model_fields
        if key in fields:
            return not (omits_default(fields[key]) and getattr(self, key) is None)
        return key in (self.model_extra or {})

    def _value(self, key: str) -> object:
        # Extras come from model_extra, never getattr: an extra key named like a
        # model attribute ("keys", "get", "json") would return the attribute.
        if key in type(self).model_fields:
            return getattr(self, key)
        return (self.model_extra or {})[key]

    def as_dict(self, mode: Literal["python", "json"] = "python") -> dict[str, object]:
        """Plain dict shaped like the old voluptuous output (LedFxModel's
        serializer already drops unset optionals)."""
        return self.model_dump(mode=mode)

    def with_values(self, **changes: object) -> Self:
        return type(self).model_validate({**self.as_dict(), **changes})

    # ---- transitional dict-style access (deleted in layer 13) ---------------
    # Returns Any on purpose: untyped plugin code reads self._config["k"] until
    # layers 10-12 rewrite it to typed attributes; `object` would add errors there.
    def __getitem__(self, key: str) -> Any:  # pyrefly: ignore[explicit-any]
        if not self._present(key):
            raise KeyError(key)
        return self._value(key)

    def get(self, key: str, default: object = None) -> Any:  # pyrefly: ignore[explicit-any]
        return self._value(key) if self._present(key) else default

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self._present(key)

    def keys(self) -> list[str]:
        return list(self.as_dict())


C_co = TypeVar("C_co", bound=PluginConfig, covariant=True)


class TypedConfig(Generic[C_co]):
    """``config = TypedConfig(Config)``: typed, read-only access to ``_config``."""

    def __init__(self, model: type[C_co]) -> None:
        self.model = model

    @overload
    def __get__(self, obj: None, owner: type) -> "TypedConfig[C_co]": ...
    @overload
    def __get__(self, obj: object, owner: type) -> C_co: ...
    def __get__(self, obj: object | None, owner: type) -> "TypedConfig[C_co] | C_co":
        if obj is None:
            return self
        try:
            return obj.__dict__["_config"]
        except KeyError:
            # Not set yet (before __init__ or object.__new__ in tests): behave
            # like a missing attribute so hasattr/getattr defaults work.
            raise AttributeError("config") from None

    def __set__(self, obj: object, value: object) -> NoReturn:
        # Data descriptor on purpose: `plugin.config = x` must not silently
        # shadow the typed view. Change config through update_config().
        raise AttributeError("config is read-only; use update_config()")


# ---- voluptuous -> pydantic (transitional) ---------------------------------
# The annotations below are built at runtime from voluptuous schemas, which a
# static checker cannot follow; those lines carry targeted pyrefly ignores.
Bounds = dict[str, int | float]  # ge / gt / le / lt
Converted = tuple[object, Bounds, JsonDict]  # annotation, bounds, json extra

_BY_NAME: dict[str, object] = {
    "validate_color": Color,
    "validate_gradient": Gradient,
    "fps_validator": Fps,
    "virtual_id_validator": VirtualId,
    "device_index_validator": AudioDeviceIndex,
    "validate_ipv4_address": IPv4,
}


def _element_type(options: list[object]) -> object:
    kinds = {type(o) for o in options}
    return kinds.pop() if len(kinds) == 1 else object


def _options(validator: vol.In) -> list[object]:
    container = validator.container
    return list(container) if isinstance(container, Iterable) else []


def _one_of(base: object, options: list[object]) -> object:
    return Annotated[base, OneOf(tuple(options))]  # pyrefly: ignore[not-a-type]


def _constrained(annotation: object, field: object) -> object:
    """Annotated[T, Field(...), *rest]: constraints before any BeforeValidator,
    or pydantic emits raw ge/le instead of minimum/maximum."""
    if get_origin(annotation) is Annotated:
        base, *metadata = get_args(annotation)
        return Annotated[(base, field, *metadata)]
    return Annotated[annotation, field]  # pyrefly: ignore[not-a-type]


def _field(
    default: object, description: str | None, extra: JsonDict | None, bounds: Bounds
) -> object:
    return Field(
        default,
        description=description,
        json_schema_extra=extra,
        ge=bounds.get("ge"),
        gt=bounds.get("gt"),
        le=bounds.get("le"),
        lt=bounds.get("lt"),
    )


def _convert(validator: object, where: str) -> Converted:
    if isinstance(validator, vol.All):
        annotation: object = None
        bounds: Bounds = {}
        extra: JsonDict = {}
        in_options: list[object] | None = None
        for part in validator.validators:
            if isinstance(part, vol.In):
                in_options = _options(part)
                continue
            sub_annotation, sub_bounds, sub_extra = _convert(part, where)
            if sub_annotation is not None:
                annotation = sub_annotation
            bounds.update(sub_bounds)
            extra.update(sub_extra)
        if in_options is not None:
            base = annotation if annotation is not None else _element_type(in_options)
            annotation = _one_of(base, in_options)
        return annotation, bounds, extra
    if isinstance(validator, vol.Coerce):
        target = validator.type
        return Annotated[target, coerce(target)], {}, {}  # pyrefly: ignore[not-a-type]
    if isinstance(validator, vol.Range):
        range_bounds: Bounds = {}
        if isinstance(validator.min, (int, float)):
            range_bounds["ge" if validator.min_included else "gt"] = validator.min
        if isinstance(validator.max, (int, float)):
            range_bounds["le" if validator.max_included else "lt"] = validator.max
        return None, range_bounds, {}
    if isinstance(validator, vol.In):
        options = _options(validator)
        return _one_of(_element_type(options), options), {}, {}
    name = getattr(validator, "__name__", None)
    if isinstance(name, str) and name in _BY_NAME:
        return _BY_NAME[name], {}, {}
    if validator in (bool, str, int, float):
        return validator, {}, {}
    if validator is list:
        return list[object], {}, {}
    if validator is dict:
        return dict[str, object], {}, {}
    if isinstance(validator, list) and len(validator) == 1:
        item, item_bounds, _ = _convert(validator[0], where)
        item_field = _field(..., None, None, item_bounds)
        return list[_constrained(item, item_field)], {}, {}  # pyrefly: ignore[invalid-annotation]
    raise TypeError(f"{where}: unsupported voluptuous validator {validator!r}")


def vol_to_model(
    name: str,
    schema: vol.Schema,
    bases: tuple[type[PluginConfig], ...] = (PluginConfig,),
) -> type[PluginConfig]:
    """Build a PluginConfig subclass equivalent to a voluptuous dict schema."""
    fields: dict[str, tuple[object, object]] = {}
    for key, validator in schema.schema.items():
        field_name = key.schema if isinstance(key, vol.Marker) else key
        annotation, bounds, extra = _convert(validator, f"{name}.{field_name}")
        extra = dict(extra)
        description = getattr(key, "description", None)
        if description is not None and not isinstance(description, str):
            extra[X_LEGACY] = {"description": description}
            description = None
        if isinstance(key, vol.Required):
            extra[X_REQUIRED] = True
        default = getattr(key, "default", vol.UNDEFINED)
        if default is not vol.UNDEFINED:
            # voluptuous stores defaults as factories
            value = default() if callable(default) else default
            fields[field_name] = (
                annotation,
                _field(value, description, extra or None, bounds),
            )
        elif isinstance(key, vol.Required):
            fields[field_name] = (
                annotation,
                _field(..., description, extra or None, bounds),
            )
        else:
            extra[X_OMIT_DEFAULT] = True
            fields[field_name] = (
                annotation | None,  # pyrefly: ignore[unsupported-operation]
                _field(None, description, extra, bounds),
            )
    # Field specs are runtime values; create_model's overloads cannot type them.
    return create_model(name, __base__=bases, __module__=__name__, **fields)  # pyrefly: ignore[no-matching-overload]
