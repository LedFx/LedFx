"""Plugin (effect/device/integration) config models."""

import inspect
from typing import Generic, Literal, NoReturn, Self, TypeVar, overload

from pydantic import ConfigDict
from typing_extensions import override

from ledfx.configuration.models import LedFxModel


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

    def as_dict(self, mode: Literal["python", "json"] = "python") -> dict[str, object]:
        """Plain dict shaped like the old voluptuous output (LedFxModel's
        serializer already drops unset optionals)."""
        return self.model_dump(mode=mode)

    def with_values(self, **changes: object) -> Self:
        return type(self).model_validate({**self.as_dict(), **changes})


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
