"""The v2 virtuals models: closed, strict and bounded."""

import json
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from ledfx.api.v2.models.plugins import UnknownPlugin
from ledfx.api.v2.models.virtuals import (
    ApplyConfig,
    CopyEffect,
    EffectPatch,
    EffectPut,
    Highlight,
    Oneshot,
    SetEffectAll,
    Virtual,
    VirtualConfig,
    VirtualCreate,
    VirtualSegment,
    VirtualUpdate,
)
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.plugin import PluginConfig
from tests.test_utilities.virtuals_core import add_virtual, running_core

SEGMENT = {"device_id": "strip", "start": 0, "end": 9}


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


def _rejects(model: type[BaseModel], body: object) -> list[tuple[object, ...]]:
    """The error locations when model refuses body (sent as JSON)."""
    with pytest.raises(ValidationError) as caught:
        model.model_validate_json(json.dumps(body), strict=True)
    return [tuple(e["loc"]) for e in caught.value.errors()]


@pytest.mark.parametrize(
    ("model", "body", "loc"),
    [
        (VirtualCreate, {"config": {"name": "A"}, "id": "a"}, ("id",)),
        (VirtualCreate, {"config": {"name": "A", "pixels": 5}}, ("config", "pixels")),
        (
            VirtualCreate,
            {"config": {"name": "A", "max_brightness": "1"}},
            ("config", "max_brightness"),
        ),
        (VirtualCreate, {"config": {"name": ""}}, ("config", "name")),
        (VirtualCreate, {"config": {"name": "x" * 129}}, ("config", "name")),
        (VirtualCreate, {"config": {"name": "A", "rows": 0}}, ("config", "rows")),
        (
            VirtualCreate,
            {"config": {"name": "A", "grouping": 4097}},
            ("config", "grouping"),
        ),
        (
            VirtualCreate,
            {"config": {"name": "A", "center_offset": 10**6 + 1}},
            ("config", "center_offset"),
        ),
        (
            VirtualCreate,
            {"config": {"name": "A", "icon_name": "x" * 8193}},
            ("config", "icon_name"),
        ),
        (VirtualSegment, {**SEGMENT, "start": -1}, ("start",)),
        (VirtualSegment, {**SEGMENT, "device_id": ""}, ("device_id",)),
        (VirtualSegment, [SEGMENT["device_id"], 0, 9, False], ()),
        (EffectPut, {"type": ""}, ("type",)),
        (EffectPut, {"type": "rainbow", "config": 5}, ("config",)),
        (EffectPut, {"type": "rainbow", "fallback_s": 0}, ("fallback_s",)),
        (EffectPut, {"type": "rainbow", "fallback_s": 86401}, ("fallback_s",)),
        (EffectPatch, {}, ("config",)),
        (SetEffectAll, {"type": "rainbow", "virtual_ids": []}, ("virtual_ids",)),
        (ApplyConfig, {"brightness": 1.5}, ("brightness",)),
        (ApplyConfig, {"background_color": "notacolor"}, ("background_color",)),
        (ApplyConfig, {"flip": "toggle"}, ("flip",)),
        (Oneshot, {"ramp_ms": 60001}, ("ramp_ms",)),
        (Oneshot, {"brightness": 1.5}, ("brightness",)),
        (Oneshot, {"hold_ms": "5"}, ("hold_ms",)),
        (Highlight, {**SEGMENT, "extra": 1}, ("extra",)),
        (CopyEffect, {"targets": []}, ("targets",)),
        (CopyEffect, {"targets": ["a"] * 1025}, ("targets",)),
    ],
)
def test_bad_bodies_are_refused_at_the_field(
    model: type[BaseModel], body: object, loc: tuple[object, ...]
) -> None:
    assert loc in _rejects(model, body)


def test_segments_are_capped() -> None:
    body = {"config": {"name": "A"}, "segments": [SEGMENT] * 4097, "active": True}
    assert ("segments",) in _rejects(VirtualUpdate, body)


def test_apply_config_needs_a_setting() -> None:
    assert _rejects(ApplyConfig, {"virtual_ids": ["a"]}) == [()]
    assert ApplyConfig.model_validate_json('{"flip": true}').flip is True


def test_colors_are_checked_and_normalized() -> None:
    assert Oneshot.model_validate_json('{"color": "red"}').color == "#ff0000"
    assert Oneshot().color == "white"


def test_highlight_range_is_ordered() -> None:
    assert _rejects(Highlight, {**SEGMENT, "start": 9, "end": 0}) == [()]


def test_virtual_config_is_the_strict_view() -> None:
    assert VirtualConfig.__name__ == "VirtualConfig"
    config = VirtualConfig.model_validate_json('{"name": "A"}', strict=True)
    assert config.model_dump()["max_brightness"] == 1.0


def _round_trip(value: Virtual) -> None:
    """What response validation does: encode, then decode strictly."""
    adapter: TypeAdapter[Virtual] = TypeAdapter(Virtual)
    adapter.validate_json(adapter.dump_json(value), strict=True)


def test_virtual_of_a_running_virtual(ledfx: MagicMock) -> None:
    bird = ledfx.virtuals.get_or_raise(VirtualIdStr("dj bird"))
    view = Virtual.of(bird)
    assert (view.id, view.name, view.effect, view.is_device) == (
        "dj bird",
        "dj bird",
        None,
        None,
    )
    assert view.segments == [VirtualSegment(device_id="strip", start=0, end=49)]
    _round_trip(view)
    ledfx.virtuals.set_effect(
        VirtualIdStr("dj bird"), "rainbow", PluginConfig.model_validate({"speed": 2.0})
    )
    view = Virtual.of(bird)
    assert type(view.effect).__name__ == "EffectState_rainbow"
    assert view.model_dump(mode="json")["effect"]["config"]["speed"] == 2.0
    assert view.last_effect == "rainbow"
    _round_trip(view)
    assert (
        Virtual.of(ledfx.virtuals.get_or_raise(VirtualIdStr("matrix"))).is_device
        == "matrix"
    )


def test_a_stored_unregistered_effect_shows_as_unknown(ledfx: MagicMock) -> None:
    """The stored effect's type is not registered."""
    old = add_virtual(
        ledfx, "old", "Old", [], effect={"type": "gone", "config": {"x": 1}}
    )
    view = Virtual.of(old)
    assert view.effect == UnknownPlugin(type="gone", config={"x": 1})
    _round_trip(view)


def test_the_effect_union_is_in_the_schema() -> None:
    schema = TypeAdapter(Virtual).json_schema(mode="serialization")
    defs = schema["$defs"]
    assert isinstance(defs, dict)
    assert {"EffectState_rainbow", "EffectConfig_rainbow", "UnknownPlugin"} <= set(defs)
    put = TypeAdapter(EffectPut).json_schema()
    assert "EffectConfig_rainbow" in put["$defs"]


def test_a_stored_virtual_beyond_the_request_bounds_is_shown(
    ledfx: MagicMock,
) -> None:
    """The response describes what is held, not what v2 accepts."""
    old = add_virtual(ledfx, "big", "n" * 300, [])
    # what v1 or an old file may have stored
    old._config = old.config.model_copy(update={"grouping": 5000})
    view = Virtual.of(old)
    assert (view.config.name, view.config.grouping) == ("n" * 300, 5000)
    view.model_dump(mode="json")
    _round_trip(view)


def test_a_wrongly_typed_stored_effect_that_does_not_run(ledfx: MagicMock) -> None:
    """No segments, so the effect never starts: it is not shown."""
    old = add_virtual(
        ledfx,
        "empty",
        "Empty",
        [],
        effect={"type": "rainbow", "config": {"speed": "fast"}},
    )
    view = Virtual.of(old)
    assert view.effect is None
    assert old.entry is not None
    assert view.last_effect == old.entry.last_effect
    view.model_dump(mode="json")
    _round_trip(view)


def test_a_wrongly_typed_stored_effect_that_runs_is_repaired(
    ledfx: MagicMock,
) -> None:
    old = add_virtual(
        ledfx,
        "typed",
        "Typed",
        [["strip", 0, 9, False]],
        effect={"type": "rainbow", "config": {"speed": "fast"}},
    )
    view = Virtual.of(old)
    assert type(view.effect).__name__ == "EffectState_rainbow"
    assert view.model_dump(mode="json")["effect"]["config"]["speed"] == 1.0
    _round_trip(view)
