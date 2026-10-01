import json
import pathlib
from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field

from ledfx.configuration import fields
from ledfx.configuration.fields import (
    X_ENUM_SOURCE,
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    X_RESTART,
    CoercedFloat,
    Color,
    EnumSource,
    Fps,
    FromSource,
    Gradient,
    IPv4,
    coerce,
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
    target: Annotated[str, FromSource("virtuals", legacy=True)] = ""
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


def _fake_source(
    monkeypatch: pytest.MonkeyPatch, name: str, source: EnumSource
) -> None:
    """Replace a registered source for one test; the real one comes back after."""
    import ledfx.virtuals  # noqa: F401 - registers the real source first

    monkeypatch.setitem(fields._ENUM_SOURCES, name, source)


@pytest.fixture(autouse=True)
def virtuals_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_source(
        monkeypatch,
        "virtuals",
        EnumSource(options=lambda: ["a", "b"], names=lambda: ["A", "B"]),
    )


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


def test_export_marks_sources_and_strips_backend_keys() -> None:
    schema = export_schema(Demo)
    props = schema["properties"]
    assert props["target"] == {
        "type": "string",
        "default": "",
        "title": "Target",
        X_ENUM_SOURCE: "virtuals",
    }
    assert X_RESTART not in props["level"]
    assert X_REQUIRED not in props["mode"]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


class Sourced(LedFxModel):
    dev: Annotated[str, FromSource("nosuch", legacy=True)] = ""


def test_legacy_missing_source_is_an_empty_enum_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert export_schema(Sourced)["properties"]["dev"][X_ENUM_SOURCE] == "nosuch"
    assert legacy_schema(Sourced)["properties"]["dev"]["enum"] == []
    assert "nosuch" in caplog.text


def test_legacy_default_factory() -> None:
    class Fac(LedFxModel):
        items: list[str] = Field(default_factory=list)

    assert legacy_schema(Fac)["properties"]["items"]["default"] == []


def test_legacy_multi_type_union_raises() -> None:
    class U(LedFxModel):
        v: int | str = 1

    with pytest.raises(ValueError, match="U.v: unions of several types"):
        legacy_schema(U)


@pytest.fixture
def fake_audio(monkeypatch: pytest.MonkeyPatch):
    from ledfx.effects.audio import AudioInputSource

    devices = {3: "WASAPI: Mic", 4: "MME: Line"}
    monkeypatch.setattr(
        AudioInputSource, "input_devices", staticmethod(lambda: devices)
    )
    return devices


@pytest.fixture
def fake_ports(monkeypatch: pytest.MonkeyPatch):
    import types

    import serial.tools.list_ports

    ports = [types.SimpleNamespace(device="/dev/ttyUSB0")]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)
    return ports


def test_audio_device_is_the_plain_optional_int_plus_marker(
    fake_audio: dict[int, str],
) -> None:
    from ledfx.configuration.models import AudioInputConfig

    class Ref(BaseModel):
        audio_device: int | None = None

    dev = export_schema(AudioInputConfig)["properties"]["audio_device"]
    assert dev == {
        **Ref.model_json_schema()["properties"]["audio_device"],
        X_ENUM_SOURCE: "audio_devices",
    }


def test_com_port_is_a_plain_string_plus_marker(fake_ports: list[object]) -> None:
    from ledfx.devices import SerialDevice

    com_port = export_schema(SerialDevice.Config)["properties"]["com_port"]
    assert com_port == {
        "default": "",
        "description": "COM port for Adalight compatible device",
        "title": "Com Port",
        "type": "string",
        X_ENUM_SOURCE: "com_ports",
    }


def test_fps_is_an_integer_with_examples_and_clamps_any_int() -> None:
    from ledfx.utils import AVAILABLE_FPS

    rate = export_schema(Demo)["properties"]["rate"]
    assert rate == {
        "type": "integer",
        "default": 60,
        "examples": list(AVAILABLE_FPS),
        "title": "Rate",
    }
    fps = list(AVAILABLE_FPS)
    for value in (-5, 0, fps[0] + 1, 10**6):
        clamped = Demo(name="x", rate=value).rate
        assert clamped == next((f for f in fps if f >= value), fps[-1])


def _served() -> str:
    from ledfx.api.schemas import build_schemas

    return json.dumps(build_schemas(None))


def test_export_is_independent_of_runtime_sources(
    monkeypatch: pytest.MonkeyPatch,
    fake_audio: dict[int, str],
    fake_ports: list[object],
) -> None:
    import types

    before = _served()
    fake_audio[7] = "USB: Interface"
    fake_ports.append(types.SimpleNamespace(device="/dev/ttyACM0"))
    _fake_source(monkeypatch, "virtuals", EnumSource(options=lambda: ["c"]))
    assert _served() == before


def _walk(node: object):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_marker_fields_carry_no_values(
    fake_audio: dict[int, str], fake_ports: list[object]
) -> None:
    from ledfx.api.schemas import build_schemas

    nodes = list(_walk(build_schemas(None)))
    marked = [n for n in nodes if X_ENUM_SOURCE in n]
    assert {n[X_ENUM_SOURCE] for n in marked} == {
        "audio_devices",
        "com_ports",
        "devices",
        "playlists",
        "scenes",
        "virtuals",
    }
    for node in marked:
        assert not [n for n in _walk(node) if "enum" in n or "const" in n], node
    assert not [n for n in nodes if "x-ledfx-enum-names" in n]


# Every config field that holds the id of a live instance, and its marker.
INSTANCE_ID_FIELDS = {
    ("audio", "properties", "audio_device"): "audio_devices",
    ("core", "$defs", "AudioConfig", "properties", "audio_device"): "audio_devices",
    ("core", "properties", "startup_scene_id"): "scenes",
    ("core", "properties", "startup_playlist_id"): "playlists",
    ("core", "$defs", "PlaylistItem", "properties", "scene_id"): "scenes",
    ("core", "$defs", "Scene", "properties", "virtuals", "propertyNames"): "virtuals",
    ("core", "$defs", "VirtualEntry", "properties", "is_device", "anyOf", 0): "devices",
    **{
        ("core", "$defs", model, "properties", "virtual_ids", "items"): "virtuals"
        for model in (
            "NowPlayingGradient",
            "NowPlayingTrackText",
            "NowPlayingAlbumArt",
            "Venue",
        )
    },
    ("effects", "radial", "properties", "source_virtual"): "virtuals",
    **{
        ("effects", "blender", "properties", key): "virtuals"
        for key in ("mask", "foreground", "background")
    },
    **{
        ("devices", device, "properties", "com_port"): "com_ports"
        for device in ("adalight",)
    },
}


# Instance ids deliberately left unmarked, and why.
NOT_MARKED = {
    ("core", "$defs", "VirtualEntry", "properties", "segments"): (
        "[device_id, start, end, reverse] rows: the segment editor edits them, not"
        " SchemaForm, and tighter validation of stored segments risks config loads"
    ),
    ("core", "$defs", "SceneVirtual", "properties", "preset"): (
        "a preset id is only meaningful per effect type; no single endpoint lists it"
    ),
    ("core", "$defs", "NowPlayingTrackText", "properties", "preset"): (
        "a preset id of the texter effect type; no single endpoint lists it"
    ),
}


def _schema_node(served: str, path: tuple[object, ...]) -> object:
    kind, *rest = path
    node = json.loads(served)[kind]
    if kind in ("effects", "devices"):
        node = node[rest.pop(0)]
    node = node["schema"]
    for key in rest:
        node = node[key]
    return node


def test_every_instance_id_field_carries_its_marker() -> None:
    served = _served()
    out = json.loads(served)
    serial = {t for t, e in out["devices"].items() if "com_port" in str(e)}
    assert serial == {"adalight"}  # a new serial device belongs in the table
    for path, marker in INSTANCE_ID_FIELDS.items():
        node = _schema_node(served, path)
        assert isinstance(node, dict) and node.get(X_ENUM_SOURCE) == marker, path
    for path in NOT_MARKED:
        assert not [n for n in _walk(_schema_node(served, path)) if X_ENUM_SOURCE in n]
    marked = sum(X_ENUM_SOURCE in n for n in _walk(out))
    assert marked == len(INSTANCE_ID_FIELDS)  # nothing marked that isn't listed


def test_dump_equals_served(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    import asyncio
    import sys

    from aiohttp.test_utils import make_mocked_request

    from ledfx.__main__ import main
    from ledfx.api.schemas import SchemasEndpoint
    from ledfx.api.schemas_kind import SchemasKindEndpoint
    from tests.configuration.legacy_schema import fake_ledfx

    dump = tmp_path / "schemas.json"
    monkeypatch.setattr(sys, "argv", ["ledfx", "--dump-schemas", str(dump)])
    assert main() == 0
    endpoint = SchemasEndpoint(fake_ledfx())
    response = asyncio.run(endpoint.get(make_mocked_request("GET", "/api/schemas")))
    served = json.loads(response.text or "")
    assert dump.read_text() == json.dumps(served, indent=2)  # same bytes, same order
    # Plugin order must not follow import order, which differs in a running server.
    for kind in ("devices", "effects", "integrations"):
        assert list(served[kind]) == sorted(served[kind]), kind
    by_kind = SchemasKindEndpoint(fake_ledfx())
    for kind in served:
        request = make_mocked_request(
            "GET", f"/api/schemas/{kind}", match_info={"kind": kind}
        )
        one = asyncio.run(by_kind.get(request))
        assert json.loads(one.text or "") == {kind: served[kind]}, kind


def test_legacy_audio_source_shape_unchanged(fake_audio: dict[int, str]) -> None:
    from ledfx.configuration.models import AudioInputConfig

    dev = legacy_schema(AudioInputConfig)["properties"]["audio_device"]
    assert dev == {
        "type": "string",
        "enum": fake_audio,
        "title": "Audio Device",
        "default": None,
    }


def test_legacy_com_port_lists_the_live_ports(fake_ports: list[object]) -> None:
    from ledfx.devices import SerialDevice

    com_port = legacy_schema(SerialDevice.Config)["properties"]["com_port"]
    assert list(com_port.items())[:2] == [
        ("type", "string"),
        ("enum", ["", "/dev/ttyUSB0"]),
    ]


def test_tempo_method_is_hidden_but_still_stored() -> None:
    # The legacy /api/schema always hid it: any string there crashes aubio.
    from ledfx.configuration.models import AudioConfig, LedFxConfig

    out = json.loads(_served())
    fields = [n["properties"] for n in _walk(out) if "properties" in n]
    assert any("pitch_method" in f for f in fields)  # the audio models are there
    assert not [f for f in fields if "tempo_method" in f]  # in audio and core $defs
    assert "Tempo Method" not in json.dumps(out)
    assert AudioConfig().tempo_method == "default"
    stored = {"audio": {"tempo_method": "specflux"}}
    assert LedFxConfig.model_validate(stored).audio.tempo_method == "specflux"
    assert LedFxConfig.model_validate(stored).model_dump()["audio"]["tempo_method"] == (
        "specflux"
    )


# Kinds whose legacy entry carried permitted_keys: what the UI may edit.
# Exposed, not permitted and scalar => readOnly (shown, not editable).
READ_ONLY = {
    "audio": {"sample_rate", "mic_rate", "fft_size", "audio_device_name"},
    "core": {"instance_id", "debug_asyncio"},
    "melbanks": set[str](),
    "melbank_collection": set[str](),
    "wled_preferences": set[str](),
}
# Not permitted, not scalar: left unmarked, because they are not form fields.
NOT_READ_ONLY = {
    ("core", name): "a nested collection with its own endpoint, not a form field"
    for name in (
        "devices",
        "virtuals",
        "audio",
        "melbanks",
        "user_presets",
        "scenes",
        "playlists",
        "integrations",
        "user_colors",
        "user_gradients",
        "wled_preferences",
        "sendspin_servers",
        "now_playing",
        "venues",
        "image_cache",
    )
}


def _scalar(prop: dict[str, object]) -> bool:
    branches = prop.get("anyOf", [prop])
    assert isinstance(branches, list)
    return all(
        b.get("type") in ("string", "integer", "number", "boolean", "null")
        for b in branches
        if isinstance(b, dict)
    )


def test_read_only_follows_permitted_keys() -> None:
    from ledfx.api.utils import PERMITTED_KEYS

    out = json.loads(_served())
    unmarked = set()
    for kind, expected in READ_ONLY.items():
        props = out[kind]["schema"]["properties"]
        permitted = set(PERMITTED_KEYS[kind])
        assert permitted <= set(props), kind
        read_only = {name for name, p in props.items() if p.get("readOnly") is True}
        assert read_only == expected, kind
        for name, prop in props.items():
            if name in permitted:
                assert "readOnly" not in prop, (kind, name)
            elif _scalar(prop):
                assert prop.get("readOnly") is True, (kind, name)
            else:
                assert "readOnly" not in prop, (kind, name)
                unmarked.add((kind, name))
    assert unmarked == set(NOT_READ_ONLY)
    assert "x-ledfx-readonly" not in json.dumps(out)


def test_read_only_does_not_leak_into_legacy() -> None:
    from tests.configuration.legacy_schema import render_legacy_schema

    legacy = render_legacy_schema()
    assert not [n for n in _walk(legacy) if "readOnly" in n or "x-ledfx-readonly" in n]
