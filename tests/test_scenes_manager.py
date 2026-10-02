"""Scenes change effects only through the Virtuals manager."""

import asyncio
import inspect
import logging
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ledfx.scenes as scenes_module
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Playlist, Scene
from ledfx.errors import Conflict, SafeMode
from ledfx.events import PlaylistAdvancedEvent, SceneActivatedEvent
from ledfx.playlists import PlaylistManager
from ledfx.scenes import Scenes
from tests.test_utilities.virtuals_core import (
    enter_safe_mode,
    running_core,
)

RED = {"color": "#ff0000"}
BIRD = VirtualIdStr("dj bird")


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


@pytest.fixture
def scenes(ledfx: MagicMock) -> Scenes:
    ledfx.scenes = Scenes(ledfx)
    ledfx.config.scenes["refused"] = Scene.model_validate(
        {
            "name": "Refused",
            "virtuals": {
                "empty": {"type": "singleColor", "config": RED},
                "dj bird": {"type": "singleColor", "config": RED},
                "matrix": {"type": "rainbow", "config": {}},
            },
        }
    )
    ledfx.config.scenes["plain"] = Scene.model_validate(
        {
            "name": "Plain",
            "virtuals": {"dj bird": {"type": "singleColor", "config": RED}},
        }
    )
    ledfx.config.scenes["stopper"] = Scene.model_validate(
        {"name": "Stopper", "virtuals": {"dj bird": {"action": "stop"}}}
    )
    return ledfx.scenes


def running(ledfx: MagicMock, virtual_id: str) -> str | None:
    effect = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id)).active_effect
    return effect.type if effect else None


def activated_events(ledfx: MagicMock) -> list[SceneActivatedEvent]:
    return [
        call.args[0]
        for call in ledfx.events.fire_event.call_args_list
        if isinstance(call.args[0], SceneActivatedEvent)
    ]


def test_a_refusing_virtual_leaks_nothing_and_the_scene_completes(
    ledfx: MagicMock, scenes: Scenes
) -> None:
    before = len(ledfx.effects.values())

    assert scenes.activate("refused") is True

    assert running(ledfx, "dj bird") == "singleColor"
    assert running(ledfx, "matrix") == "rainbow"
    assert running(ledfx, "empty") is None
    # Two effects run; the refused one was not left registered.
    assert len(ledfx.effects.values()) == before + 2
    assert [e.scene_id for e in activated_events(ledfx)] == ["refused"]
    ledfx.config_store.request_save.assert_called()


def test_safe_mode_refuses_the_whole_call_and_changes_nothing(
    ledfx: MagicMock, scenes: Scenes
) -> None:
    scenes.activate("plain")
    enter_safe_mode(ledfx)
    ledfx.events.fire_event.reset_mock()
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    stored = entry.effect

    for call in (
        lambda: scenes.activate("refused"),
        lambda: scenes.deactivate("plain"),
        lambda: scenes.create({"name": "New", "virtuals": ["dj bird"]}),
        lambda: scenes.destroy("plain"),
    ):
        with pytest.raises(SafeMode):
            call()

    assert running(ledfx, "dj bird") == "singleColor"
    assert running(ledfx, "matrix") is None
    assert entry.effect == stored
    assert "plain" in ledfx.config.scenes
    assert "new" not in ledfx.config.scenes
    assert activated_events(ledfx) == []


def test_stop_and_deactivate_clear_the_stored_effect(
    ledfx: MagicMock, scenes: Scenes
) -> None:
    entry = ledfx.virtuals.get_or_raise(BIRD).entry
    assert entry is not None

    scenes.activate("plain")
    assert entry.effect is not None
    scenes.activate("stopper")
    assert entry.effect is None

    scenes.activate("plain")
    assert entry.effect is not None
    scenes.deactivate("plain")
    assert entry.effect is None
    # The history keeps the type for the next start.
    assert "singleColor" in entry.effects


def test_scenes_only_use_the_manager(
    ledfx: MagicMock, scenes: Scenes, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_effect = MagicMock(wraps=ledfx.virtuals.set_effect)
    clear_effect = MagicMock(wraps=ledfx.virtuals.clear_effect)
    monkeypatch.setattr(ledfx.virtuals, "set_effect", set_effect)
    monkeypatch.setattr(ledfx.virtuals, "clear_effect", clear_effect)

    scenes.activate("plain")
    scenes.activate("stopper")
    scenes.activate("plain")
    scenes.deactivate("plain")

    assert [c.args[:2] for c in set_effect.call_args_list] == [
        (BIRD, "singleColor"),
        (BIRD, "singleColor"),
    ]
    assert [c.args for c in clear_effect.call_args_list] == [(BIRD,)] * 2
    assert all(c.kwargs == {"fallback": None} for c in set_effect.call_args_list)


def test_scenes_source_has_no_direct_effect_calls() -> None:
    source = inspect.getsource(scenes_module)
    assert "effects.create(" not in source
    assert "update_effect_config" not in source
    # Only the manager's own methods may start or stop an effect.
    assert source.count(".set_effect(") == source.count("virtuals.set_effect(")
    assert source.count(".clear_effect(") == source.count("virtuals.clear_effect(")


def playlist_core(ledfx: MagicMock, scenes: Scenes, tmp_path: Path) -> SimpleNamespace:
    ledfx.config.playlists = dict[str, Playlist]()
    return SimpleNamespace(
        config=ledfx.config,
        config_dir=str(tmp_path),
        config_store=ledfx.config_store,
        events=ledfx.events,
        scenes=scenes,
    )


async def run_one_item(core: SimpleNamespace) -> list[PlaylistAdvancedEvent]:
    manager = PlaylistManager(core)
    await manager.create_or_replace(
        {
            "id": "p1",
            "name": "P1",
            "items": [{"scene_id": "refused", "duration_ms": 600}],
        }
    )
    assert await manager.start("p1")
    # The first step is applied before its event fires.
    async with asyncio.timeout(5):
        while not advanced_events(core):
            await asyncio.sleep(0.01)
    await manager.stop()
    return advanced_events(core)


def advanced_events(core: SimpleNamespace) -> list[PlaylistAdvancedEvent]:
    return [
        call.args[0]
        for call in core.events.fire_event.call_args_list
        if isinstance(call.args[0], PlaylistAdvancedEvent)
    ]


async def test_playlists_advance_when_a_scene_partly_fails(
    ledfx: MagicMock, scenes: Scenes, tmp_path: Path
) -> None:
    advanced = await run_one_item(playlist_core(ledfx, scenes, tmp_path))

    assert len(advanced) == 1
    assert running(ledfx, "dj bird") == "singleColor"
    assert running(ledfx, "matrix") == "rainbow"


async def test_playlists_skip_quietly_in_safe_mode(
    ledfx: MagicMock,
    scenes: Scenes,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    core = playlist_core(ledfx, scenes, tmp_path)
    enter_safe_mode(ledfx)
    with caplog.at_level(logging.DEBUG, logger="ledfx.playlists"):
        advanced = await run_one_item(core)

    assert len(advanced) == 1
    assert running(ledfx, "dj bird") is None
    quiet = [r for r in caplog.records if r.name == "ledfx.playlists"]
    assert quiet
    assert all(r.levelno == logging.DEBUG for r in quiet)
    assert "safe mode" in quiet[0].getMessage()


def test_activate_in_is_refused_up_front_in_safe_mode(
    ledfx: MagicMock, scenes: Scenes
) -> None:
    enter_safe_mode(ledfx)
    with pytest.raises(SafeMode):
        scenes.activate_in("plain", 5)
    ledfx.loop.call_later.assert_not_called()


def test_the_final_save_follows_the_event_and_is_optional(
    ledfx: MagicMock, scenes: Scenes
) -> None:
    order: list[str] = []

    def save() -> None:
        order.append("save")

    def fire(event: object) -> None:
        order.append("event" if isinstance(event, SceneActivatedEvent) else "other")

    ledfx.config_store.request_save.side_effect = save
    ledfx.events.fire_event.side_effect = fire

    scenes.activate("plain")
    assert order[-2:] == ["event", "save"]

    order.clear()
    scenes.activate("stopper", save_config_after=False)
    # The manager's own saves come before the event; none follow it.
    assert order[-1] == "event"


@pytest.mark.parametrize(
    "entry",
    [
        {"type": "nosuchtype", "config": {}},
        {"type": "nosuchtype", "preset": "x"},
    ],
)
def test_an_unknown_effect_type_is_skipped(
    ledfx: MagicMock,
    scenes: Scenes,
    caplog: pytest.LogCaptureFixture,
    entry: dict[str, object],
) -> None:
    ledfx.config.scenes["odd"] = Scene.model_validate(
        {
            "name": "Odd",
            "virtuals": {
                "mirror": entry,
                "dj bird": {"type": "singleColor", "config": RED},
            },
        }
    )
    with caplog.at_level(logging.WARNING, logger="ledfx.scenes"):
        assert scenes.activate("odd") is True

    assert running(ledfx, "mirror") is None
    assert running(ledfx, "dj bird") == "singleColor"
    # One warning, no traceback.
    assert [(r.levelno, r.exc_info) for r in caplog.records] == [
        (logging.WARNING, None)
    ]
    assert "Unknown effect type: nosuchtype" in caplog.text
    assert [e.scene_id for e in activated_events(ledfx)] == ["odd"]


def test_a_config_the_model_refuses_is_skipped(
    ledfx: MagicMock, scenes: Scenes, caplog: pytest.LogCaptureFixture
) -> None:
    before = len(ledfx.effects.values())
    ledfx.config.scenes["odd"] = Scene.model_validate(
        {
            "name": "Odd",
            "virtuals": {
                "matrix": {"type": "rainbow", "config": {"speed": "x"}},
                "dj bird": {"type": "singleColor", "config": RED},
            },
        }
    )
    with caplog.at_level(logging.WARNING, logger="ledfx.scenes"):
        assert scenes.activate("odd") is True

    assert running(ledfx, "matrix") is None
    assert running(ledfx, "dj bird") == "singleColor"
    assert "speed" in caplog.text
    assert len(ledfx.effects.values()) == before + 1


def test_deactivate_warns_for_a_refusal_like_activate(
    ledfx: MagicMock,
    scenes: Scenes,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        ledfx.virtuals, "clear_effect", MagicMock(side_effect=Conflict("busy"))
    )
    with caplog.at_level(logging.WARNING, logger="ledfx.scenes"):
        assert scenes.deactivate("plain") is True

    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert "busy" in caplog.text
