"""The v2 plugin variants, over every registered plugin."""

import json
import os
import subprocess
import sys

import pytest
from annotated_types import MaxLen
from pydantic import TypeAdapter, ValidationError

from ledfx.api.v2.models.plugins import (
    MAX_TEXT,
    UI_ONLY_KEYS,
    EffectConfigBody,
    PluginKind,
    UnknownPlugin,
    effect_config_partial_union,
    effect_state,
    effect_state_union,
    plugin_variant,
    state_models,
    variants,
)
from ledfx.devices import Device
from ledfx.effects import Effect
from ledfx.integrations import Integration

KINDS: tuple[PluginKind, ...] = ("effect", "device", "integration")
PREFIX = {"effect": "Effect", "device": "Device", "integration": "Integration"}
BASES = {"effect": Effect, "device": Device, "integration": Integration}
# The registry sizes in the canonical environment (Linux, Python 3.12, every
# extra); elsewhere plugins with a missing optional dependency don't load.
COUNTS = {"effect": 63, "device": 18, "integration": 4}
CANONICAL = os.environ.get("LEDFX_CANONICAL_SPEC") == "1"
# Device configs require these (no defaults).
REQUIRED = {"name": "Strip", "ip_address": "192.168.1.50", "group_name": "Group"}
CASES = [(kind, type_id) for kind in KINDS for type_id in variants(kind)]


def _defaults(kind: PluginKind, type_id: str) -> dict[str, object]:
    """The plugin's own model's defaults, dumped to JSON types."""
    model = BASES[kind].registry()[type_id].config_model()
    required = {k: v for k, v in REQUIRED.items() if k in model.model_fields}
    return model.model_validate(required).model_dump(mode="json")


@pytest.mark.parametrize("kind", KINDS)
def test_every_registered_plugin_has_a_variant(kind: PluginKind) -> None:
    count = len(variants(kind))
    if CANONICAL:
        assert count == COUNTS[kind]
    else:
        assert 0 < count <= COUNTS[kind]


@pytest.mark.parametrize(("kind", "type_id"), CASES)
def test_variant_is_strict_closed_and_complete(kind: PluginKind, type_id: str) -> None:
    model = BASES[kind].registry()[type_id].config_model()
    variant = plugin_variant(kind, type_id, model)
    assert variant is variants(kind)[type_id]
    assert variant.__name__ == f"{PREFIX[kind]}Config_{type_id}"
    ui_keys = set(UI_ONLY_KEYS) if kind == "effect" else set()
    assert set(variant.model_fields) == set(model.model_fields) | ui_keys

    defaults = _defaults(kind, type_id)
    variant.model_validate_json(json.dumps(defaults), strict=True)

    with pytest.raises(ValidationError) as unknown:
        variant.model_validate_json(json.dumps({**defaults, "not_a_setting": 1}))
    assert unknown.value.errors()[0]["type"] == "extra_forbidden"

    floats = [n for n, f in variant.model_fields.items() if f.annotation is float]
    if floats:
        with pytest.raises(ValidationError) as text:
            variant.model_validate_json(json.dumps({**defaults, floats[0]: "0.5"}))
        assert text.value.errors()[0]["loc"] == (floats[0],)


def test_ui_only_keys_are_accepted_on_effects() -> None:
    rainbow = variants("effect")["rainbow"]
    config = rainbow.model_validate_json('{"gradient_name": "Rainbow"}', strict=True)
    assert config.model_dump()["gradient_name"] == "Rainbow"
    assert (
        "gradient_name"
        not in variants("device")[next(iter(variants("device")))].model_fields
    )


def test_type_coercions_are_dropped_and_checks_kept() -> None:
    single = variants("effect")["singleColor"]
    with pytest.raises(ValidationError):
        single.model_validate_json('{"brightness": "1"}', strict=True)
    # validate_color still runs, after strict str validation.
    assert (
        single.model_validate_json('{"color": "red"}').model_dump()["color"]
        == "#ff0000"
    )
    with pytest.raises(ValidationError):
        single.model_validate_json('{"color": "notacolor"}')


def test_unbounded_text_is_capped() -> None:
    texter = variants("effect")["texter2d"]
    assert MaxLen(MAX_TEXT) in texter.model_fields["text"].metadata
    # A typed id (a NewType of str) is text too.
    assert (
        MaxLen(MAX_TEXT) in variants("effect")["blender"].model_fields["mask"].metadata
    )
    with pytest.raises(ValidationError) as caught:
        texter.model_validate_json(json.dumps({"text": "x" * (MAX_TEXT + 1)}))
    assert caught.value.errors()[0]["type"] == "string_too_long"


def test_state_models_are_named_per_kind() -> None:
    assert state_models("effect")["rainbow"].__name__ == "EffectState_rainbow"
    device_type = next(iter(variants("device")))
    assert state_models("device")[device_type].__name__ == f"DeviceState_{device_type}"


def test_effect_state_union_is_discriminated_by_type() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(effect_state_union())
    state = adapter.validate_json('{"type": "rainbow", "config": {}}', strict=True)
    assert type(state).__name__ == "EffectState_rainbow"
    with pytest.raises(ValidationError) as caught:
        adapter.validate_json('{"type": "gone", "config": {}}')
    assert caught.value.errors()[0]["type"] == "union_tag_invalid"


def test_the_partial_union_accepts_any_subset() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(effect_config_partial_union())
    adapter.validate_json("{}", strict=True)
    adapter.validate_json('{"speed": 2.0}', strict=True)


def test_effect_state_of_a_registered_type_keeps_declared_keys() -> None:
    state = effect_state("rainbow", {"speed": 2.0, "gone_setting": 1})
    config = state.model_dump(mode="json")["config"]
    assert config["speed"] == 2.0
    assert "gone_setting" not in config


def test_an_unregistered_stored_type_is_an_unknown_plugin() -> None:
    state = effect_state("gone", {"x": 1})
    assert isinstance(state, UnknownPlugin)
    assert state.model_dump(mode="json") == {
        "type": "gone",
        "config": {"x": 1},
        "available": False,
    }
    with pytest.raises(ValidationError):
        UnknownPlugin.model_validate({"type": "gone", "config": {}, "available": True})


def test_the_partial_documents_no_null_and_refuses_it() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(effect_config_partial_union())
    adapter.validate_json("{}", strict=True)
    with pytest.raises(ValidationError):
        adapter.validate_json('{"speed": null}')
    speeds = [
        d["properties"]["speed"]
        for d in adapter.json_schema()["$defs"].values()
        if "speed" in d.get("properties", {})
    ]
    assert speeds
    assert all("null" not in json.dumps(v) for v in speeds)


def test_unbounded_optional_text_is_capped() -> None:
    token = variants("device")["nanoleaf"].model_fields["auth_token"]
    assert MaxLen(MAX_TEXT) in token.metadata


def test_a_config_body_must_be_an_object() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(EffectConfigBody)
    assert adapter.validate_json('{"speed": 1}') == {"speed": 1}
    with pytest.raises(ValidationError):
        adapter.validate_json("[1]")
    with pytest.raises(ValidationError):
        adapter.validate_json('"text"')


def test_importing_builds_nothing() -> None:
    code = (
        "from ledfx.api.v2.models import plugins as p;"
        "assert p.variants.cache_info().currsize == 0;"
        "assert p.state_models.cache_info().currsize == 0"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
