"""Silence-scene control and recovery tests without audio hardware."""

import asyncio
import json
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
import pytest_asyncio

from ledfx.configuration.models import LedFxConfig
from ledfx.core import LedFxCore
from ledfx.silence_scene import SilenceRecoverySnapshot, SilenceSceneController


class _Events:
    def add_listener(self, *_args, **_kwargs):
        return lambda: None

    def fire_event(self, _event):
        pass

    @contextmanager
    def automated(self):
        yield


class _Playlists:
    def __init__(self):
        self.restore_results = []
        self.restore_calls = 0

    def recovery_checkpoint(self):
        return {"active": False}

    async def pause(self):
        return False

    async def restore_checkpoint(self, _checkpoint):
        self.restore_calls += 1
        if self.restore_results:
            return self.restore_results.pop(0)
        return True


class _Scenes:
    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        self.activation_saw_durable_snapshot = False

    def get(self, scene_id: str) -> object | None:
        return object() if scene_id == "quiet" else None

    def activate(self, _scene_id, **_kwargs):
        self.activation_saw_durable_snapshot = self.journal_path.exists()
        return True


class _Virtuals:
    def __init__(self, virtuals: Iterable[SimpleNamespace] = ()):
        self._virtuals = {virtual.id: virtual for virtual in virtuals}

    def values(self) -> list[object]:
        return list(self._virtuals.values())

    def get(self, virtual_id: str) -> object | None:
        return self._virtuals.get(virtual_id)

    def clear_effect(self, virtual_id: str, *, store: bool = True) -> None:
        self._virtuals[virtual_id].active_effect = None

    def set_runtime_active(self, virtual_id: str, active: bool) -> None:
        self._virtuals[virtual_id].active = active

    def set_effect(
        self, virtual_id: str, type_id: str, config: object, *, store: bool = True
    ) -> None:
        self._virtuals[virtual_id].active_effect = SimpleNamespace(
            type=type_id,
            config=SimpleNamespace(as_dict=lambda: config),
        )


@pytest_asyncio.fixture
async def controller_core(tmp_path: Path) -> tuple[SimpleNamespace, Path]:
    config = LedFxConfig.model_validate(
        {
            "silence_scene": {
                "enabled": True,
                "scene_id": "quiet",
                "timeout_seconds": 60,
            }
        }
    )
    journal_path = tmp_path / "silence_scene_recovery.json"
    core = SimpleNamespace(
        config_dir=str(tmp_path),
        config=config,
        audio=None,
        loop=asyncio.get_running_loop(),
        events=_Events(),
        playlists=_Playlists(),
        virtuals=_Virtuals(),
    )
    core.scenes = _Scenes(journal_path)
    return core, journal_path


async def _elapse_timeout(controller: SilenceSceneController) -> None:
    controller._cancel_timer()
    controller._timeout_elapsed()
    if controller._operation is not None:
        await controller._operation


@pytest.mark.asyncio
async def test_threshold_silence_persists_before_scene_then_restores(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()

    controller.report_volume(core.config.audio.min_volume)
    await asyncio.sleep(0)
    assert controller.status()["timeout_pending"] is True

    await _elapse_timeout(controller)
    assert core.scenes.activation_saw_durable_snapshot is True
    assert controller.state == "silence_active"
    persisted = json.loads(journal_path.read_text(encoding="utf-8"))
    assert persisted["version"] == 1
    assert persisted["phase"] == "active"

    controller.report_volume(core.config.audio.min_volume + 0.01)
    await asyncio.sleep(0)
    if controller._operation is not None:
        await controller._operation
    assert controller.state == "normal"
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_no_selected_scene_deactivates_then_restores_virtuals(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    core.config.silence_scene.scene_id = None
    original_config = {"speed": 4}
    virtual = SimpleNamespace(
        id="v1",
        active=True,
        active_effect=SimpleNamespace(
            type="bars",
            config=SimpleNamespace(as_dict=lambda: original_config),
        ),
    )
    core.virtuals = _Virtuals([virtual])

    class _ConfigModel:
        @staticmethod
        def model_validate(config: dict[str, object]) -> dict[str, object]:
            return config

    def get_effect_class(_effect_type: str) -> SimpleNamespace:
        return SimpleNamespace(config_model=lambda: _ConfigModel)

    core.effects = SimpleNamespace(get_class=get_effect_class)
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("test_silence")
    await asyncio.sleep(0)

    await _elapse_timeout(controller)
    assert virtual.active is False
    assert virtual.active_effect is None
    assert journal_path.exists()
    assert core.scenes.activation_saw_durable_snapshot is False
    assert controller.state == "silence_active"

    controller.report_source_active("test_active")
    await asyncio.sleep(0)
    if controller._operation is not None:
        await controller._operation

    assert virtual.active is True
    assert virtual.active_effect is not None
    assert virtual.active_effect.type == "bars"
    assert virtual.active_effect.config.as_dict() == original_config
    assert controller.state == "normal"
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_failed_snapshot_write_never_activates_scene(
    controller_core: tuple[SimpleNamespace, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    core, journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))

    def fail_write(snapshot: SilenceRecoverySnapshot) -> bool:
        return False

    monkeypatch.setattr(controller, "_write_journal", fail_write)
    controller.start_monitoring()

    controller.report_source_silence("test_silence")
    await asyncio.sleep(0)
    await _elapse_timeout(controller)

    assert controller.state == "normal"
    assert not core.scenes.activation_saw_durable_snapshot
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_startup_recovery_clears_snapshot_after_restore(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    journal_path.write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "active",
                "silence_scene_id": "quiet",
                "virtuals": {},
                "playlist": {"active": False},
            }
        ),
        encoding="utf-8",
    )
    controller = SilenceSceneController(cast(LedFxCore, core))

    assert await controller.recover_startup() is True
    assert controller.state == "normal"
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_startup_recovery_ignores_deleted_virtuals(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    journal_path.write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "active",
                "silence_scene_id": "quiet",
                "virtuals": {
                    "deleted": {
                        "active": True,
                        "effect_type": "bars",
                        "effect_config": {},
                    }
                },
                "playlist": {"active": False},
            }
        ),
        encoding="utf-8",
    )
    controller = SilenceSceneController(cast(LedFxCore, core))

    assert await controller.recover_startup() is True
    assert controller.state == "normal"
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_incomplete_playlist_recovery_retries_on_activity_only(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    core.playlists.restore_results = [False, False, True]
    journal_path.write_text(
        json.dumps(
            {
                "version": 1,
                "phase": "active",
                "silence_scene_id": "quiet",
                "virtuals": {},
                "playlist": {
                    "active": True,
                    "playlist_id": "missing",
                    "runtime_items": [{"scene_id": "quiet"}],
                    "index": 0,
                    "order": [0],
                },
            }
        ),
        encoding="utf-8",
    )
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()

    assert await controller.recover_startup() is True
    assert core.playlists.restore_calls == 1
    assert controller.status()["recovery_pending"] is True

    controller._handle_activity(False, "audio")
    assert controller._operation is not None
    await controller._operation
    assert core.playlists.restore_calls == 2
    assert controller.status()["recovery_pending"] is True
    assert controller.status()["timeout_pending"] is False
    assert controller._timer is None

    controller._handle_activity(True, "audio")
    assert controller._operation is not None
    await controller._operation
    assert core.playlists.restore_calls == 3
    assert controller.status()["recovery_pending"] is False
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_unavailable_scene_does_not_create_a_recovery_journal(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    core.config.silence_scene.scene_id = "deleted"
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()

    controller.report_source_silence("test_silence")
    await asyncio.sleep(0)
    await _elapse_timeout(controller)

    assert controller.state == "normal"
    assert not journal_path.exists()
