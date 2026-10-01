import json
import os

import pytest

from ledfx.configuration.migrations import (
    CURRENT_SCHEMA_VERSION,
    run_migrations,
    schema_version_of,
)
from ledfx.configuration.migrations.legacy import LEGACY_EFFECT_IDS, legacy_to_v1
from ledfx.configuration.migrations.v2 import SCENE_FIELDS
from ledfx.configuration.models import Scene

LEGACY_DIR = os.path.join(os.path.dirname(__file__), "legacy")
CURRENT_FIXTURES = os.path.join(os.path.dirname(__file__), "..", "configs")


def _load(path: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _strip_versions(data: dict[str, object]) -> dict[str, object]:
    return {
        k: v
        for k, v in data.items()
        if k not in ("configuration_version", "schema_version")
    }


@pytest.mark.parametrize("name", ["v0_displays", "v0_devices_only", "v2_3_5_equalizer"])
def test_legacy_port_matches_migrate_config_golden(name: str) -> None:
    raw = _load(os.path.join(LEGACY_DIR, f"{name}.json"))
    golden = _load(os.path.join(LEGACY_DIR, f"{name}.golden.json"))
    assert _strip_versions(legacy_to_v1(raw)) == _strip_versions(golden)


@pytest.mark.parametrize("name", sorted(os.listdir(CURRENT_FIXTURES)))
def test_current_236_configs_are_untouched(name: str) -> None:
    raw = _load(os.path.join(CURRENT_FIXTURES, name))
    assert raw["configuration_version"] == "2.3.6"
    assert _strip_versions(legacy_to_v1(raw)) == _strip_versions(raw)


def test_legacy_port_does_not_mutate_input() -> None:
    raw = _load(os.path.join(LEGACY_DIR, "v0_displays.json"))
    before = json.dumps(raw, sort_keys=True)
    legacy_to_v1(raw)
    assert json.dumps(raw, sort_keys=True) == before


def test_schema_version_of() -> None:
    assert schema_version_of({}) == 0
    assert schema_version_of({"schema_version": 1}) == 1
    assert schema_version_of({"schema_version": "1"}) == 0
    assert schema_version_of({"schema_version": True}) == 0


def test_run_migrations_sets_version_and_copies() -> None:
    raw: dict[str, object] = {"configuration_version": "2.3.6", "devices": []}
    out = run_migrations(raw)
    assert out["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "schema_version" not in raw


def test_run_migrations_skips_applied_steps() -> None:
    raw: dict[str, object] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "devices": [{"id": "x"}],
    }
    assert run_migrations(raw) == raw


def test_legacy_effect_ids_snapshot_is_frozen() -> None:
    assert isinstance(LEGACY_EFFECT_IDS, frozenset)
    assert {"rainbow", "equalizer2d", "singleColor"} <= LEGACY_EFFECT_IDS
    assert len(LEGACY_EFFECT_IDS) == 63


def _old(version: object | None = None, **extra: object) -> dict[str, object]:
    raw: dict[str, object] = {"crossfade": 1, "devices": [], **extra}
    if version is not None:
        raw["configuration_version"] = version
    return raw


def test_exactly_236_is_returned_unchanged() -> None:
    raw = _old("2.3.6")
    assert legacy_to_v1(raw) == raw


def test_2310_counts_as_newer_than_236() -> None:
    raw = _old("2.3.10")
    assert legacy_to_v1(raw) == raw


@pytest.mark.parametrize("version", ["not-a-version", 5, None, ["2.3.6"]])
def test_invalid_or_non_string_version_is_migrated_with_eq_fix(
    version: object,
) -> None:
    eq = {"ring": False, "center": False}
    raw = _old(
        version,
        virtuals=[
            {
                "id": "m",
                "config": {"name": "M"},
                "effect": {"type": "equalizer2d", "config": dict(eq)},
            }
        ],
    )
    raw["configuration_version"] = version
    out = legacy_to_v1(raw)
    assert "crossfade" not in out
    virtuals = out["virtuals"]
    assert isinstance(virtuals, list)
    effect = virtuals[0]["effect"]
    # InvalidVersion (str) and non-string (None/list) run the fix; the int 5
    # parses as "5" >= 2.3.6 so the fix is skipped.
    assert effect["config"].get("flip_vertical", False) is (version != 5)


def test_missing_version_with_virtuals_list() -> None:
    raw = _old(
        virtuals=[{"id": "v", "config": {"name": "V"}, "segments": []}],
        user_presets={},
    )
    out = legacy_to_v1(raw)
    assert "crossfade" not in out
    assert out["virtuals"] == [
        {"id": "v", "config": {"name": "V"}, "segments": [], "auto_generated": False}
    ]


def test_malformed_entries_pass_through_without_phantom_virtual() -> None:
    raw = _old(
        "1.0.0",
        devices=[
            "junk",
            {"id": "noname", "type": "wled", "config": {}},
            {"id": "ok", "type": "wled", "config": {"name": "Ok", "pixel_count": 3}},
        ],
        user_presets={"rainbow": {"p": "bad"}, "fire": "bad"},
        scenes={"s": {"name": "S", "virtuals": {"ok": "bad"}}, "t": "bad"},
    )
    out = legacy_to_v1(raw)
    devices = out["devices"]
    assert isinstance(devices, list)
    assert devices[0] == "junk"
    virtuals = out["virtuals"]
    assert isinstance(virtuals, list)
    assert [v["is_device"] for v in virtuals] == ["ok"]
    assert out["user_presets"] == {"rainbow": {"p": "bad"}, "fire": "bad"}
    assert out["scenes"] == {
        "s": {"name": "S", "virtuals": {"ok": "bad"}},
        "t": "bad",
    }


def test_run_migrations_from_version_skips_applied_steps() -> None:
    raw: dict[str, object] = {"devices": ["junk"], "crossfade": 1}
    out = run_migrations(raw, from_version=CURRENT_SCHEMA_VERSION)
    assert out == raw
    assert (
        run_migrations(raw, from_version=0)["schema_version"] == CURRENT_SCHEMA_VERSION
    )


def test_v2_drops_runtime_keys() -> None:
    out = run_migrations(
        {"schema_version": 1, "hosts": ["1.2.3.4"], "ledfx_presets": {}, "port": 1}
    )
    assert out == {"schema_version": 2, "port": 1}


def test_v2_scene_fields_match_the_scene_model() -> None:
    assert SCENE_FIELDS == frozenset(Scene.model_fields)


def _spotify_v1(integrations: list[object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scenes": {
            "s1": {
                "name": "S1",
                "virtuals": {},
                "abc-1000": ["abc", "Song", 1000],
                "x": [1],
            },
            "s2": {"name": "S2", "virtuals": {}},
        },
        "integrations": integrations,
    }


def test_v2_moves_spotify_triggers_replacing_the_stale_copy() -> None:
    stale: dict[str, object] = {
        "s1": {"name": "S1", "virtuals": {"v": 1}, "abc-1000": ["abc", "Song", 1]}
    }
    out = run_migrations(
        _spotify_v1(
            [
                {"id": "spotify", "type": "spotify", "data": stale},
                {"id": "qlc", "type": "qlc", "data": [1]},
            ]
        )
    )
    # "x" is not a trigger: it stays for the loader to quarantine.
    assert out["scenes"] == {
        "s1": {"name": "S1", "virtuals": {}, "x": [1]},
        "s2": {"name": "S2", "virtuals": {}},
    }
    assert out["integrations"] == [
        {
            "id": "spotify",
            "type": "spotify",
            "data": {"s1": {"abc-1000": ["abc", "Song", 1000]}},
        },
        {"id": "qlc", "type": "qlc", "data": [1]},
    ]


def test_v2_strips_and_logs_triggers_without_a_spotify_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    out = run_migrations(_spotify_v1([]))
    assert out["scenes"] == {
        "s1": {"name": "S1", "virtuals": {}, "x": [1]},
        "s2": {"name": "S2", "virtuals": {}},
    }
    assert out["integrations"] == []
    assert "abc-1000" in caplog.text
