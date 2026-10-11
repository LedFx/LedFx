import pytest
from pydantic import ValidationError

from ledfx.configuration.lenient import Quarantine, lenient_validate
from ledfx.configuration.models import (
    RESTART_FIELDS,
    Jitter,
    LedFxConfig,
    MelbanksConfig,
    Playlist,
    VirtualConfig,
    VirtualEntry,
)


def test_defaults_match_the_old_core_schema() -> None:
    cfg = LedFxConfig()
    assert (cfg.host, cfg.port, cfg.port_s) == ("0.0.0.0", 8888, 8443)
    assert cfg.visualisation_fps == 30 and cfg.global_brightness == 1.0
    assert cfg.devices == [] and cfg.scenes == {} and cfg.audio.min_volume == 0.2


def test_unknown_top_level_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LedFxConfig.model_validate({"bogus": 1})


def test_assignment_is_validated() -> None:
    cfg = LedFxConfig()
    with pytest.raises(ValidationError):
        cfg.visualisation_fps = 0


def test_virtual_entry_accepts_empty_effect_dict_as_none() -> None:
    entry = VirtualEntry.model_validate(
        {"id": "v", "config": {"name": "V"}, "segments": [], "effect": {}}
    )
    assert entry.effect is None


def test_playlist_jitter_bounds() -> None:
    with pytest.raises(ValidationError):
        Playlist.model_validate(
            {
                "id": "p",
                "name": "P",
                "items": [],
                "timing": {"jitter": {"factor_min": 2, "factor_max": 1}},
            }
        )


def test_restart_fields_match_legacy_list() -> None:
    assert RESTART_FIELDS == {
        "host",
        "port",
        "port_s",
        "dev_mode",
        "transmission_mode",
        "global_transitions",
        "melbank_collection",
    }


Record = tuple[str, object, list[str]]


def _collect() -> tuple[list[Record], Quarantine]:
    records: list[Record] = []

    def quarantine(path: str, value: object, errors: list[str]) -> None:
        records.append((path, value, errors))

    return records, quarantine


def test_lenient_defaults_bad_leaf_and_keeps_entry() -> None:
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig,
        {
            "virtuals": [
                {
                    "id": "v",
                    "config": {"name": "V", "transition_mode": "Wipe"},
                    "segments": [],
                }
            ]
        },
        "",
        q,
    )
    assert cfg is not None and cfg.virtuals[0].config.transition_mode == "Add"
    assert records[0][0] == "virtuals.0.config.transition_mode"


def test_lenient_drops_entry_missing_required_field() -> None:
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig,
        {
            "devices": [
                {"id": "a", "type": "wled", "config": {}},
                {"type": "wled", "config": {}},
            ]
        },
        "",
        q,
    )
    assert cfg is not None and [d.id for d in cfg.devices] == ["a"]
    assert records[0][0] == "devices.1"


def test_lenient_quarantines_unknown_keys() -> None:
    records, q = _collect()
    cfg = lenient_validate(LedFxConfig, {"port": 1, "mystery": {"x": 1}}, "", q)
    assert cfg is not None and cfg.port == 1 and records[0][0] == "mystery"


def test_lenient_never_shifts_scalar_lists() -> None:
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig, {"melbanks": {"max_frequencies": [350, "bad", 15000]}}, "", q
    )
    default = LedFxConfig().melbanks.max_frequencies
    assert cfg is not None and cfg.melbanks.max_frequencies == default
    assert [r[0] for r in records] == ["melbanks.max_frequencies"]


def test_lenient_quarantines_escalated_entry_once() -> None:
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig, {"virtuals": [{"id": "v", "config": {}, "segments": []}]}, "", q
    )
    assert cfg is not None and cfg.virtuals == []
    assert [r[0] for r in records] == ["virtuals.0"]


def test_lenient_keeps_list_integration_data() -> None:
    # QLC/MQTT integrations persist their data as a list
    records, q = _collect()
    entry: dict[str, object] = {
        "id": "q",
        "type": "qlc",
        "data": [{"event": "x"}],
        "config": {},
    }
    cfg = lenient_validate(LedFxConfig, {"integrations": [entry]}, "", q)
    assert cfg is not None and cfg.integrations[0].data == [{"event": "x"}]
    assert not records


def test_sendspin_defaults_track_the_sendspin_module() -> None:
    from ledfx.configuration.models import SendspinServerConfig
    from ledfx.sendspin.config import DEFAULT_CLIENT_NAME, DEFAULT_SERVER_URL

    cfg = SendspinServerConfig()
    assert (cfg.server_url, cfg.client_name) == (
        DEFAULT_SERVER_URL,
        DEFAULT_CLIENT_NAME,
    )


def test_lenient_drops_only_a_non_dict_entry_of_a_model_list() -> None:
    # legacy_to_v1 passes junk entries through; the other devices must survive
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig,
        {"devices": ["junk", {"id": "a", "type": "wled", "config": {}}]},
        "",
        q,
    )
    assert cfg is not None and [d.id for d in cfg.devices] == ["a"]
    assert records == [("devices.0", "junk", records[0][2])]


@pytest.mark.parametrize(
    ("field", "entries"),
    [
        ("devices", [{"type": "w", "config": {}}, {"type": "w", "config": {}}]),
        ("devices", ["junk", "junk2"]),
        (
            "virtuals",
            [
                {"id": "v", "config": {}, "segments": []},
                {"id": "w", "config": {}, "segments": []},
            ],
        ),
    ],
)
def test_lenient_removes_adjacent_bad_entries_once_each(
    field: str, entries: list[object]
) -> None:
    valid: dict[str, dict[str, object]] = {
        "devices": {"id": "ok", "type": "wled", "config": {}},
        "virtuals": {"id": "ok", "config": {"name": "Ok"}, "segments": []},
    }
    records, q = _collect()
    cfg = lenient_validate(LedFxConfig, {field: [*entries, valid[field]]}, "", q)
    assert cfg is not None
    assert [e.id for e in getattr(cfg, field)] == ["ok"]
    assert [r[1] for r in records] == entries


def test_lenient_never_shifts_a_scalar_list_holding_a_dict() -> None:
    records, q = _collect()
    cfg = lenient_validate(
        LedFxConfig, {"melbanks": {"max_frequencies": [350, {}, 15000]}}, "", q
    )
    default = LedFxConfig().melbanks.max_frequencies
    assert cfg is not None and cfg.melbanks.max_frequencies == default
    assert [r[0] for r in records] == ["melbanks.max_frequencies"]


def test_lenient_resets_a_list_of_lists_whole() -> None:
    records, q = _collect()
    virtual: dict[str, object] = {
        "id": "v",
        "config": {"name": "V"},
        "segments": [["d", 0, 1, False], "bad"],
    }
    cfg = lenient_validate(LedFxConfig, {"virtuals": [virtual]}, "", q)
    assert cfg is not None and cfg.virtuals[0].segments == []
    assert [r[0] for r in records] == ["virtuals.0.segments"]


# Values these accept reach divisions and int() at runtime: inf overflows a
# playlist duration, peak_isolation 1 or nan is an infinite or NaN power, and
# 0 rows divides by zero in the matrix effects.
@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (Jitter, "factor_max", "inf"),
        (Jitter, "factor_min", float("nan")),
        (MelbanksConfig, "peak_isolation", "nan"),
        (MelbanksConfig, "peak_isolation", 1),
        (MelbanksConfig, "peak_isolation", -0.5),
        (VirtualConfig, "rows", 0),
    ],
)
def test_runtime_breaking_values_are_rejected(
    model: type, field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({field: value})
