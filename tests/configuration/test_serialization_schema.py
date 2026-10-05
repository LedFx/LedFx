"""Config models have real serialization-mode JSON Schemas, and
fields marked X_OMIT_DEFAULT still leave every dump while None."""

from collections.abc import Iterator

from pydantic import Field

from ledfx.configuration.fields import X_LEGACY, X_OMIT_DEFAULT, X_REQUIRED
from ledfx.configuration.models import LedFxModel, MelbankConfig, omits_default
from ledfx.configuration.plugin import PluginConfig
from ledfx.configuration.schema import strip_backend_keys
from tests.configuration.model_schema import _registry_by_kind


def _subclasses(cls: type[LedFxModel]) -> Iterator[type[LedFxModel]]:
    for sub in cls.__subclasses__():
        yield sub
        yield from _subclasses(sub)


def _all_models() -> list[type[LedFxModel]]:
    _registry_by_kind()  # imports every plugin module, defining its Config
    return sorted(
        set(_subclasses(LedFxModel)), key=lambda m: f"{m.__module__}.{m.__qualname__}"
    )


def test_no_config_model_has_an_empty_serialization_schema() -> None:
    models = _all_models()
    assert PluginConfig in models
    empty = [
        m.__qualname__
        for m in models
        if m.model_json_schema(mode="serialization") == {}
    ]
    assert empty == []


def test_every_marked_field_is_excluded_when_none() -> None:
    unmarked = [
        f"{m.__qualname__}.{name}"
        for m in _all_models()
        for name, info in m.model_fields.items()
        if omits_default(info) and info.exclude_if is None
    ]
    assert unmarked == []


def test_marked_field_is_omitted_while_none() -> None:
    assert "name" not in MelbankConfig().model_dump()
    assert "name" not in MelbankConfig().model_dump(mode="json")
    assert MelbankConfig(name="low").model_dump()["name"] == "low"
    schema = MelbankConfig.model_json_schema(mode="serialization")
    assert "name" in schema["properties"]


def test_marked_field_is_omitted_in_subclasses_and_deferred_plugins() -> None:
    class Base(LedFxModel):
        note: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})

    class Child(Base):
        size: int = 1

    class Plugin(PluginConfig):
        advanced: bool | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})

    class SubPlugin(Plugin):
        speed: int = 2

    assert Child().model_dump() == {"size": 1}
    assert Child(note="x").model_dump() == {"note": "x", "size": 1}
    assert SubPlugin().model_dump() == {"speed": 2}
    assert SubPlugin(advanced=True).model_dump() == {"advanced": True, "speed": 2}


class _EarlyRef(LedFxModel):
    note: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})
    child: "_LateRef | None" = None  # defined below: the class starts incomplete


class _LateRef(LedFxModel):
    x: int = 1


def test_forward_reference_does_not_break_class_definition() -> None:
    # Defining _EarlyRef must not raise; once the reference resolves it dumps.
    _EarlyRef.model_rebuild()
    assert _EarlyRef().model_dump() == {"child": None}
    assert _EarlyRef(note="n").model_dump() == {"note": "n", "child": None}


def test_strip_backend_keys_removes_backend_markers_at_any_depth() -> None:
    schema = {
        "properties": {
            "name": {"type": "string", X_OMIT_DEFAULT: True},
            "ids": {"items": [{"x-ledfx-enum-source": "virtuals", X_REQUIRED: True}]},
        },
        X_LEGACY: {"omit": True},
    }
    assert strip_backend_keys(schema) == {
        "properties": {
            "name": {"type": "string"},
            "ids": {"items": [{"x-ledfx-enum-source": "virtuals"}]},
        }
    }
