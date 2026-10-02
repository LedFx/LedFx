"""The Virtuals manager: CRUD, safe mode and mutators that never await."""

import asyncio
import inspect
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer
from pydantic import ValidationError

from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Scene, Segment, VirtualConfig
from ledfx.effects import DummyEffect, Effect
from ledfx.errors import Conflict, Invalid, NotFound, SafeMode
from ledfx.events import GlobalPauseEvent, VirtualConfigUpdateEvent
from ledfx.virtuals import EffectRejected, Virtuals
from tests.test_utilities.virtuals_core import (
    add_virtual,
    enter_safe_mode,
    running_core,
)
from tests.v1_golden.harness import build_app

BIRD = VirtualIdStr("dj bird")

# Every manager method that changes state. None may be a coroutine: the
# change and its save must happen with no await in between.
MUTATORS: tuple[str, ...] = (
    "add",
    "update",
    "remove",
    "set_paused",
    "set_effect",
    "patch_effect",
    "randomize_effect",
    "reset_effect",
    "clear_effect",
    "delete_effect_history",
    "fire_fallback",
)


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


def _entry_ids(ledfx: MagicMock) -> list[str]:
    return [entry.id for entry in ledfx.config.virtuals]


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
    assert _entry_ids(ledfx)[-2:] == ["k-che", "k-che-1"]
    assert ledfx.config.virtuals[-2].config is virtual.config
    ledfx.config_store.request_save.assert_called()
    event = ledfx.events.fire_event.call_args.args[0]
    assert isinstance(event, VirtualConfigUpdateEvent)
    assert event.virtual_id == "k-che-1"


def test_update_config_segments_and_active(ledfx: MagicMock) -> None:
    virtual = ledfx.virtuals.update(
        BIRD,
        config=VirtualConfig(name="Bird", max_brightness=0.5),
        segments=[Segment("strip", 0, 24, False)],
        active=False,
    )
    assert virtual.config.max_brightness == 0.5
    assert virtual.name == "Bird"
    entry = virtual.entry
    assert entry is not None
    assert entry.config is virtual.config
    assert entry.segments == [["strip", 0, 24, False]]
    assert entry.active is False
    ledfx.config_store.request_save.assert_called_once()


def test_update_refuses_bad_segments_and_changes_nothing(ledfx: MagicMock) -> None:
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.update(BIRD, segments=[Segment("nope", 0, 9, False)])
    assert caught.value.loc == ("body", "segments")
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    assert virtual.segments == [["strip", 0, 49, False]]
    ledfx.config_store.request_save.assert_not_called()


def test_update_active_without_segments_is_invalid(ledfx: MagicMock) -> None:
    with pytest.raises(Invalid) as caught:
        ledfx.virtuals.update(VirtualIdStr("empty"), active=True)
    assert caught.value.loc == ("body", "active")
    ledfx.config_store.request_save.assert_not_called()


def test_remove_drops_entry_and_scene_references(ledfx: MagicMock) -> None:
    ledfx.config.scenes["s"] = Scene.model_validate(
        {"name": "S", "virtuals": {"dj bird": {"type": "singleColor", "config": {}}}}
    )
    ledfx.virtuals.remove(BIRD)
    assert ledfx.virtuals.get(BIRD) is None
    assert "dj bird" not in _entry_ids(ledfx)
    assert "dj bird" not in ledfx.config.scenes["s"].virtuals
    ledfx.config_store.request_save.assert_called_once()


def test_remove_device_virtual_removes_its_device(ledfx: MagicMock) -> None:
    ledfx.virtuals.remove(VirtualIdStr("matrix"))
    assert ledfx.devices.get("matrix") is None
    assert "matrix" not in _entry_ids(ledfx)


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
    "update-config": lambda v: v.update(BIRD, config=VirtualConfig(name="Renamed")),
    "update-segments": lambda v: v.update(
        BIRD, segments=[Segment("strip", 0, 9, False)]
    ),
    "update-active": lambda v: v.update(BIRD, active=False),
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


async def test_concurrent_v1_update_and_delete_leave_no_orphan(
    ledfx: MagicMock,
) -> None:
    """An update racing a delete through the v1 handlers
    ends with the virtual gone from both the manager and the config."""
    app = build_app(ledfx, (VirtualsEndpoint, VirtualEndpoint))
    async with TestClient(TestServer(app)) as client:
        for n in range(20):
            virtual_id = f"race-{n}"
            add_virtual(ledfx, virtual_id, virtual_id, [["strip", 0, 9, False]])
            update, delete = await asyncio.gather(
                client.post(
                    "/api/virtuals",
                    json={"id": virtual_id, "config": {"max_brightness": 0.5}},
                ),
                client.delete(f"/api/virtuals/{virtual_id}"),
            )
            assert update.status == 200
            assert delete.status == 200
            assert ledfx.virtuals.get(virtual_id) is None
            assert virtual_id not in _entry_ids(ledfx)


# ---- the running effect ----------------------------------------------------


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
    virtual = ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": 2.0})
    assert virtual.id == "dj bird"
    assert _running(ledfx) == "rainbow"
    assert _setting(ledfx, "speed") == 2.0
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    assert entry.effect is not None and entry.effect.type == "rainbow"
    assert entry.last_effect == "rainbow"
    ledfx.config_store.request_save.assert_called()


def test_set_effect_without_config_restores_the_stored_one(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": 2.0})
    ledfx.virtuals.set_effect(BIRD, "singleColor", {})
    ledfx.virtuals.set_effect(BIRD, "rainbow", None)
    assert _setting(ledfx, "speed") == 2.0


def test_set_effect_refusals(ledfx: MagicMock) -> None:
    with pytest.raises(Invalid, match="Unknown effect type: nope") as caught:
        ledfx.virtuals.set_effect(BIRD, "nope", {})
    assert caught.value.loc == ("body", "type")
    with pytest.raises(ValidationError):
        ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": "fast"})
    with pytest.raises(
        EffectRejected, match="no configured device segments"
    ) as rejected:
        ledfx.virtuals.set_effect(VirtualIdStr("empty"), "rainbow", {})
    assert rejected.value.effect.type == "rainbow"
    assert rejected.value.status == 409
    ledfx.config_store.request_save.assert_not_called()


def test_set_effect_with_fallback_on_a_streamed_virtual_conflicts(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.update(
        BIRD,
        segments=[Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)],
    )
    ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    matrix = VirtualIdStr("matrix")
    assert ledfx.virtuals.get_or_raise(matrix).streaming
    with pytest.raises(Conflict, match="Virtual matrix is being streamed to"):
        ledfx.virtuals.set_effect(matrix, "singleColor", {}, fallback=5.0)


def test_patch_effect_updates_the_running_effect(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    started = _effect(ledfx)
    ledfx.virtuals.patch_effect(BIRD, {"speed": 3.0})
    assert _effect(ledfx) is started
    assert started.config.as_dict()["speed"] == 3.0
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None and entry.effects["rainbow"].config["speed"] == 3.0


def test_a_colour_change_restarts_the_effect(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", {})
    started = _effect(ledfx)
    ledfx.virtuals.patch_effect(BIRD, {"color": "#00ff00"})
    assert _effect(ledfx) is not started
    assert _setting(ledfx, "color") == "#00ff00"


def test_patch_effect_refusals(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="Virtual dj bird has no active effect"):
        ledfx.virtuals.patch_effect(BIRD, {"speed": 3.0})
    ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    with pytest.raises(ValidationError):
        ledfx.virtuals.patch_effect(BIRD, {"speed": "fast"})


def test_running_effect(ledfx: MagicMock) -> None:
    with pytest.raises(Conflict, match="Virtual dj bird has no active effect"):
        ledfx.virtuals.running_effect(BIRD)
    ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": 3.0})
    type_id, config = ledfx.virtuals.running_effect(BIRD)
    assert (type_id, config.as_dict()["speed"]) == ("rainbow", 3.0)


def test_patch_effect_refuses_a_patch_checked_against_another_type(
    ledfx: MagicMock,
) -> None:
    """A fallback can swap the effect between the caller's check and the
    patch; the patch must then not reach the new effect."""
    ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": 2.0})
    with pytest.raises(Conflict, match="runs rainbow, not singleColor"):
        ledfx.virtuals.patch_effect(BIRD, {"speed": 3.0}, type_id="singleColor")
    assert _setting(ledfx, "speed") == 2.0
    ledfx.virtuals.patch_effect(BIRD, {"speed": 3.0}, type_id="rainbow")
    assert _setting(ledfx, "speed") == 3.0


def test_randomize_keeps_brightness(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", {"brightness": 0.3})
    ledfx.virtuals.randomize_effect(BIRD)
    assert _setting(ledfx, "brightness") == 0.3


def test_reset_restores_defaults(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", {"speed": 3.0})
    ledfx.virtuals.reset_effect(BIRD)
    assert _setting(ledfx, "speed") != 3.0
    with pytest.raises(Conflict, match="has no active effect"):
        ledfx.virtuals.reset_effect(VirtualIdStr("mirror"))


def test_clear_effect_keeps_history(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    ledfx.virtuals.clear_effect(BIRD)
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    assert entry.effect is None
    assert [t for t, _ in ledfx.virtuals.effect_history(BIRD)] == ["rainbow"]


def test_delete_effect_history_stops_a_running_type(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", {})
    ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    ledfx.virtuals.delete_effect_history(BIRD, "rainbow")
    assert _running(ledfx) == ""
    assert [t for t, _ in ledfx.virtuals.effect_history(BIRD)] == ["singleColor"]


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
    "set": lambda v: v.set_effect(BIRD, "rainbow", {}),
    "patch": lambda v: v.patch_effect(BIRD, {"speed": 3.0}),
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
    ledfx.virtuals.set_effect(BIRD, "singleColor", {})
    ledfx.config_store.request_save.reset_mock()
    enter_safe_mode(ledfx)
    before = ledfx.config.model_dump()
    with pytest.raises(SafeMode):
        call(ledfx.virtuals)
    assert ledfx.config.model_dump() == before
    assert _running(ledfx) == "singleColor"
    ledfx.config_store.request_save.assert_not_called()


def test_refused_effects_are_not_left_in_the_registry(ledfx: MagicMock) -> None:
    ledfx.virtuals.update(
        BIRD,
        segments=[Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)],
    )
    ledfx.virtuals.set_effect(BIRD, "singleColor", {})
    before = set(ledfx.effects)
    with pytest.raises(Conflict):  # streamed to
        ledfx.virtuals.set_effect(VirtualIdStr("matrix"), "rainbow", {}, fallback=5.0)
    with pytest.raises(EffectRejected):  # no segments
        ledfx.virtuals.set_effect(VirtualIdStr("empty"), "rainbow", {})
    assert set(ledfx.effects) == before


def test_an_effect_that_fails_to_activate_stays_registered_iff_held(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Effect, virtual: object) -> None:
        raise ValueError("boom")

    monkeypatch.setattr(Effect, "activate", refuse)
    before = set(ledfx.effects)
    with pytest.raises(EffectRejected, match="boom") as rejected:
        ledfx.virtuals.set_effect(BIRD, "rainbow", {})
    effect = rejected.value.effect
    held = ledfx.virtuals.get_or_raise(BIRD).active_effect is effect
    assert (effect.id in set(ledfx.effects)) == held
    assert set(ledfx.effects) - before == ({effect.id} if held else set())
