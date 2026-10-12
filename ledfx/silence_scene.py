"""Runtime silence-scene handling and crash-safe operational recovery."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import tempfile
import time
from enum import Enum
from typing import TYPE_CHECKING, TypedDict, TypeGuard

from ledfx.configuration.fields import VirtualIdStr
from ledfx.events import (
    AudioSourceErrorEvent,
    BaseConfigUpdateEvent,
    Event,
    SceneDeletedEvent,
    SilenceSceneEnteredEvent,
    SilenceSceneExitedEvent,
)
from ledfx.fsutil import fsync_directory
from ledfx.playlists import PlaylistRecoveryCheckpoint

if TYPE_CHECKING:
    from ledfx.core import LedFxCore
    from ledfx.effects.audio import AudioAnalysisSource

_LOGGER = logging.getLogger(__name__)


class StartupRecoveryOutcome(Enum):
    NO_RECOVERY = "no_recovery"
    RECOVERED = "recovered"
    RECOVERY_PENDING = "recovery_pending"
    RECOVERY_FAILED = "recovery_failed"


class VirtualRecoverySnapshot(TypedDict):
    active: bool
    effect_type: str | None
    effect_config: dict[str, object] | None


class SilenceRecoverySnapshot(TypedDict, total=False):
    version: int
    phase: str
    silence_scene_id: str | None
    created_monotonic: float
    virtuals: dict[str, VirtualRecoverySnapshot]
    playlist: PlaylistRecoveryCheckpoint


class SilenceSceneController:
    JOURNAL_VERSION = 1

    def __init__(self, ledfx: LedFxCore) -> None:
        self._ledfx = ledfx
        self._journal_path = os.path.join(
            ledfx.config_dir, "silence_scene_recovery.json"
        )
        self._state = "normal"
        self._silent: bool | None = None
        self._timer: asyncio.TimerHandle | None = None
        self._operation: asyncio.Task[None] | None = None
        self._operation_lock = asyncio.Lock()
        self._monitoring = False
        self._audio_source: AudioAnalysisSource | None = None
        self._override_active = False
        self._resume_after_activation = False
        self._journal: SilenceRecoverySnapshot | None = None
        self._recovery_failed = False
        self._last_reason: str | None = None
        self._last_reported_active: bool | None = None
        self._source_forced_silence = False

        for event_type in (
            Event.EFFECT_SET,
            Event.EFFECT_UPDATED,
            Event.EFFECT_CLEARED,
            Event.SCENE_ACTIVATED,
            Event.PLAYLIST_STARTED,
            Event.PLAYLIST_STOPPED,
            Event.PLAYLIST_PAUSED,
            Event.PLAYLIST_RESUMED,
        ):
            ledfx.events.add_listener(self._on_user_operation, event_type)
        ledfx.events.add_listener(self._on_config_update, Event.BASE_CONFIG_UPDATE)
        ledfx.events.add_listener(self._on_scene_deleted, Event.SCENE_DELETED)
        ledfx.events.add_listener(
            self._on_audio_device_change, Event.AUDIO_INPUT_DEVICE_CHANGED
        )
        ledfx.events.add_listener(self._on_audio_source_error, Event.AUDIO_SOURCE_ERROR)
        ledfx.events.add_listener(self._on_shutdown, Event.LEDFX_SHUTDOWN)

    @property
    def state(self) -> str:
        return self._state

    def status(self) -> dict[str, object]:
        settings = self._ledfx.config.silence_scene
        return {
            "enabled": settings.enabled,
            "scene_id": settings.scene_id,
            "timeout_seconds": settings.timeout_seconds,
            "audio_silent": self._silent,
            "timeout_pending": self._state == "silence_pending",
            "silence_scene_active": self._state == "silence_active",
            "restoring": self._state in ("restoring", "startup_recovery"),
            "state": self._state,
            "reason": self._last_reason,
            "recovery_pending": self._journal is not None or self._recovery_failed,
        }

    def start_monitoring(self) -> None:
        self._monitoring = True
        if self._ledfx.config.silence_scene.enabled:
            self._ensure_audio_monitor()
        if self._source_forced_silence:
            self._handle_activity(
                False, self._last_reason or "audio_source_unavailable"
            )
            return
        if self._ledfx.audio is not None and getattr(
            self._ledfx.audio, "_has_volume_measurement", False
        ):
            volume = self._ledfx.audio.volume()
            if volume is not None:
                self._handle_activity(
                    volume > self._ledfx.config.audio.min_volume, "audio"
                )

    def stop_monitoring(self) -> None:
        self._monitoring = False
        self._cancel_timer()
        self._release_audio_monitor()

    def _ensure_audio_monitor(self) -> None:
        source = self._ledfx.audio
        if source is None:
            try:
                from ledfx.effects.audio import AudioAnalysisSource

                source = AudioAnalysisSource(
                    self._ledfx, self._ledfx.config.audio.model_dump()
                )
                self._ledfx.audio = source
            except Exception:
                _LOGGER.exception("Could not start audio monitoring for silence scene")
                return
        if source is self._audio_source:
            return
        self._release_audio_monitor()
        try:
            source.subscribe(self._keep_audio_source_active)
        except Exception:
            _LOGGER.exception("Could not subscribe to audio for silence monitoring")
            return
        self._audio_source = source

    def _release_audio_monitor(self) -> None:
        if self._audio_source is None:
            return
        self._audio_source.unsubscribe(self._keep_audio_source_active)
        self._audio_source = None

    def _keep_audio_source_active(self) -> None:
        pass

    def report_volume(self, volume: float | None) -> None:
        """Called by the audio callback; dispatch only classification changes."""
        if volume is None or self._source_forced_silence:
            return
        min_volume = self._ledfx.config.audio.min_volume
        active = volume > min_volume
        if active == getattr(self, "_last_reported_active", None):
            return
        self._last_reported_active = active
        loop = self._ledfx.loop
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_activity, active, "audio")

    def report_source_silence(self, reason: str) -> None:
        self._source_forced_silence = True
        self._last_reported_active = False
        self._last_reason = reason
        loop = self._ledfx.loop
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_activity, False, reason)

    def report_source_active(self, reason: str) -> None:
        self._source_forced_silence = False
        self._last_reported_active = True
        self._last_reason = reason
        loop = self._ledfx.loop
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_activity, True, reason)

    def report_source_unknown(self, reason: str) -> None:
        self._source_forced_silence = False
        self._last_reported_active = None
        self._last_reason = reason
        loop = self._ledfx.loop
        if loop.is_running():
            loop.call_soon_threadsafe(self._handle_activity, None, reason)

    def _handle_activity(self, active: bool | None, reason: str) -> None:
        if not self._monitoring:
            return
        self._last_reason = reason
        if self._recovery_failed:
            self._silent = None if active is None else not active
            return
        if active is None:
            self._silent = None
            self._cancel_timer()
            if self._state == "silence_pending":
                self._set_state("normal")
            return
        self._silent = not active

        if self._journal is not None:
            self._cancel_timer()
            if self._state == "activating":
                if active is True:
                    self._resume_after_activation = True
            elif self._state == "silence_active":
                if active is True:
                    self._begin_restore()
            elif self._state != "restoring":
                self._begin_restore()
            return

        if active:
            self._cancel_timer()
            if self._state == "silence_pending":
                self._set_state("normal")
            elif self._state == "activating":
                self._resume_after_activation = True
            elif self._state == "silence_active":
                self._begin_restore()
            return

        if self._state in ("activating", "silence_active", "restoring"):
            return

        if not self._ledfx.config.silence_scene.enabled:
            return
        if self._journal is not None:
            return
        if self._state == "normal":
            self._set_state("silence_pending")
            delay = self._ledfx.config.silence_scene.timeout_seconds
            self._timer = self._ledfx.loop.call_later(delay, self._timeout_elapsed)

    def _timeout_elapsed(self) -> None:
        self._timer = None
        if (
            not self._monitoring
            or self._state != "silence_pending"
            or not self._ledfx.config.silence_scene.enabled
            or self._silent is not True
        ):
            if self._state == "silence_pending":
                self._set_state("normal")
            return
        self._set_state("activating")
        self._operation = asyncio.create_task(self._activate_serialized())

    async def _activate_serialized(self) -> None:
        operation = asyncio.current_task()
        try:
            async with self._operation_lock:
                await self._activate()
        finally:
            if self._operation is operation:
                self._operation = None

    def _begin_restore(self) -> None:
        if self._state == "activating":
            self._resume_after_activation = True
            return
        if self._operation is not None and not self._operation.done():
            return
        self._set_state("restoring")
        self._operation = asyncio.create_task(self._restore_serialized())

    async def _restore_serialized(self) -> None:
        restored = False
        operation = asyncio.current_task()
        try:
            async with self._operation_lock:
                if self._journal is not None:
                    restored = await self._restore_snapshot(self._journal)
        finally:
            if self._operation is operation:
                self._operation = None
        if restored and self._state == "normal" and self._silent is True:
            self._handle_activity(False, self._last_reason or "audio")

    async def _activate(self) -> None:
        settings = self._ledfx.config.silence_scene
        scene_id = settings.scene_id
        if not settings.enabled:
            self._set_state("normal")
            return
        if scene_id and self._ledfx.scenes.get(scene_id) is None:
            _LOGGER.warning(
                "Silence scene is enabled but its selected scene is unavailable"
            )
            self._set_state("normal")
            return

        try:
            # Checkpoint capture and pause begin in one event-loop turn; pause
            # sets the runner's paused flag before yielding to its cancellation.
            snapshot = {
                "version": self.JOURNAL_VERSION,
                "phase": "pending",
                "silence_scene_id": scene_id,
                "created_monotonic": time.monotonic(),
                "virtuals": self._capture_virtuals(),
                "playlist": self._ledfx.playlists.recovery_checkpoint(),
            }
        except Exception:
            _LOGGER.exception("Could not capture the pre-silence operational state")
            self._set_state("normal")
            return
        if not self._write_journal(snapshot):
            _LOGGER.error(
                "Silence scene not activated: recovery snapshot could not be persisted"
            )
            self._set_state("normal")
            return
        self._journal = snapshot

        try:
            playlist = snapshot["playlist"]
            if playlist.get("active"):
                with self._ledfx.events.automated():
                    await self._ledfx.playlists.pause()
            if scene_id:
                with self._ledfx.events.automated():
                    activated = self._ledfx.scenes.activate(
                        scene_id, save_config_after=False, persist=False, strict=True
                    )
                if not activated:
                    await self._restore_snapshot(snapshot)
                    return
            else:
                with self._ledfx.events.automated():
                    for virtual in self._ledfx.virtuals.values():
                        virtual_id = VirtualIdStr(virtual.id)
                        self._ledfx.virtuals.clear_effect(virtual_id, store=False)
                        # Flush the final zero frame while the virtual is still
                        # active; deactivation first would suppress its update.
                        virtual.flush_pending_clear_frame()
                        virtual.clear_frame()
            await asyncio.sleep(0)
            snapshot["phase"] = "active"
            self._write_journal(snapshot)
            self._set_state("silence_active")
            if self._resume_after_activation or self._silent is False:
                self._resume_after_activation = False
                restored = await self._restore_snapshot(snapshot)
                if restored and self._state == "normal" and self._silent is True:
                    self._handle_activity(False, self._last_reason or "audio")
        except Exception:
            _LOGGER.exception(
                "Silence scene activation failed; restoring previous state"
            )
            await self._restore_snapshot(snapshot)

    def _capture_virtuals(self) -> dict[str, VirtualRecoverySnapshot]:
        captured: dict[str, VirtualRecoverySnapshot] = {}
        for virtual in self._ledfx.virtuals.values():
            virtual_id = virtual.id
            effect = virtual.active_effect
            effect_type = getattr(effect, "type", None)
            effect_config = (
                effect.config.as_dict()
                if effect is not None and effect_type is not None
                else None
            )
            captured[virtual_id] = {
                "active": bool(virtual.active),
                "effect_type": effect_type,
                "effect_config": effect_config,
            }
        return captured

    async def _restore_snapshot(self, snapshot: SilenceRecoverySnapshot) -> bool:
        self._set_state("restoring")
        snapshot["phase"] = "restoring"
        journal_written = self._write_journal(snapshot)
        if not journal_written:
            _LOGGER.error("Could not update recovery journal before restoration")

        complete = True
        with self._ledfx.events.automated():
            for virtual_id, saved in snapshot.get("virtuals", {}).items():
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual is None:
                    _LOGGER.warning(
                        "Recovery snapshot references missing virtual %s", virtual_id
                    )
                    continue
                try:
                    effect_type = saved.get("effect_type")
                    if effect_type:
                        effect_config = saved.get("effect_config") or {}
                        model = self._ledfx.effects.get_class(
                            effect_type
                        ).config_model()
                        config = model.model_validate(effect_config)
                        self._ledfx.virtuals.set_effect(
                            VirtualIdStr(virtual_id), effect_type, config, store=False
                        )
                    else:
                        self._ledfx.virtuals.clear_effect(
                            VirtualIdStr(virtual_id), store=False
                        )
                    self._ledfx.virtuals.set_runtime_active(
                        VirtualIdStr(virtual_id), bool(saved.get("active", True))
                    )
                except Exception:
                    _LOGGER.exception(
                        "Could not restore virtual %s from silence snapshot", virtual_id
                    )
                    complete = False

        playlist = snapshot.get("playlist", {"active": False})
        if playlist.get("active"):
            try:
                with self._ledfx.events.automated():
                    if not await self._ledfx.playlists.restore_checkpoint(playlist):
                        _LOGGER.warning(
                            "Could not fully restore the pre-silence playlist state"
                        )
                        complete = False
            except Exception:
                _LOGGER.exception("Could not restore the pre-silence playlist")
                complete = False
        await asyncio.sleep(0)

        if complete and self._clear_journal():
            self._journal = None
            self._set_state("normal")
            return True
        self._journal = snapshot
        self._set_state("normal")
        _LOGGER.error(
            "Silence recovery is incomplete; durable snapshot retained for retry"
        )
        return False

    async def recover_startup(self) -> StartupRecoveryOutcome:
        """Restore any durable snapshot before configured startup scene/playlist."""
        try:
            snapshot = await asyncio.to_thread(self._read_journal)
        except FileNotFoundError:
            return StartupRecoveryOutcome.NO_RECOVERY
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as err:
            self._recovery_failed = True
            self._set_state("recovery_failed")
            _LOGGER.error(
                "Could not read silence recovery journal at %s; preserving it and "
                "skipping configured startup scene/playlist: %s",
                self._journal_path,
                err,
            )
            return StartupRecoveryOutcome.RECOVERY_FAILED

        if not self._valid_snapshot(snapshot):
            self._recovery_failed = True
            self._set_state("recovery_failed")
            _LOGGER.error(
                "Invalid or unsupported silence recovery journal at %s; preserving "
                "it and skipping configured startup scene/playlist",
                self._journal_path,
            )
            return StartupRecoveryOutcome.RECOVERY_FAILED
        if snapshot.get("phase") == "cancelled":
            self._clear_journal()
            return StartupRecoveryOutcome.NO_RECOVERY

        self._journal = snapshot
        self._set_state("startup_recovery")
        if await self._restore_snapshot(snapshot):
            return StartupRecoveryOutcome.RECOVERED
        return StartupRecoveryOutcome.RECOVERY_PENDING

    def _read_journal(self) -> object:
        with open(self._journal_path, encoding="utf-8") as file:
            return json.load(file)

    def _valid_snapshot(self, snapshot: object) -> TypeGuard[SilenceRecoverySnapshot]:
        if not isinstance(snapshot, dict):
            return False
        if snapshot.get("version") != self.JOURNAL_VERSION:
            return False
        if snapshot.get("phase") == "cancelled":
            return True
        virtuals = snapshot.get("virtuals")
        playlist = snapshot.get("playlist")
        if not isinstance(virtuals, dict) or not isinstance(playlist, dict):
            return False
        for virtual_id, saved in virtuals.items():
            if not isinstance(virtual_id, str) or not isinstance(saved, dict):
                return False
            if not isinstance(saved.get("active"), bool):
                return False
            effect_type = saved.get("effect_type")
            effect_config = saved.get("effect_config")
            if effect_type is not None and not isinstance(effect_type, str):
                return False
            if effect_config is not None and not isinstance(effect_config, dict):
                return False
        if not isinstance(playlist.get("active"), bool):
            return False
        if playlist["active"]:
            if not isinstance(playlist.get("playlist_id"), str):
                return False
            items = playlist.get("runtime_items")
            if (
                not isinstance(items, list)
                or not items
                or any(not isinstance(item, dict) for item in items)
            ):
                return False
            index = playlist.get("index")
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                return False
            order = playlist.get("order")
            if not isinstance(order, list) or any(
                not isinstance(item_index, int)
                or isinstance(item_index, bool)
                or not 0 <= item_index < len(items)
                for item_index in order
            ):
                return False
            if order and index >= len(order):
                return False
            remaining = playlist.get("remaining_ms")
            if remaining is not None and (
                not isinstance(remaining, int)
                or isinstance(remaining, bool)
                or remaining < 0
            ):
                return False
        return True

    def _write_journal(self, snapshot: SilenceRecoverySnapshot) -> bool:
        directory = os.path.dirname(self._journal_path)
        try:
            fd, temporary = tempfile.mkstemp(
                dir=directory, prefix=".silence-scene.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    json.dump(snapshot, file, separators=(",", ":"), allow_nan=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self._journal_path)
                fsync_directory(directory)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(temporary)
                raise
            return True
        except (OSError, TypeError, ValueError) as err:
            _LOGGER.error("Failed to persist silence recovery snapshot: %s", err)
            return False

    def _clear_journal(self) -> bool:
        try:
            os.unlink(self._journal_path)
            fsync_directory(os.path.dirname(self._journal_path))
            return True
        except FileNotFoundError:
            return True
        except OSError as err:
            _LOGGER.error("Failed to clear silence recovery journal: %s", err)
            return False

    def _on_user_operation(self, event: Event) -> None:
        if getattr(event, "_automated", False):
            return
        if self._state == "silence_pending":
            self._cancel_timer()
            self._set_state("normal")
            return
        if self._state not in ("activating", "silence_active", "restoring"):
            return
        # Playlist-driven scene changes are automatic; an explicit playlist
        # start/stop or direct scene/effect operation is a deliberate override.
        if (
            event.event_type == Event.SCENE_ACTIVATED
            and getattr(event, "scene_id", None)
            == self._ledfx.config.silence_scene.scene_id
        ):
            return
        _LOGGER.info(
            "Silence override superseded by user operation (event=%s)",
            event.event_type,
        )
        if self._operation and not self._operation.done():
            self._operation.cancel()
        if self._state == "restoring":
            self._operation = asyncio.create_task(self._cancel_override())
            return
        self._operation = asyncio.create_task(self._cancel_override())

    async def _cancel_override(self) -> None:
        async with self._operation_lock:
            if self._journal is not None:
                cancelled = {"version": self.JOURNAL_VERSION, "phase": "cancelled"}
                cancelled_written = self._write_journal(cancelled)
                journal_cleared = self._clear_journal()
                if cancelled_written or journal_cleared:
                    self._journal = None
                else:
                    _LOGGER.critical(
                        "Manual override could not invalidate silence recovery journal"
                    )
            self._cancel_timer()
            self._set_state("normal")
            self._operation = None

    def _on_config_update(self, event: BaseConfigUpdateEvent) -> None:
        if "audio" in event.config and self._ledfx.audio is not None:
            self._last_reported_active = None
            if getattr(self._ledfx.audio, "_has_volume_measurement", False):
                self.report_volume(self._ledfx.audio.volume())
        if "silence_scene" not in event.config:
            return
        self._cancel_timer()
        settings = self._ledfx.config.silence_scene
        if self._monitoring:
            if settings.enabled:
                self._ensure_audio_monitor()
            else:
                self._release_audio_monitor()
        if self._state in ("silence_active", "activating") and (
            not settings.enabled
            or self._journal is not None
            and self._journal.get("silence_scene_id") != settings.scene_id
        ):
            if self._operation and not self._operation.done():
                self._operation.cancel()
            self._operation = asyncio.create_task(self._restore_for_config_change())
        elif self._state == "silence_pending":
            self._set_state("normal")
            if settings.enabled and self._silent is True:
                self._handle_activity(False, "configuration")
        elif self._state == "normal" and settings.enabled and self._silent is True:
            self._handle_activity(False, "configuration")

    async def _restore_for_config_change(self) -> None:
        operation = asyncio.current_task()
        try:
            async with self._operation_lock:
                if self._journal is not None:
                    restored = await self._restore_snapshot(self._journal)
                else:
                    restored = True
                    self._set_state("normal")
        finally:
            if self._operation is operation:
                self._operation = None
        if restored and self._state == "normal" and self._silent is True:
            self._handle_activity(False, "configuration")

    def _on_scene_deleted(self, event: SceneDeletedEvent) -> None:
        if event.scene_id != self._ledfx.config.silence_scene.scene_id:
            return
        self._cancel_timer()
        if self._state == "silence_pending":
            self._set_state("normal")
            return
        if self._state in ("silence_active", "activating"):
            if self._operation and not self._operation.done():
                self._operation.cancel()
            self._operation = asyncio.create_task(self._restore_for_config_change())

    def _on_audio_device_change(self, _event) -> None:
        self.report_source_unknown("audio_source_changed")

    def _on_audio_source_error(self, event: AudioSourceErrorEvent) -> None:
        if event.error_type in (
            "sendspin_device_not_found",
            "sendspin_device_unavailable",
        ):
            self.report_source_silence("sendspin_source_unavailable")

    def _on_shutdown(self, _event) -> None:
        self.stop_monitoring()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _set_state(self, state: str) -> None:
        if self._state == state:
            return
        old_state = self._state
        self._state = state
        _LOGGER.info("Silence scene state: %s -> %s", old_state, state)
        if state == "silence_active":
            self._override_active = True
            self._ledfx.events.fire_event(SilenceSceneEnteredEvent())
        elif state == "normal" and self._override_active:
            self._override_active = False
            self._ledfx.events.fire_event(SilenceSceneExitedEvent())
