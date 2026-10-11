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
from ledfx.events import EffectSetEvent, SceneActivatedEvent
from ledfx.silence_scene import (
    SilenceRecoverySnapshot,
    SilenceSceneController,
    StartupRecoveryOutcome,
)


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

    assert await controller.recover_startup() is StartupRecoveryOutcome.RECOVERED
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

    assert await controller.recover_startup() is StartupRecoveryOutcome.RECOVERED
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

    assert await controller.recover_startup() is StartupRecoveryOutcome.RECOVERY_PENDING
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
async def test_missing_startup_journal_is_distinct_from_recovery_failure(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))

    assert await controller.recover_startup() is StartupRecoveryOutcome.NO_RECOVERY
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_cancelled_journal_allows_normal_startup(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    journal_path.write_text(
        json.dumps({"version": 1, "phase": "cancelled"}), encoding="utf-8"
    )
    controller = SilenceSceneController(cast(LedFxCore, core))

    assert await controller.recover_startup() is StartupRecoveryOutcome.NO_RECOVERY
    assert not journal_path.exists()


@pytest.mark.parametrize(
    "journal_contents",
    [
        "{not-json",
        json.dumps({"version": 999, "phase": "active"}),
    ],
)
@pytest.mark.asyncio
async def test_corrupt_or_unsupported_journal_is_preserved_and_blocks_override(
    controller_core: tuple[SimpleNamespace, Path], journal_contents: str
):
    core, journal_path = controller_core
    journal_path.write_text(journal_contents, encoding="utf-8")
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()

    assert await controller.recover_startup() is StartupRecoveryOutcome.RECOVERY_FAILED
    controller._handle_activity(False, "audio")

    assert journal_path.read_text(encoding="utf-8") == journal_contents
    assert controller.state == "recovery_failed"
    assert controller.status()["recovery_pending"] is True
    assert controller._timer is None

    restarted = SilenceSceneController(cast(LedFxCore, core))
    assert await restarted.recover_startup() is StartupRecoveryOutcome.RECOVERY_FAILED
    assert journal_path.read_text(encoding="utf-8") == journal_contents


@pytest.mark.asyncio
async def test_unreadable_startup_journal_is_preserved(
    controller_core: tuple[SimpleNamespace, Path],
    monkeypatch: pytest.MonkeyPatch,
):
    core, journal_path = controller_core
    journal_path.write_text("diagnostic contents", encoding="utf-8")
    controller = SilenceSceneController(cast(LedFxCore, core))

    def fail_read() -> object:
        raise PermissionError("read denied")

    monkeypatch.setattr(controller, "_read_journal", fail_read)
    assert await controller.recover_startup() is StartupRecoveryOutcome.RECOVERY_FAILED
    assert journal_path.read_text(encoding="utf-8") == "diagnostic contents"
    assert controller.state == "recovery_failed"


@pytest.mark.asyncio
async def test_unknown_source_does_not_restore_active_silence_override(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("sendspin_paused")
    await asyncio.sleep(0)
    await _elapse_timeout(controller)
    assert controller.state == "silence_active"

    controller.report_source_unknown("sendspin_stream_started")
    await asyncio.sleep(0)

    assert controller.state == "silence_active"
    assert journal_path.exists()


@pytest.mark.asyncio
async def test_unknown_resets_volume_deduplication_after_forced_silence(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, _journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("sendspin_paused")
    await asyncio.sleep(0)
    controller.report_source_unknown("sendspin_resumed")
    await asyncio.sleep(0)

    controller.report_volume(core.config.audio.min_volume + 0.01)
    await asyncio.sleep(0)

    assert controller.status()["audio_silent"] is False
    assert controller.status()["timeout_pending"] is False


@pytest.mark.asyncio
async def test_resumed_silent_volume_does_not_restore_until_audio_exceeds_threshold(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("sendspin_paused")
    await asyncio.sleep(0)
    await _elapse_timeout(controller)
    assert controller.state == "silence_active"

    controller.report_source_unknown("sendspin_playback_resumed")
    await asyncio.sleep(0)
    controller.report_volume(core.config.audio.min_volume)
    await asyncio.sleep(0)
    assert controller.state == "silence_active"
    assert journal_path.exists()

    controller.report_volume(core.config.audio.min_volume + 0.01)
    await asyncio.sleep(0)
    if controller._operation is not None:
        await controller._operation

    assert controller.state == "normal"
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_playlist_checkpoint_precedes_pause_and_scene_activation(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, _journal_path = controller_core
    operations: list[str] = []

    def checkpoint() -> dict[str, object]:
        operations.append("checkpoint")
        return {"active": True, "playlist_id": "p1"}

    async def pause() -> bool:
        operations.append("pause")
        return True

    core.playlists.recovery_checkpoint = checkpoint
    core.playlists.pause = pause

    def activate_scene(
        _scene_id: str,
        *,
        save_config_after: bool = True,
        persist: bool = True,
        strict: bool = False,
    ) -> bool:
        operations.append("scene")
        return True

    core.scenes.activate = activate_scene
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("test_silence")
    await asyncio.sleep(0)

    await _elapse_timeout(controller)

    assert operations == ["checkpoint", "pause", "scene"]


@pytest.mark.asyncio
async def test_manual_action_cancels_activation_and_invalidates_journal(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    pause_started = asyncio.Event()
    never_release = asyncio.Event()

    async def pause() -> bool:
        pause_started.set()
        await never_release.wait()
        return True

    core.playlists.recovery_checkpoint = lambda: {
        "active": True,
        "playlist_id": "p1",
    }
    core.playlists.pause = pause
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller.start_monitoring()
    controller.report_source_silence("test_silence")
    await asyncio.sleep(0)
    controller._cancel_timer()
    controller._timeout_elapsed()
    activation = controller._operation
    assert activation is not None
    await pause_started.wait()

    controller._on_user_operation(
        EffectSetEvent("manual", "effect", "v1", "bars", True, False)
    )
    cancellation = controller._operation
    assert cancellation is not None and cancellation is not activation
    await cancellation

    assert not journal_path.exists()
    assert controller.state == "normal"
    assert controller._operation is None


@pytest.mark.asyncio
async def test_manual_effect_during_playlist_restoration_is_not_overwritten(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, journal_path = controller_core
    restoring_playlist = asyncio.Event()
    never_release = asyncio.Event()
    manual_effect = SimpleNamespace(type="manual")
    virtual = SimpleNamespace(
        id="v1",
        active=True,
        active_effect=SimpleNamespace(type="before", config=None),
    )
    core.virtuals = _Virtuals([virtual])

    class _ConfigModel:
        @staticmethod
        def model_validate(config: dict[str, object]) -> dict[str, object]:
            return config

    def get_effect_class(_effect_type: str) -> SimpleNamespace:
        return SimpleNamespace(config_model=lambda: _ConfigModel)

    core.effects = SimpleNamespace(get_class=get_effect_class)

    async def block_playlist_restore(_checkpoint: dict[str, object]) -> bool:
        restoring_playlist.set()
        await never_release.wait()
        return True

    core.playlists.restore_checkpoint = block_playlist_restore
    controller = SilenceSceneController(cast(LedFxCore, core))
    snapshot: SilenceRecoverySnapshot = {
        "version": 1,
        "phase": "active",
        "silence_scene_id": "quiet",
        "virtuals": {
            "v1": {
                "active": True,
                "effect_type": "bars",
                "effect_config": {},
            }
        },
        "playlist": {
            "active": True,
            "playlist_id": "p1",
            "runtime_items": [{"scene_id": "quiet"}],
            "index": 0,
            "order": [0],
        },
    }
    assert controller._write_journal(snapshot)
    controller._journal = snapshot
    controller._state = "silence_active"
    controller.start_monitoring()

    controller._handle_activity(True, "audio")
    restoration = controller._operation
    assert restoration is not None
    await restoring_playlist.wait()
    virtual.active_effect = manual_effect

    controller._on_user_operation(
        EffectSetEvent("manual", "effect", "v1", "bars", True, False)
    )
    cancellation = controller._operation
    assert cancellation is not None and cancellation is not restoration
    await cancellation

    assert virtual.active_effect is manual_effect
    assert controller._journal is None
    assert not journal_path.exists()


@pytest.mark.asyncio
async def test_controller_generated_scene_activation_is_ignored_as_manual_action(
    controller_core: tuple[SimpleNamespace, Path],
):
    core, _journal_path = controller_core
    controller = SilenceSceneController(cast(LedFxCore, core))
    controller._state = "silence_active"
    event = SceneActivatedEvent("quiet")
    event._automated = True
    controller._on_user_operation(event)
    assert controller.state == "silence_active"
    assert controller._operation is None


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
