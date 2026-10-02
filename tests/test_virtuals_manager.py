"""The Virtuals manager: CRUD, safe mode and mutators that never await."""

import inspect
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import pytest

from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import (
    ApplyConfigResult,
    GlobalEffectUpdate,
    Highlight,
    OneshotParams,
    Scene,
    Segment,
    SetEffectAllResult,
    VirtualConfig,
    replace_model,
)
from ledfx.effects import DummyEffect, Effect
from ledfx.errors import Conflict, Invalid, NotFound, SafeMode
from ledfx.events import GlobalPauseEvent, VirtualConfigUpdateEvent
from ledfx.virtuals import (
    EffectRejected,
    Virtual,
    VirtualChanges,
    Virtuals,
    repaired_config,
    restarts_effect,
)
from tests.test_utilities.virtuals_core import (
    add_virtual,
    cfg,
    enter_safe_mode,
    entry_ids,
    flashes,
    reload_virtual,
    running_core,
)

BIRD = VirtualIdStr("dj bird")


# Every manager method that changes state. None may be a coroutine: the
# change and its save must happen with no await in between.
MUTATORS: tuple[str, ...] = (
    "add",
    "set_segments",
    "set_config",
    "set_active",
    "patch",
    "remove",
    "set_paused",
    "set_effect",
    "patch_effect",
    "randomize_effect",
    "reset_effect",
    "clear_effect",
    "delete_effect_history",
    "fire_fallback",
    "clear_all_effects",
    "apply_global_config",
    "set_effect_all",
    "oneshot",
    "clear_oneshots",
    "force_color",
    "set_calibration",
    "set_highlight",
    "copy_effect",
)


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.mark.parametrize("name", MUTATORS)
def test_mutators_are_plain_functions(name: str) -> None:
    assert not inspect.iscoroutinefunction(getattr(Virtuals, name))


def test_get_or_raise(ledfx: MagicMock) -> None:
    assert ledfx.virtuals.get_or_raise(BIRD).id == "dj bird"
    with pytest.raises(NotFound, match="Virtual 'nope' not found"):
        ledfx.virtuals.get_or_raise(VirtualIdStr("nope"))


def test_add_stores_saves_and_fires(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.add(VirtualConfig(name="Küche"))
    assert virtual.id == "k-che"
    assert ledfx.virtuals.add(VirtualConfig(name="Küche")).id == "k-che-1"
    assert entry_ids(ledfx)[-2:] == ["k-che", "k-che-1"]
    assert ledfx.config.virtuals[-2].config is virtual.config
    ledfx.config_store.request_save.assert_called()
    event = ledfx.events.fire_event.call_args.args[0]
    assert isinstance(event, VirtualConfigUpdateEvent)
    assert event.virtual_id == "k-che-1"


@pytest.mark.parametrize("name", ["oneshot", "Force Color"])
def test_add_refuses_a_reserved_id(ledfx: MagicMock, name: str) -> None:
    before = entry_ids(ledfx)
    with pytest.raises(Invalid, match="is reserved") as refused:
        ledfx.virtuals.add(VirtualConfig(name=name))
    assert refused.value.loc == ("body", "config", "name")
    assert entry_ids(ledfx) == before
    ledfx.config_store.request_save.assert_not_called()


def test_a_generated_id_is_at_most_128_characters(ledfx: MagicMock) -> None:
    ids = [ledfx.virtuals.add(VirtualConfig(name="a" * 300)).id for _ in range(12)]
    assert len(set(ids)) == 12
    assert {len(i) for i in ids} == {128}
    assert ids[0] == "a" * 128
    assert ids[1] == "a" * 126 + "-1"
    assert ids[10] == "a" * 125 + "-10"


def test_patch_config_segments_and_active(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.patch(
        BIRD,
        VirtualChanges(
            config=VirtualConfig(name="Bird", max_brightness=0.5),
            segments=[Segment("strip", 0, 24, False)],
            active=False,
        ),
    )
    assert virtual.config.max_brightness == 0.5
    assert virtual.name == "Bird"
    entry = virtual.entry
    assert entry is not None
    assert entry.config is virtual.config
    assert entry.segments == [["strip", 0, 24, False]]
    assert entry.active is False
    ledfx.config_store.request_save.assert_called_once()


@pytest.mark.parametrize(
    ("segment", "field"),
    [
        (Segment("nope", 0, 9, False), "device_id"),
        (Segment("strip", 0, 50, False), "end"),
        (Segment("strip", 50, 60, False), "start"),
        (Segment("strip", -1, 9, False), "start"),
        (Segment("strip", 9, 0, False), "start"),
    ],
)
def test_set_segments_refuses_bad_segments_and_changes_nothing(
    ledfx: MagicMock, segment: Segment, field: str
) -> None:
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.set_segments(BIRD, [Segment("strip", 0, 9, False), segment])
    assert caught.value.loc == ("body", "segments", 1, field)
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert virtual.segments == [["strip", 0, 49, False]]
    ledfx.config_store.request_save.assert_not_called()


def test_set_segments_accepts_a_gap_segment_beyond_any_range(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.set_segments(BIRD, [Segment("gap-1", 0, 500, False)])
    assert virtual.segments == [["gap-1", 0, 500, False]]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"frequency_min": 900, "frequency_max": 100}, "frequency_min"),
        ({"frequency_min": 500, "frequency_max": 500}, "frequency_min"),
        ({"rows": 1, "rotate": 2}, "rotate"),
    ],
)
def test_set_config_refuses_what_it_would_repair(
    ledfx: MagicMock, changes: dict[str, int], field: str
) -> None:
    before = ledfx.virtuals.get_or_raise(BIRD).config
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.set_config(BIRD, replace_model(before, **changes))
    assert caught.value.loc == ("body", "config", field)
    assert ledfx.virtuals.get_or_raise(BIRD).config == before
    ledfx.config_store.request_save.assert_not_called()


def _store_unchecked(virtual: Virtual, **changes: object) -> None:
    """Put a config in the virtual and its entry as an old file or v1 left it."""
    virtual._config = replace_model(virtual.config, **changes)
    assert virtual.entry is not None
    virtual.entry.config = virtual._config


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"frequency_min": 900, "frequency_max": 100}, "frequency_min"),
        ({"frequency_min": 500, "frequency_max": 500}, "frequency_min"),
        ({"rows": 1, "rotate": 2}, "rotate"),
    ],
)
def test_add_refuses_what_it_would_repair(
    ledfx: MagicMock, changes: dict[str, int], field: str
) -> None:
    before = entry_ids(ledfx)
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.add(replace_model(VirtualConfig(name="Bad"), **changes))
    assert caught.value.loc == ("body", "config", field)
    assert entry_ids(ledfx) == before
    assert ledfx.virtuals.get(VirtualIdStr("bad")) is None
    ledfx.config_store.request_save.assert_not_called()


def test_a_config_check_looks_only_at_what_changes(ledfx: MagicMock) -> None:
    """v1 can store rows 1 with rotate 2; a change to something else keeps it."""
    virtual = ledfx.virtuals.add(VirtualConfig(name="R"))
    _store_unchecked(virtual, rows=1, rotate=2)
    stored = virtual.config
    changed = ledfx.virtuals.set_config(
        virtual.id, replace_model(stored, max_brightness=0.5)
    )
    assert (changed.config.rows, changed.config.rotate) == (1, 2)
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.set_config(virtual.id, replace_model(changed.config, rotate=3))
    assert caught.value.loc == ("body", "config", "rotate")
    two_rows = ledfx.virtuals.add(VirtualConfig(name="S", rows=2, rotate=2))
    with pytest.raises(Invalid):
        ledfx.virtuals.set_config(two_rows.id, replace_model(two_rows.config, rows=1))


def test_repaired_config_fixes_the_range_and_the_rotate() -> None:
    config = replace_model(
        VirtualConfig(name="Old"),
        frequency_min=900,
        frequency_max=100,
        rows=1,
        rotate=2,
    )
    fixed = repaired_config(config)
    assert (fixed.frequency_min, fixed.frequency_max, fixed.rotate) == (100, 900, 0)
    assert repaired_config(fixed) == fixed


def test_a_stored_config_is_still_repaired_on_load(ledfx: MagicMock) -> None:
    config = VirtualConfig(name="Old", frequency_min=900, frequency_max=100)
    virtual = ledfx.virtuals.create(
        id="old", config=config, ledfx=ledfx, is_device=False
    )
    assert (virtual.config.frequency_min, virtual.config.frequency_max) == (100, 900)


def test_set_active_without_segments_is_a_conflict(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="no configured device segments"):
        ledfx.virtuals.set_active(VirtualIdStr("empty"), True)
    ledfx.config_store.request_save.assert_not_called()


def test_remove_drops_entry_and_scene_references(ledfx: MagicMock) -> None:
    ledfx.config.scenes["s"] = Scene.model_validate(
        {"name": "S", "virtuals": {"dj bird": {"type": "singleColor", "config": {}}}}
    )
    ledfx.virtuals.remove(BIRD)
    assert ledfx.virtuals.get(BIRD) is None
    assert "dj bird" not in entry_ids(ledfx)
    assert "dj bird" not in ledfx.config.scenes["s"].virtuals
    ledfx.config_store.request_save.assert_called_once()


def test_remove_device_virtual_removes_its_device(ledfx: MagicMock) -> None:
    ledfx.virtuals.remove(VirtualIdStr("matrix"))
    assert ledfx.devices.get("matrix") is None
    assert "matrix" not in entry_ids(ledfx)


def test_set_paused_is_runtime_only(ledfx: MagicMock) -> None:
    enter_safe_mode(ledfx)  # allowed: nothing is saved
    assert ledfx.virtuals.set_paused(True) is True
    assert ledfx.virtuals.paused is True
    assert all(v._paused for v in ledfx.virtuals.values())
    event = ledfx.events.fire_event.call_args.args[0]
    assert isinstance(event, GlobalPauseEvent)
    ledfx.config_store.request_save.assert_not_called()


# In safe mode a change raises SafeMode and changes nothing.
CRUD_CHANGES: dict[str, Callable[[Virtuals], object]] = {
    "add": lambda v: v.add(VirtualConfig(name="New")),
    "set-config": lambda v: v.set_config(BIRD, VirtualConfig(name="Renamed")),
    "set-segments": lambda v: v.set_segments(BIRD, [Segment("strip", 0, 9, False)]),
    "set-active": lambda v: v.set_active(BIRD, False),
    "patch": lambda v: v.patch(BIRD, VirtualChanges(active=False)),
    "remove": lambda v: v.remove(BIRD),
}


@pytest.mark.parametrize("call", list(CRUD_CHANGES.values()), ids=list(CRUD_CHANGES))
def test_safe_mode_refuses_and_changes_nothing(
    ledfx: MagicMock, call: Callable[[Virtuals], object]
) -> None:
    enter_safe_mode(ledfx)
    before = ledfx.config.model_dump()
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    ids = list(ledfx.virtuals._virtuals)
    with pytest.raises(SafeMode):
        call(ledfx.virtuals)
    assert ledfx.config.model_dump() == before
    assert list(ledfx.virtuals._virtuals) == ids
    assert virtual.name == "dj bird"
    assert virtual.segments == [["strip", 0, 49, False]]
    ledfx.config_store.request_save.assert_not_called()


def _running(ledfx: MagicMock, virtual_id: str = "dj bird") -> str:
    virtual = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id))
    effect = virtual.active_effect
    return "" if effect is None or isinstance(effect, DummyEffect) else effect.type


def _effect(ledfx: MagicMock, virtual_id: str = "dj bird") -> Effect:
    return ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id)).active_effect


def _setting(ledfx: MagicMock, name: str) -> object:
    """A setting of dj bird's running effect."""
    return _effect(ledfx).config.as_dict()[name]


def test_set_effect_runs_stores_and_saves(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 2.0}))
    assert virtual.id == "dj bird"
    assert _running(ledfx) == "rainbow"
    assert _setting(ledfx, "speed") == 2.0
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    assert entry.effect is not None and entry.effect.type == "rainbow"
    assert entry.last_effect == "rainbow"
    ledfx.config_store.request_save.assert_called()


def test_an_effect_started_on_a_paused_virtual_is_stored_active(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_active(BIRD, False)
    virtual = ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    assert virtual.active is True
    entry = virtual.entry
    assert entry is not None and entry.active is True

    # a restart from the stored config leaves it active and running
    restored = reload_virtual(ledfx, BIRD)
    assert restored is not virtual
    assert restored.active is True
    assert restored.active_effect is not None
    assert restored.active_effect.type == "rainbow"


def _paused_with(ledfx: MagicMock, type_id: str) -> Virtual:
    ledfx.virtuals.set_effect(BIRD, type_id, cfg({}))
    ledfx.virtuals.set_active(BIRD, False)
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert virtual.active is False and virtual.entry is not None
    assert virtual.entry.active is False
    return virtual


def test_a_colour_patch_keeps_a_paused_virtual_paused(ledfx: MagicMock) -> None:
    virtual = _paused_with(ledfx, "singleColor")
    ledfx.virtuals.patch_effect(BIRD, cfg({"color": "#00ff00"}))
    assert virtual.active is False
    assert virtual.entry is not None and virtual.entry.active is False
    assert virtual.active_effect is not None
    assert virtual.active_effect.config.color == "#00ff00"


def test_a_speed_patch_keeps_a_paused_virtual_paused(ledfx: MagicMock) -> None:
    virtual = _paused_with(ledfx, "rainbow")
    ledfx.virtuals.patch_effect(BIRD, cfg({"speed": 3.0}))
    assert virtual.active is False
    assert virtual.entry is not None and virtual.entry.active is False


def test_a_colour_patch_keeps_an_active_virtual_active(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    ledfx.virtuals.patch_effect(BIRD, cfg({"color": "#00ff00"}))
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert virtual.active is True
    assert virtual.entry is not None and virtual.entry.active is True


def test_a_fallback_effect_leaves_the_stored_active_flag(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_active(BIRD, False)
    virtual = ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}), fallback=5.0)
    assert virtual.entry is not None and virtual.entry.active is False
    # the same effect without a fallback is stored active
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    assert virtual.entry.active is True


def test_set_effect_without_config_restores_the_stored_one(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 2.0}))
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    ledfx.virtuals.set_effect(BIRD, "rainbow", None)
    assert _setting(ledfx, "speed") == 2.0


def test_set_effect_refusals(ledfx: MagicMock) -> None:
    before = set(ledfx.effects)
    with pytest.raises(Invalid, match="Unknown effect type: nope") as caught:
        ledfx.virtuals.set_effect(BIRD, "nope", cfg({}))
    assert caught.value.loc == ("body", "type")
    with pytest.raises(Invalid) as bad:
        ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": "fast"}))
    assert bad.value.loc == ("body", "config", "speed")
    with pytest.raises(
        EffectRejected, match="no configured device segments"
    ) as rejected:
        ledfx.virtuals.set_effect(VirtualIdStr("empty"), "rainbow", cfg({}))
    assert rejected.value.effect.type == "rainbow"
    assert rejected.value.status == 409
    assert set(ledfx.effects) == before
    ledfx.config_store.request_save.assert_not_called()


def test_set_effect_with_fallback_on_a_streamed_virtual_conflicts(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_segments(
        BIRD, [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)]
    )
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    matrix = VirtualIdStr("matrix")
    assert ledfx.virtuals.get_or_raise(matrix).streaming
    with pytest.raises(Conflict, match="Virtual matrix is being streamed to"):
        ledfx.virtuals.set_effect(matrix, "singleColor", cfg({}), fallback=5.0)


def test_set_effect_checks_the_stream_before_it_creates_anything(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.virtuals.set_segments(
        BIRD, [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)]
    )
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    create = MagicMock(wraps=ledfx.effects.create)
    monkeypatch.setattr(ledfx.effects, "create", create)
    with pytest.raises(Conflict, match="being streamed to"):
        ledfx.virtuals.set_effect(
            VirtualIdStr("matrix"), "singleColor", None, fallback=5.0
        )
    create.assert_not_called()


def test_a_stale_stored_config_is_a_conflict_naming_the_field(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 2.0}))
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    entry.effects["rainbow"].config["speed"] = "x"
    before = set(ledfx.effects)
    with pytest.raises(Conflict, match="Stored field 'config.speed'") as caught:
        ledfx.virtuals.set_effect(BIRD, "rainbow", None)
    assert caught.value.loc == ("config", "speed")
    assert set(ledfx.effects) == before


def test_restarts_effect_is_a_colour_change_on_a_blending_effect(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    effect = _effect(ledfx)
    assert restarts_effect(effect, cfg({"color": "#00ff00"}))
    assert not restarts_effect(effect, cfg({"speed": 3.0}))
    effect._config = effect.config.model_copy(update={"color_blend": False})
    assert not restarts_effect(effect, cfg({"color": "#00ff00"}))


def test_patch_effect_updates_the_running_effect(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    started = _effect(ledfx)
    ledfx.virtuals.patch_effect(BIRD, cfg({"speed": 3.0}))
    assert _effect(ledfx) is started
    assert started.config.as_dict()["speed"] == 3.0
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None and entry.effects["rainbow"].config["speed"] == 3.0


def test_a_colour_change_restarts_the_effect(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    started = _effect(ledfx)
    ledfx.virtuals.patch_effect(BIRD, cfg({"color": "#00ff00"}))
    assert _effect(ledfx) is not started
    assert _setting(ledfx, "color") == "#00ff00"


def test_patch_effect_refusals(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="Virtual dj bird has no active effect"):
        ledfx.virtuals.patch_effect(BIRD, cfg({"speed": 3.0}))
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    with pytest.raises(Invalid) as bad:
        ledfx.virtuals.patch_effect(BIRD, cfg({"speed": "fast"}))
    assert bad.value.loc == ("body", "config", "speed")


def test_running_effect(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="Virtual dj bird has no active effect"):
        ledfx.virtuals.running_effect(BIRD)
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 3.0}))
    type_id, config = ledfx.virtuals.running_effect(BIRD)
    assert (type_id, config.as_dict()["speed"]) == ("rainbow", 3.0)


def test_patch_effect_refuses_a_patch_checked_against_another_type(
    ledfx: MagicMock,
) -> None:
    """A fallback can swap the effect between the caller's check and the
    patch; the patch must then not reach the new effect."""
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 2.0}))
    with pytest.raises(Conflict, match="runs rainbow, not singleColor"):
        ledfx.virtuals.patch_effect(BIRD, cfg({"speed": 3.0}), type_id="singleColor")
    assert _setting(ledfx, "speed") == 2.0
    ledfx.virtuals.patch_effect(BIRD, cfg({"speed": 3.0}), type_id="rainbow")
    assert _setting(ledfx, "speed") == 3.0


def test_randomize_keeps_brightness(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"brightness": 0.3}))
    ledfx.virtuals.randomize_effect(BIRD)
    assert _setting(ledfx, "brightness") == 0.3


def test_reset_restores_defaults(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 3.0}))
    ledfx.virtuals.reset_effect(BIRD)
    assert _setting(ledfx, "speed") != 3.0
    with pytest.raises(Conflict, match="has no active effect"):
        ledfx.virtuals.reset_effect(VirtualIdStr("mirror"))


def test_clear_effect_keeps_history(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.clear_effect(BIRD)
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    assert entry.effect is None
    assert [t for t, _ in ledfx.virtuals.effect_history(BIRD)] == ["rainbow"]


def test_delete_effect_history_stops_a_running_type(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.delete_effect_history(BIRD, "rainbow")
    assert _running(ledfx) == ""
    assert [t for t, _ in ledfx.virtuals.effect_history(BIRD)] == ["singleColor"]


def test_delete_effect_history_of_an_unknown_type_is_not_found(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.config_store.request_save.reset_mock()
    with pytest.raises(NotFound) as info:
        ledfx.virtuals.delete_effect_history(BIRD, "never-set")
    assert info.value.ids == ("never-set",)
    assert _running(ledfx) == "rainbow"
    ledfx.config_store.request_save.assert_not_called()


def test_delete_effect_history_lets_a_failed_clear_propagate(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    virtual = ledfx.virtuals.get_or_raise(BIRD)

    def broken() -> None:
        raise RuntimeError("device went away")

    monkeypatch.setattr(virtual, "clear_effect", broken)
    with pytest.raises(RuntimeError, match="went away"):
        ledfx.virtuals.delete_effect_history(BIRD, "rainbow")
    assert [t for t, _ in ledfx.virtuals.effect_history(BIRD)] == ["rainbow"]


def test_effect_history_keeps_unregistered_types(ledfx: MagicMock) -> None:
    add_virtual(
        ledfx,
        "old",
        "Old",
        [],
        effects={"gone": {"type": "gone", "config": {"x": 1}}},
    )
    [(type_id, config)] = ledfx.virtuals.effect_history(VirtualIdStr("old"))
    assert (type_id, config.as_dict()) == ("gone", {"x": 1})


def test_fire_fallback_is_runtime_only(ledfx: MagicMock) -> None:
    enter_safe_mode(ledfx)
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    virtual.fallback_active = True
    ledfx.virtuals.fire_fallback(BIRD)
    assert virtual.fallback_fire is True


EFFECT_CHANGES: dict[str, Callable[[Virtuals], object]] = {
    "set": lambda v: v.set_effect(BIRD, "rainbow", cfg({})),
    "patch": lambda v: v.patch_effect(BIRD, cfg({"speed": 3.0})),
    "randomize": lambda v: v.randomize_effect(BIRD),
    "reset": lambda v: v.reset_effect(BIRD),
    "clear": lambda v: v.clear_effect(BIRD),
    "delete-history": lambda v: v.delete_effect_history(BIRD, "singleColor"),
}


@pytest.mark.parametrize(
    "call", list(EFFECT_CHANGES.values()), ids=list(EFFECT_CHANGES)
)
def test_effect_changes_are_refused_in_safe_mode(
    ledfx: MagicMock, call: Callable[[Virtuals], object]
) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    ledfx.config_store.request_save.reset_mock()
    enter_safe_mode(ledfx)
    before = ledfx.config.model_dump()
    with pytest.raises(SafeMode):
        call(ledfx.virtuals)
    assert ledfx.config.model_dump() == before
    assert _running(ledfx) == "singleColor"
    ledfx.config_store.request_save.assert_not_called()


def test_refused_effects_are_not_left_in_the_registry(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_segments(
        BIRD, [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)]
    )
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    before = set(ledfx.effects)
    with pytest.raises(Conflict):  # streamed to
        ledfx.virtuals.set_effect(
            VirtualIdStr("matrix"), "rainbow", cfg({}), fallback=5.0
        )
    with pytest.raises(EffectRejected):  # no segments
        ledfx.virtuals.set_effect(VirtualIdStr("empty"), "rainbow", cfg({}))
    assert set(ledfx.effects) == before


def test_an_effect_that_fails_to_activate_stays_registered_iff_held(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Effect, virtual: object) -> None:
        raise ValueError("boom")

    monkeypatch.setattr(Effect, "activate", refuse)
    before = set(ledfx.effects)
    with pytest.raises(EffectRejected, match="boom") as rejected:
        ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    effect = rejected.value.effect
    held = ledfx.virtuals.get_or_raise(BIRD).active_effect is effect
    assert (effect.id in set(ledfx.effects)) == held
    assert set(ledfx.effects) - before == ({effect.id} if held else set())


# ---- bulk actions and tools ------------------------------------------------


MIRROR = VirtualIdStr("mirror")


def test_clear_all_effects_can_be_limited(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.set_effect(VirtualIdStr("matrix"), "rainbow", cfg({}))
    ledfx.virtuals.clear_all_effects([VirtualIdStr("matrix")])
    assert _running(ledfx) == "rainbow"
    assert _running(ledfx, "matrix") == ""


def test_apply_global_config_updates_running_effects(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"flip": False}))
    result = ledfx.virtuals.apply_global_config(
        GlobalEffectUpdate(brightness=0.5, flip=True)
    )
    assert result == ApplyConfigResult(updated=1, skipped=0, failed=0)
    effect = ledfx.virtuals.get_or_raise(BIRD).active_effect
    assert effect.config.brightness == 0.5
    assert effect.config.flip is True
    ledfx.config_store.request_save.assert_called()


def test_apply_global_config_gradient_and_filter(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "gradient", cfg({}))
    ledfx.virtuals.set_effect(VirtualIdStr("matrix"), "gradient", cfg({}))
    assert ledfx.virtuals.apply_global_config(
        GlobalEffectUpdate(gradient="Dancefloor"), [VirtualIdStr("matrix")]
    ) == ApplyConfigResult(updated=1, skipped=0, failed=0)
    bird = ledfx.virtuals.get_or_raise(BIRD).active_effect
    matrix = ledfx.virtuals.get_or_raise(VirtualIdStr("matrix")).active_effect
    assert matrix.config.gradient != bird.config.gradient
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.apply_global_config(GlobalEffectUpdate(gradient="nope("))
    assert caught.value.loc == ("body", "gradient")
    assert not caught.value.detail.startswith('Invalid value for "gradient"')


def test_apply_global_config_counts_refusals_apart_from_skips(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.virtuals.set_effect(BIRD, "gradient", cfg({}))
    ledfx.virtuals.set_effect(VirtualIdStr("matrix"), "rainbow", cfg({}))
    bird = ledfx.virtuals.get_or_raise(BIRD).active_effect
    assert bird is not None

    def refuse(config: object) -> None:
        raise ValueError("refused")

    monkeypatch.setattr(bird, "update_config", refuse)
    # matrix has no gradient setting: skipped; bird refuses: failed.
    assert ledfx.virtuals.apply_global_config(
        GlobalEffectUpdate(gradient="Dancefloor")
    ) == ApplyConfigResult(updated=0, skipped=1, failed=1)


def test_apply_global_config_lets_a_real_error_through(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    effect = ledfx.virtuals.get_or_raise(BIRD).active_effect
    assert effect is not None

    def bug(config: object) -> None:
        raise TypeError("bug")

    monkeypatch.setattr(effect, "update_config", bug)
    with pytest.raises(TypeError):
        ledfx.virtuals.apply_global_config(GlobalEffectUpdate(brightness=0.5))


def test_set_effect_all_counts_each_outcome(ledfx: MagicMock) -> None:
    result = ledfx.virtuals.set_effect_all("rainbow", cfg({}), ["dj bird", "empty"])
    assert result == SetEffectAllResult(applied=1, blocked=0, failed=1)
    with pytest.raises(Invalid, match="Unknown effect type: nope"):
        ledfx.virtuals.set_effect_all("nope", cfg({}))
    assert _running(ledfx) == "rainbow"


def test_set_effect_all_refuses_an_unknown_id_before_starting_anything(
    ledfx: MagicMock,
) -> None:
    before = set(ledfx.effects)
    with pytest.raises(NotFound, match="Virtual 'ghost' not found"):
        ledfx.virtuals.set_effect_all("rainbow", None, [BIRD, VirtualIdStr("ghost")])
    assert _running(ledfx) == ""
    assert set(ledfx.effects) == before
    ledfx.config_store.request_save.assert_not_called()


def test_set_effect_all_without_a_config_starts_the_defaults(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 3.0}))
    result = ledfx.virtuals.set_effect_all("rainbow", None, [BIRD])
    assert result.applied == 1
    assert _setting(ledfx, "speed") != 3.0


def test_set_effect_all_blocks_streamed_virtuals_with_a_fallback(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_segments(
        BIRD, [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)]
    )
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    result = ledfx.virtuals.set_effect_all(
        "singleColor", cfg({}), ["matrix"], fallback=5.0
    )
    assert result.blocked == 1


def test_oneshot_one_and_all(ledfx: MagicMock) -> None:
    params = OneshotParams(color="#0000ff", hold_ms=500, brightness=0.5)
    with pytest.raises(Conflict, match="Virtual dj bird is not active"):
        ledfx.virtuals.oneshot(BIRD, params)
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.oneshot(BIRD, params)
    ledfx.virtuals.oneshot(None, params)  # inactive virtuals are passed over
    assert len(flashes(ledfx, "dj bird")) == 2
    assert ledfx.virtuals.clear_oneshots(BIRD) is True
    assert flashes(ledfx, "dj bird") == []
    assert ledfx.virtuals.clear_oneshots(MIRROR) is False


@pytest.mark.parametrize("brightness", [-0.1, 3, float("nan")])
def test_oneshot_brightness_is_a_fraction(brightness: float) -> None:
    with pytest.raises(Invalid) as info:
        OneshotParams(brightness=brightness)
    assert info.value.loc == ("body", "brightness")


def test_the_colours_collection_still_stores_a_list(ledfx: MagicMock) -> None:
    """The collection is a load/v1 path: it takes [r, g, b]."""
    ledfx.colors["listed"] = [1, 2, 3]
    assert ledfx.config.user_colors["listed"] == "#010203"


def test_force_color(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.force_color(BIRD, "red")
    assert ledfx.virtuals.get_or_raise(BIRD).assembled_frame[0].tolist() == [
        255.0,
        0.0,
        0.0,
    ]
    ledfx.virtuals.force_color(None, "blue")  # device virtuals only
    assert ledfx.virtuals.get_or_raise(VirtualIdStr("matrix")).assembled_frame[
        0
    ].tolist() == [0.0, 0.0, 255.0]
    assert ledfx.virtuals.get_or_raise(BIRD).assembled_frame[0].tolist() == [
        255.0,
        0.0,
        0.0,
    ]
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.force_color(BIRD, "notacolor")
    assert caught.value.loc == ("body", "color")


def test_highlight_needs_calibration(ledfx: MagicMock) -> None:
    highlight = Highlight("strip", 0, 9)
    with pytest.raises(Conflict, match="not in calibration mode"):
        ledfx.virtuals.set_highlight(BIRD, highlight)
    ledfx.virtuals.set_calibration(BIRD, True)
    ledfx.virtuals.set_highlight(BIRD, highlight)
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert (virtual._hl_device, virtual._hl_start, virtual._hl_end) == ("strip", 0, 9)
    with pytest.raises(Invalid, match="Unknown device: ghost") as unknown:
        ledfx.virtuals.set_highlight(BIRD, Highlight("ghost", 0, 1))
    assert unknown.value.loc == ("body", "device_id")
    # The same wording and loc segment_problem gives a segment.
    with pytest.raises(
        Invalid, match="end must be within the device's pixels 0..49"
    ) as past:
        ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 99))
    assert past.value.loc == ("body", "end")
    with pytest.raises(Invalid, match="start must be within") as start_past:
        ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 60, 70))
    assert start_past.value.loc == ("body", "start")
    assert virtual.calibrating
    ledfx.virtuals.set_calibration(BIRD, False)
    assert not virtual.calibrating
    ledfx.virtuals.set_calibration(BIRD, True)
    for start, end in [(5, 2), (-5, -2), (-1, -1), (-1, 3)]:
        with pytest.raises(Invalid) as bad:
            ledfx.virtuals.set_highlight(BIRD, Highlight("strip", start, end))
        assert bad.value.loc == ("body", "start")
    assert (virtual._hl_start, virtual._hl_end) == (0, 9)  # nothing changed
    ledfx.virtuals.set_highlight(BIRD, None)
    assert virtual._hl_state is False


def test_a_highlight_checks_its_input_before_the_state(ledfx: MagicMock) -> None:
    """Existence and input come before the calibration conflict."""
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    before = (virtual._hl_state, virtual._hl_start, virtual._hl_end)
    with pytest.raises(Invalid) as unknown:
        ledfx.virtuals.set_highlight(BIRD, Highlight("ghost", 0, 1))
    assert unknown.value.loc == ("body", "device_id")
    with pytest.raises(Invalid) as past:
        ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 99))
    assert past.value.loc == ("body", "end")
    with pytest.raises(Conflict, match="not in calibration mode"):
        ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 9))
    assert (virtual._hl_state, virtual._hl_start, virtual._hl_end) == before


def test_a_highlight_is_switched_on_after_its_range_is_set(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The render thread reads the range once _hl_state is on, so it goes last."""
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    ledfx.virtuals.set_calibration(BIRD, True)
    order: list[str] = []

    def spy(self: object, name: str, value: object) -> None:
        if name.startswith("_hl_"):
            order.append(name)
        object.__setattr__(self, name, value)

    monkeypatch.setattr(type(virtual), "__setattr__", spy)
    ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 9))
    assert order[-1] == "_hl_state"


def test_copy_effect(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="Virtual dj bird has no active effect"):
        ledfx.virtuals.copy_effect(BIRD, [MIRROR])
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 3.0}))
    with pytest.raises(NotFound) as unknown:  # checked before anything starts
        ledfx.virtuals.copy_effect(BIRD, [MIRROR, VirtualIdStr("ghost")])
    assert unknown.value.ids == ("ghost",)
    with pytest.raises(NotFound) as twice:  # each unknown id is named once
        ledfx.virtuals.copy_effect(BIRD, [VirtualIdStr("ghost")] * 2)
    assert twice.value.ids == ("ghost",)
    assert ledfx.virtuals.get_or_raise(MIRROR).active_effect is None
    ledfx.virtuals.copy_effect(BIRD, [MIRROR])
    copied = ledfx.virtuals.get_or_raise(MIRROR).active_effect
    assert copied.type == "rainbow" and copied.config.speed == 3.0
    with pytest.raises(Conflict, match="No target could run the effect"):
        ledfx.virtuals.copy_effect(BIRD, [VirtualIdStr("empty")])


def test_copy_effect_reaches_each_target(ledfx: MagicMock) -> None:
    """The result is a new effect object with the source's settings."""
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({"speed": 3.0}))
    ledfx.virtuals.set_effect(MIRROR, "singleColor", cfg({}))
    stale = _effect(ledfx, "mirror")
    ledfx.virtuals.copy_effect(BIRD, [MIRROR, VirtualIdStr("empty")])
    copied = _effect(ledfx, "mirror")
    assert copied is not stale
    assert (copied.type, copied.config.as_dict()["speed"]) == ("rainbow", 3.0)
    assert copied is not _effect(ledfx)


def test_copy_effect_answers_an_unknown_target_before_an_idle_source(
    ledfx: MagicMock,
) -> None:
    """Existence before state."""
    before = set(ledfx.effects)
    with pytest.raises(NotFound) as caught:
        ledfx.virtuals.copy_effect(BIRD, [VirtualIdStr("ghost")])
    assert caught.value.ids == ("ghost",)
    with pytest.raises(Conflict, match="no active effect"):
        ledfx.virtuals.copy_effect(BIRD, [MIRROR])
    assert set(ledfx.effects) == before
    assert ledfx.virtuals.get_or_raise(BIRD).active_effect is None
    assert ledfx.virtuals.get_or_raise(MIRROR).active_effect is None


def test_set_effect_all_answers_an_unknown_id_before_an_unknown_type(
    ledfx: MagicMock,
) -> None:
    """Existence before input."""
    before = set(ledfx.effects)
    with pytest.raises(NotFound):
        ledfx.virtuals.set_effect_all("nope", None, [VirtualIdStr("ghost")])
    with pytest.raises(Invalid):
        ledfx.virtuals.set_effect_all("nope", None, [BIRD])
    assert set(ledfx.effects) == before
    assert ledfx.virtuals.get_or_raise(BIRD).active_effect is None


def test_force_color_answers_an_unknown_virtual_before_a_bad_colour(
    ledfx: MagicMock,
) -> None:
    """Existence before input."""
    before = set(ledfx.effects)
    with pytest.raises(NotFound):
        ledfx.virtuals.force_color(VirtualIdStr("ghost"), "notacolor")
    assert set(ledfx.effects) == before
    assert ledfx.virtuals.get_or_raise(BIRD).active_effect is None


def test_set_effect_checks_the_config_before_the_stream(ledfx: MagicMock) -> None:
    """Input before state."""
    ledfx.virtuals.set_segments(
        BIRD, [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)]
    )
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    matrix = VirtualIdStr("matrix")
    assert ledfx.virtuals.get_or_raise(matrix).streaming
    before = set(ledfx.effects)
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.set_effect(
            matrix, "rainbow", cfg({"speed": "fast"}), fallback=5.0
        )
    assert caught.value.loc == ("body", "config", "speed")
    assert set(ledfx.effects) == before


@pytest.mark.parametrize(
    ("update", "field"),
    [
        (lambda: GlobalEffectUpdate(brightness=5), "brightness"),
        (lambda: GlobalEffectUpdate(brightness=-0.1), "brightness"),
        (lambda: GlobalEffectUpdate(background_brightness=2), "background_brightness"),
        (
            lambda: GlobalEffectUpdate(background_brightness=float("nan")),
            "background_brightness",
        ),
        (lambda: GlobalEffectUpdate(background_color="notacolor"), "background_color"),
    ],
    ids=["high", "negative", "background-high", "nan", "colour"],
)
def test_a_bad_global_value_is_invalid_not_a_failed_count(
    update: Callable[[], GlobalEffectUpdate], field: str
) -> None:
    with pytest.raises(Invalid) as caught:
        update()
    assert caught.value.loc == ("body", field)


def test_a_global_update_accepts_what_it_is_given() -> None:
    update = GlobalEffectUpdate(
        brightness=0, background_brightness=1, background_color="#00ff00", flip=True
    )
    assert (
        update.brightness,
        update.background_brightness,
        update.background_color,
        update.flip,
    ) == (0, 1, "#00ff00", True)


def test_a_refused_patch_config_fires_no_event_and_touches_no_segments(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every input is checked before the first change."""
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    segments = list(virtual.segments)
    running = virtual.active_effect
    ledfx.events.fire_event.reset_mock()
    ledfx.config_store.request_save.reset_mock()
    update_segments = MagicMock(wraps=virtual.update_segments)
    monkeypatch.setattr(virtual, "update_segments", update_segments)
    changes = VirtualChanges(
        segments=[Segment("strip", 0, 9, False)],
        config=replace_model(virtual.config, frequency_min=500, frequency_max=100),
    )
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.patch(BIRD, changes)
    assert caught.value.loc == ("body", "config", "frequency_min")
    update_segments.assert_not_called()
    ledfx.events.fire_event.assert_not_called()
    ledfx.config_store.request_save.assert_not_called()
    assert virtual.segments == segments
    assert virtual.active_effect is running


BULK_CHANGES: dict[str, Callable[[Virtuals], object]] = {
    "apply-global": lambda v: v.apply_global_config(GlobalEffectUpdate(brightness=0.5)),
    "set-effect-all": lambda v: v.set_effect_all("rainbow", cfg({})),
    "copy": lambda v: v.copy_effect(BIRD, [MIRROR]),
}


@pytest.mark.parametrize("call", list(BULK_CHANGES.values()), ids=list(BULK_CHANGES))
def test_bulk_changes_are_refused_in_safe_mode(
    ledfx: MagicMock, call: Callable[[Virtuals], object]
) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    ledfx.config_store.request_save.reset_mock()
    enter_safe_mode(ledfx)
    before = ledfx.config.model_dump()
    with pytest.raises(SafeMode):
        call(ledfx.virtuals)
    assert ledfx.config.model_dump() == before
    assert _running(ledfx, "mirror") == ""
    ledfx.config_store.request_save.assert_not_called()


def test_runtime_tools_work_in_safe_mode(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.config_store.request_save.reset_mock()
    enter_safe_mode(ledfx)
    ledfx.virtuals.clear_all_effects()
    ledfx.virtuals.oneshot(None, OneshotParams())
    ledfx.virtuals.clear_oneshots(None)
    ledfx.virtuals.force_color(None, "red")
    ledfx.virtuals.set_calibration(BIRD, True)
    ledfx.virtuals.set_highlight(BIRD, None)
    ledfx.config_store.request_save.assert_not_called()


def test_bulk_refusals_leave_nothing_in_the_registry(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    before = set(ledfx.effects)
    ledfx.virtuals.set_effect_all("rainbow", cfg({}), ["empty"])  # no segments
    with pytest.raises(Conflict):
        ledfx.virtuals.copy_effect(BIRD, [VirtualIdStr("empty")])
    assert set(ledfx.effects) == before


def test_set_effect_all_mixed_outcomes_leave_only_the_running_effects(
    ledfx: MagicMock,
) -> None:
    before = set(ledfx.effects)
    ids = [BIRD, MIRROR, VirtualIdStr("empty")]
    result = ledfx.virtuals.set_effect_all("rainbow", cfg({}), ids)
    assert result == SetEffectAllResult(applied=2, blocked=0, failed=1)
    assert len(set(ledfx.effects) - before) == 2


def test_copy_effect_warns_per_refusing_target(
    ledfx: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    with caplog.at_level("WARNING", logger="ledfx.virtuals"):
        ledfx.virtuals.copy_effect(BIRD, [MIRROR, VirtualIdStr("empty")])
    refusals = [r for r in caplog.records if "Unable to copy effect" in r.message]
    assert len(refusals) == 1 and "empty" in refusals[0].message


def test_set_effect_all_names_every_unknown_id(ledfx: MagicMock) -> None:
    ids = [BIRD, VirtualIdStr("ghost"), MIRROR, VirtualIdStr("spook")]
    with pytest.raises(NotFound) as caught:
        ledfx.virtuals.set_effect_all("rainbow", None, ids)
    assert caught.value.detail == "Virtuals not found: 'ghost', 'spook'"
    assert caught.value.ids == ("ghost", "spook")
    assert _running(ledfx) == ""


def test_only_domain_refusals_of_an_activation_are_conflicts(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.clear_effect(BIRD)
    ledfx.virtuals.get_or_raise(BIRD).active = False
    ledfx.effects.create = MagicMock(side_effect=ValueError("plugin bug"))
    with pytest.raises(ValueError, match="plugin bug"):
        ledfx.virtuals.set_active(BIRD, True)


def test_refused_activations_leave_the_registry_alone(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.clear_effect(BIRD)
    ledfx.virtuals.patch(BIRD, VirtualChanges(segments=[], active=False))
    before = set(ledfx.effects)
    for _ in range(5):
        with pytest.raises(Conflict):  # no segments to run the restored effect on
            ledfx.virtuals.set_active(BIRD, True)
    assert set(ledfx.effects) == before


def test_v2_highlight_off_is_idempotent(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_highlight(BIRD, None)  # not calibrating: still fine


def test_a_refused_patch_restores_a_config_v2_would_refuse(ledfx: MagicMock) -> None:
    """v1 can store rows 1 with rotate 2; the undo puts it back, unchecked."""
    virtual = ledfx.virtuals.add(VirtualConfig(name="R"))
    _store_unchecked(virtual, rows=1, rotate=2)
    before = virtual.config
    assert before.rotate == 2
    changes = VirtualChanges(config=replace_model(before, rotate=0), active=True)
    with pytest.raises(Conflict):  # no segments to activate on
        ledfx.virtuals.patch(virtual.id, changes)
    assert virtual.config == before
    assert virtual.entry is not None
    assert virtual.entry.config.rotate == 2


def test_a_refused_patch_restores_segments_that_no_longer_fit(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A device that shrank leaves stored segments v2 would refuse. The undo
    does not run the strict checks, so it restores (clamped, as a reload
    would) instead of failing and leaving the new segments in place."""
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    ledfx.devices.get("strip").pixel_count = 30

    def refuse(config: object) -> None:
        raise Conflict("the config step refused")

    monkeypatch.setattr(virtual, "replace_config", refuse)
    changes = VirtualChanges(
        segments=[Segment("strip", 0, 9, False)],
        config=replace_model(virtual.config, max_brightness=0.5),
    )
    with pytest.raises(Conflict, match="config step refused"):
        ledfx.virtuals.patch(BIRD, changes)
    assert virtual.segments == [["strip", 0, 29, False]]
    assert virtual.entry is not None
    assert virtual.entry.segments == [["strip", 0, 29, False]]


def test_stored_segments_out_of_range_load_clamped(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    virtual.update_segments([["strip", 0, 99, False], ["strip", 30, 10, False]])
    assert virtual.segments == [["strip", 0, 49, False], ["strip", 10, 10, False]]
