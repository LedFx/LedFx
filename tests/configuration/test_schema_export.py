from typing import Annotated, Literal

import pytest
from pydantic import Field

from ledfx.configuration.fields import (
    X_ENUM_SOURCE,
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    X_RESTART,
    AudioDeviceIndex,
    CoercedFloat,
    Color,
    EnumSource,
    Fps,
    Gradient,
    IPv4,
    VirtualId,
    coerce,
    register_enum_source,
)
from ledfx.configuration.models import LedFxModel
from ledfx.configuration.schema import export_schema, legacy_schema


class Inner(LedFxModel):
    setting: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})


class Demo(LedFxModel):
    name: str = Field(description="Friendly name")
    mode: Literal["span", "copy"] = Field("span", json_schema_extra={X_REQUIRED: True})
    level: CoercedFloat = Field(0.5, ge=0, le=1, json_schema_extra={X_RESTART: True})
    color: Color = "#000000"
    gradient: Gradient = "#ff0000"
    rate: Fps = 60
    target: VirtualId = ""
    ip: IPv4 = "255.255.255.255"
    freqs: list[Annotated[int, Field(ge=0, le=9), coerce(int)]] = Field([1])
    anything: list[object] = Field(list[object]())
    blob: dict[str, object] = Field(dict[str, object]())
    nested: Inner = Inner(setting="x")
    advanced: bool | None = Field(
        None, json_schema_extra={X_OMIT_DEFAULT: True, X_LEGACY: {"description": False}}
    )
    newer: bool = Field(False, json_schema_extra={X_LEGACY: {"omit": True}})
    typed_list: list[Inner] = Field(
        list[Inner](), json_schema_extra={X_LEGACY: {"type": "array"}}
    )


@pytest.fixture(autouse=True)
def virtuals_source():
    from ledfx.configuration import fields

    previous = fields._ENUM_SOURCES.get("virtuals")
    register_enum_source(
        "virtuals",
        EnumSource(options=lambda: ["a", "b"], names=lambda: ["A", "B"]),
    )
    yield
    if previous is None:
        fields._ENUM_SOURCES.pop("virtuals", None)
    else:
        register_enum_source("virtuals", previous)


def test_legacy_shapes() -> None:
    props = legacy_schema(Demo)["properties"]
    assert props["name"] == {
        "type": "string",
        "title": "Name",
        "description": "Friendly name",
    }
    assert props["mode"] == {
        "type": "string",
        "enum": ["span", "copy"],
        "title": "Mode",
        "default": "span",
    }
    assert props["level"] == {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "title": "Level",
        "default": 0.5,
    }
    assert props["color"] == {
        "type": "color",
        "gradient": False,
        "title": "Color",
        "default": "#000000",
    }
    assert props["gradient"]["gradient"] is True
    assert props["rate"]["type"] == "int" and isinstance(props["rate"]["enum"], list)
    assert props["target"] == {
        "type": "string",
        "enum": ["a", "b"],
        "names": ["A", "B"],
        "title": "Target",
        "default": "",
    }
    assert props["ip"] == {
        "type": "string",
        "format": "ipv4",
        "title": "Ip",
        "default": "255.255.255.255",
    }
    assert props["freqs"] == {
        "type": "list",
        "validators": [{"type": "integer", "minimum": 0, "maximum": 9}],
        "title": "Freqs",
        "default": [1],
    }
    assert props["anything"] == {"type": "array", "title": "Anything", "default": []}
    assert props["blob"] == {"type": "dict", "title": "Blob", "default": {}}
    assert props["nested"] == {
        "properties": {"setting": {"type": "string", "title": "Setting"}},
        "title": "Nested",
        "default": {"setting": "x"},
    }
    assert props["advanced"] == {
        "type": "boolean",
        "title": "Advanced",
        "description": False,
    }
    assert "newer" not in props
    assert props["typed_list"] == {
        "type": "array",
        "title": "Typed List",
        "default": [],
    }
    assert legacy_schema(Demo)["required"] == ["name", "mode"]
    assert list(props)[:3] == ["name", "mode", "level"]


def test_legacy_order_and_extra_properties() -> None:
    out = legacy_schema(
        Demo,
        order=["level", "name", "hosts"],
        extra_properties={"hosts": {"type": "array", "title": "Hosts", "default": []}},
    )
    assert list(out["properties"])[:3] == ["level", "name", "hosts"]


def test_export_resolves_sources_and_strips_backend_keys() -> None:
    schema = export_schema(Demo)
    props = schema["properties"]
    assert props["target"]["enum"] == ["a", "b"]
    assert props["target"]["x-ledfx-enum-names"] == ["A", "B"]
    assert X_RESTART not in props["level"]
    assert X_REQUIRED not in props["mode"]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_export_without_resolve_keeps_source_name() -> None:
    props = export_schema(Demo, resolve=False)["properties"]
    assert "enum" not in props["target"]
    assert props["target"][X_ENUM_SOURCE] == "virtuals"
    assert X_RESTART not in props["level"]


class Sourced(LedFxModel):
    dev: str = Field("", json_schema_extra={X_ENUM_SOURCE: "nosuch"})


def test_export_missing_source_keeps_key_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    props = export_schema(Sourced)["properties"]
    assert "enum" not in props["dev"]
    assert props["dev"][X_ENUM_SOURCE] == "nosuch"
    assert "nosuch" in caplog.text


def test_export_empty_source_has_no_enum_but_legacy_is_empty_list() -> None:
    from ledfx.configuration import fields

    register_enum_source("nosuch", EnumSource(options=list))
    try:
        assert "enum" not in export_schema(Sourced)["properties"]["dev"]
        assert legacy_schema(Sourced)["properties"]["dev"]["enum"] == []
    finally:
        fields._ENUM_SOURCES.pop("nosuch", None)


def test_legacy_default_factory() -> None:
    class Fac(LedFxModel):
        items: list[str] = Field(default_factory=list)

    assert legacy_schema(Fac)["properties"]["items"]["default"] == []


def test_legacy_multi_type_union_raises() -> None:
    class U(LedFxModel):
        v: int | str = 1

    with pytest.raises(ValueError, match="U.v: unions of several types"):
        legacy_schema(U)


def test_export_nullable_source_puts_enum_in_the_non_null_branch() -> None:
    from ledfx.configuration import fields

    class Nullable(LedFxModel):
        dev: AudioDeviceIndex = None

    previous = fields._ENUM_SOURCES.get("audio_devices")
    register_enum_source(
        "audio_devices", EnumSource(options=lambda: {3: "Mic", 5: "Loopback"})
    )
    try:
        dev = export_schema(Nullable)["properties"]["dev"]
    finally:
        if previous is None:
            fields._ENUM_SOURCES.pop("audio_devices", None)
        else:
            register_enum_source("audio_devices", previous)
    # default null must stay valid: the enum only constrains the integer branch
    assert "enum" not in dev
    assert dev["anyOf"] == [{"type": "integer", "enum": [3, 5]}, {"type": "null"}]
    assert dev["default"] is None
    assert dev["x-ledfx-enum-names"] == ["Mic", "Loopback"]
