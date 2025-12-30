"""Playlist manager for LedFx

This file provides a small PlaylistManager that stores playlist definitions
in the main config under the `playlists` key. It does not persist any runtime
state (active index, remaining_ms, etc.).
"""

from __future__ import annotations

import asyncio
import copy
import random
import sys
import time

import voluptuous as vol

from ledfx.config import save_config
from ledfx.events import (
    PlaylistAdvancedEvent,
    PlaylistPausedEvent,
    PlaylistResumedEvent,
    PlaylistStartedEvent,
    PlaylistStoppedEvent,
)
from ledfx.utils import generate_id

PlaylistItem = vol.Schema(
    {
        vol.Required(
            "scene_id", description="ID of the scene to activate"
        ): str,
        vol.Optional(
            "duration_ms",
            description="Duration in milliseconds to display this item",
        ): vol.All(int, vol.Range(min=500)),
    }
)


def _validate_jitter_bounds(j):
    try:
        fmin = float(j.get("factor_min", 1.0))
        fmax = float(j.get("factor_max", 1.0))
    except Exception:
        raise vol.Invalid("jitter.factor_min/factor_max must be numbers")
    if fmax < fmin:
        raise vol.Invalid("jitter.factor_max must be >= factor_min")
    return j


JitterSchema = vol.All(
    vol.Schema(
        {
            vol.Optional("enabled", default=False): bool,
            vol.Optional("factor_min", default=1.0): vol.All(
                vol.Coerce(float), vol.Range(min=0.0)
            ),
            vol.Optional("factor_max", default=1.0): vol.All(
                vol.Coerce(float), vol.Range(min=0.0)
            ),
        },
        extra=vol.ALLOW_EXTRA,
    ),
    _validate_jitter_bounds,
)

TimingSchema = vol.Schema(
    {vol.Optional("jitter", default={}): JitterSchema}, extra=vol.ALLOW_EXTRA
)


PlaylistSchema = vol.Schema(
    {
        vol.Required("id", description="Unique playlist identifier"): str,
        vol.Required(
            "name", description="Human readable name for the playlist"
        ): str,
        vol.Required(
            "items",
            description="Ordered list of items (scene_id + optional duration). Empty list = dynamic 'all scenes' resolved at start time.",
        ): [PlaylistItem],
        vol.Optional(
            "default_duration_ms",
            description="Default duration (ms) applied to items that omit duration",
            default=500,
        ): vol.All(int, vol.Range(min=500)),
        vol.Optional(
            "mode",
            description="Playback mode: 'sequence' or 'shuffle'",
            default="sequence",
        ): vol.In(["sequence", "shuffle"]),
        vol.Optional(
            "timing",
            description="Advanced timing settings",
            default={},
        ): TimingSchema,
        vol.Optional(
            "tags",
            description="Tags for filtering or grouping playlists",
            default=list,
        ): list,
        vol.Optional(
            "image",
            description="Image or icon to display for the playlist",
            default="Wallpaper",
        ): vol.Any(str, None),
    },
    extra=vol.ALLOW_EXTRA,
)


class PlaylistManager:
    def __init__(self, core):
        # core is expected to hold `config` (dict) and `config_dir`
        self._core = core
        self._lock = asyncio.Lock()

        # runtime state
        self._active_playlist_id: str | None = None
        # _active_index represents the position within the concrete play order
        # (i.e. the index into self._order). The actual item index in the
        # playlist's items array is self._order[self._active_index].
        self._active_index: int = 0
        # Concrete per-cycle order (permutation of 0..N-1) used when mode == "shuffle"
        self._order: list[int] = []
        self._task: asyncio.Task | None = None
        self._paused: bool = False
        self._pause_event: asyncio.Event = asyncio.Event()
        # timing/runtime fields for current item
        # wall-clock timestamp (monotonic) when current item started
        self._item_start_ts: float | None = None
        # effective duration (ms) after jitter applied for current item
        self._item_effective_duration_ms: int | None = None
        # remaining ms for the current item (set on pause/cancel)
        self._remaining_ms: int | None = None
        # which order-position the remaining_ms corresponds to
        self._remaining_for_order_pos: int | None = None
        # runtime-only mode override applied when starting a playlist (None = use configured)
        self._mode_override: str | None = None
        # runtime-only timing override applied when starting a playlist
        self._timing_override: dict | None = None
        # runtime-resolved items list (for dynamic "all scenes" playlists with empty items)
        self._runtime_items: list | None = None

        # load playlists from config (validate)
        raw = copy.deepcopy(core.config.get("playlists", {})) or {}
        self._playlists: dict[str, dict] = {}
        for pid, p in raw.items():
            try:
                validated = PlaylistSchema(p)
                self._playlists[pid] = validated
            except vol.MultipleInvalid:
                # ignore invalid entries but log to stderr
                sys.stderr.write(
                    f"[playlists] invalid playlist in config: {pid}\n"
                )

    def list_playlists(self) -> dict[str, dict]:
        return copy.deepcopy(self._playlists)

    def _effective_mode(self, playlist: dict | None) -> str:
        """Return the effective playback mode for a playlist, honoring
        a runtime override when present.
        """
        if self._mode_override is not None:
            return self._mode_override
        if playlist is None:
            return "sequence"
        return playlist.get("mode", "sequence")

    def _ensure_order(
        self,
        playlist: dict | None,
        items: list,
        desired_mode: str | None = None,
    ) -> None:
        """Ensure self._order is a concrete permutation matching the
        provided items. If the order is missing or its length doesn't
        match, generate a new concrete order using the effective mode.

        If `desired_mode` is provided it will be used instead of asking
        for the effective mode. This lets callers (for example `start()`)
        force-regenerate an order when a runtime-only override is used.
        """
        if not items:
            self._order = []
            return

        # Determine which mode to use: caller-provided desired_mode wins,
        # otherwise fall back to the runtime/configured effective mode.
        effective_mode = (
            desired_mode
            if desired_mode is not None
            else self._effective_mode(playlist)
        )

        # Regenerate when we don't have an order, when length changed, or
        # when a caller explicitly requested a specific mode.
        if (
            not self._order
            or len(self._order) != len(items)
            or desired_mode is not None
        ):
            if effective_mode == "shuffle":
                self._order = random.sample(
                    list(range(len(items))), len(items)
                )
            else:
                self._order = list(range(len(items)))

    def _current_item_info(
        self,
    ) -> tuple[
        dict | None, list, list | None, int | None, str | None, int | None
    ]:
        """Return (playlist, items, order, item_idx, scene_id, base_duration_ms)
        for the current active position. Values may be None when not
        applicable.
        """
        pid = self._active_playlist_id
        if not pid:
            return None, [], None, None, None, None
        playlist = self._playlists.get(pid)
        items = self._runtime_items
        if not items:
            return playlist, [], None, None, None, None
        if self._order and len(self._order) == len(items):
            order = list(self._order)
            item_idx = order[self._active_index % len(order)]
        else:
            order = None
            item_idx = self._active_index % len(items)
        scene_id = None
        base_duration_ms = None
        try:
            scene_id = items[item_idx].get("scene_id")
            base_duration_ms = items[item_idx].get(
                "duration_ms", playlist.get("default_duration_ms", 500)
            )
        except Exception:
            scene_id = None
            base_duration_ms = None
        return playlist, items, order, item_idx, scene_id, base_duration_ms

    def _get_timing_for_playlist(self, playlist: dict | None) -> dict:
        """Return the effective timing dict for a playlist, honoring runtime override."""
        return (
            self._timing_override
            if self._timing_override is not None
            else (playlist.get("timing", {}) if playlist else {})
        )

    def _sample_effective_duration(
        self, base_duration_ms: int, timing: dict, preserved: int | None = None
    ) -> int:
        """Return the effective duration (ms) for an item given base duration
        and timing. If `preserved` is provided, return that (used on resume).
        """
        if preserved is not None:
            return int(preserved)
        jitter = timing.get("jitter", {}) or {}
        jitter_enabled = bool(jitter.get("enabled", False))
        if jitter_enabled:
            fmin = float(jitter.get("factor_min", 1.0))
            fmax = float(jitter.get("factor_max", 1.0))
            factor = random.uniform(fmin, fmax)
        else:
            factor = 1.0
        return max(500, int(base_duration_ms * factor))

    def get_playlist(self, pid: str) -> dict | None:
        return copy.deepcopy(self._playlists.get(pid))

    async def create_or_replace(self, playlist: dict) -> dict:
        # If caller omitted an id, generate one from the provided name and
        # ensure it's unique within current playlists.
        p = dict(playlist)  # work on a shallow copy
        if not p.get("id"):
            if not p.get("name"):
                raise ValueError(
                    "Playlist must include 'id' or 'name' when creating"
                )
            base = generate_id(p["name"])
            new_id = base
            idx = 1
            while new_id in self._playlists:
                new_id = f"{base}-{idx}"
                idx += 1
            p["id"] = new_id

        validated = PlaylistSchema(p)
        pid = validated["id"]
        async with self._lock:
            self._playlists[pid] = validated
            # persist to core config
            self._core.config["playlists"] = copy.deepcopy(self._playlists)
            save_config(self._core.config, self._core.config_dir)
        return copy.deepcopy(validated)

    async def delete(self, pid: str) -> bool:
        # If the playlist to delete is currently active, stop it first so the
        # runner doesn't keep referencing a playlist that will be removed.
        try:
            if pid and pid == self._active_playlist_id:
                # stop will clear runtime state
                await self.stop()
        except Exception:
            # ignore stop failures and proceed with deletion attempt
            pass

        async with self._lock:
            if pid in self._playlists:
                del self._playlists[pid]
                self._core.config["playlists"] = copy.deepcopy(self._playlists)
                save_config(self._core.config, self._core.config_dir)
                return True
            return False

    # Runtime controls
    async def _runner(self, pid: str):
        """Internal runner that activates scenes in order for the active playlist.

        Uses self._runtime_items which is always set by start() before runner is called.
        """
        try:
            while self._active_playlist_id == pid:
                playlist = self._playlists.get(pid)
                if not playlist:
                    break

                # Ensure we have a concrete order matching the current items
                self._ensure_order(playlist, self._runtime_items)

                # compute order_pos and item_idx
                order_pos = self._active_index % len(self._order)
                item_idx = self._order[order_pos]
                item = self._runtime_items[item_idx]
                scene_id = item.get("scene_id")
                base_duration_ms = item.get(
                    "duration_ms",
                    playlist.get("default_duration_ms", 500),
                )

                # Determine jitter and effective duration, honoring runtime override
                timing = self._get_timing_for_playlist(playlist)
                # preserved effective duration used when resuming a paused item
                preserved = None
                if (
                    self._remaining_ms is not None
                    and self._remaining_for_order_pos == order_pos
                    and self._item_effective_duration_ms is not None
                ):
                    preserved = int(self._item_effective_duration_ms)
                effective_duration_ms = self._sample_effective_duration(
                    base_duration_ms, timing, preserved
                )

                # If we have a stored remaining for this order position (resume), use that
                if (
                    self._remaining_ms is not None
                    and self._remaining_for_order_pos == order_pos
                ):
                    sleep_ms = int(self._remaining_ms)
                    # compute an adjusted start timestamp so elapsed calculation works
                    self._item_start_ts = time.monotonic() - (
                        (effective_duration_ms - sleep_ms) / 1000.0
                    )
                else:
                    sleep_ms = effective_duration_ms
                    self._item_start_ts = time.monotonic()

                # Store the effective duration — preserve it across cancellation so
                # resume can reuse the same sampled duration instead of resampling.
                self._item_effective_duration_ms = effective_duration_ms
                # clear any remaining markers once we've decided to run this item
                self._remaining_ms = None
                self._remaining_for_order_pos = None

                # Wrap activation, event emission, sleeping and advancements in a try/finally
                try:
                    # Activate the scene (synchronous API)
                    # Skip config save during playlist playback to reduce disk I/O
                    try:
                        if hasattr(self._core, "scenes"):
                            self._core.scenes.activate(scene_id, save_config_after=False)
                    except Exception:
                        # Swallow scene activation errors to keep playlist running
                        pass

                    # Emit an event that we activated a scene / advanced
                    try:
                        self._core.events.fire_event(
                            PlaylistAdvancedEvent(
                                pid,
                                order_pos,
                                scene_id,
                                effective_duration_ms=self._item_effective_duration_ms,
                            )
                        )
                    except Exception:
                        # don't let event failures break playlist
                        pass

                    # Wait for the duration unless paused or cancelled
                    try:
                        if self._paused:
                            await self._pause_event.wait()
                        await asyncio.sleep(sleep_ms / 1000.0)
                    except asyncio.CancelledError:
                        # compute remaining time for this item
                        try:
                            if (
                                self._item_start_ts
                                and self._item_effective_duration_ms
                            ):
                                elapsed_ms = int(
                                    (time.monotonic() - self._item_start_ts)
                                    * 1000
                                )
                                remaining = max(
                                    0,
                                    self._item_effective_duration_ms
                                    - elapsed_ms,
                                )
                                self._remaining_ms = remaining
                                self._remaining_for_order_pos = order_pos
                        except Exception:
                            self._remaining_ms = None
                            self._remaining_for_order_pos = None
                        return

                    # advance index if not paused
                    if not self._paused:
                        self._active_index = self._active_index + 1
                        # If we've completed a cycle, wrap and regenerate order if needed
                        if self._active_index >= len(self._order):
                            # cycle completed: regenerate order for shuffle mode
                            self._ensure_order(
                                playlist,
                                self._runtime_items,
                                desired_mode=self._effective_mode(playlist),
                            )
                            self._active_index = 0
                finally:
                    # Clear per-item runtime markers after the item finishes.
                    # If we set _remaining_ms because of cancellation (pause), keep
                    # the sampled _item_effective_duration_ms so resume can reuse it.
                    self._item_start_ts = None
                    if self._remaining_ms is None:
                        # item truly finished normally; clear sampled duration
                        self._item_effective_duration_ms = None

        finally:
            # Clear task handle when runner exits
            if self._task and self._task.done():
                self._task = None

    async def start(
        self, pid: str, mode: str | None = None, timing: dict | None = None
    ) -> bool:
        """Start a playlist by id. Stops any current playlist.

        If `mode` is provided it overrides the playlist's configured mode
        for this runtime session (e.g. force shuffle or sequence).

        If the playlist has an empty items list, it will be dynamically
        resolved to all available scenes at start time.
        """
        if pid not in self._playlists:
            return False

        playlist = self._playlists[pid]
        items = playlist.get("items", [])

        # Dynamic "all scenes" resolution: if items list is empty, populate
        # with all current scene IDs. This happens at start time so the playlist
        # always includes the latest scenes.
        if not items:
            # Access scenes from config since Scenes class stores them there
            if hasattr(self._core, "config") and "scenes" in self._core.config:
                all_scene_ids = list(self._core.config["scenes"].keys())
                if not all_scene_ids:
                    # No scenes available, reject start
                    return False
                # Build transient items list with all scene IDs
                # Duration will be resolved from playlist default_duration_ms
                items = [{"scene_id": sid} for sid in all_scene_ids]
            else:
                # No scenes subsystem available, reject start
                return False

        # stop existing
        await self.stop()

        # Store runtime items for resume/prev/next operations
        # Must be set after stop() since stop() clears it
        self._runtime_items = items

        # apply runtime mode and timing overrides if provided
        self._mode_override = mode
        # set timing override (None means use configured timing)
        self._timing_override = timing

        self._active_playlist_id = pid
        self._active_index = 0

        # initialize concrete order per playlist mode (respect runtime override)
        # Determine the intended mode for this start call. If the caller
        # provided an explicit runtime override, use that. Otherwise use
        # the playlist's configured mode. Passing this as desired_mode
        # guarantees we generate an order matching the intended mode and
        # won't reuse a stale order from a previous session.
        intended_mode = (
            self._mode_override
            if self._mode_override is not None
            else playlist.get("mode", "sequence")
        )
        self._ensure_order(playlist, items, desired_mode=intended_mode)

        self._paused = False
        self._pause_event.set()

        # start runner
        self._task = asyncio.create_task(self._runner(pid))
        try:
            # fire playlist started event (include scene_id if available)
            scene_id = None
            try:
                if self._order:
                    # derive actual item index from concrete order
                    order_pos = self._active_index % len(self._order)
                    item_idx = self._order[order_pos]
                    scene_id = items[item_idx].get("scene_id")
            except Exception:
                scene_id = None
            try:
                self._core.events.fire_event(
                    PlaylistStartedEvent(
                        pid,
                        self._active_index,
                        scene_id,
                        effective_duration_ms=self._item_effective_duration_ms,
                        remaining_ms=(
                            self._remaining_ms
                            if self._remaining_for_order_pos
                            == self._active_index
                            else None
                        ),
                    )
                )
            except Exception:
                pass
        except Exception:
            pass
        return True

    async def stop(self) -> None:
        """Stop any running playlist."""
        pid = self._active_playlist_id
        # compute scene_id before clearing active playlist
        scene_id = None
        if pid:
            try:
                _, _, _, _, scene_id, _ = self._current_item_info()
            except Exception:
                scene_id = None

        self._active_playlist_id = None
        self._paused = False
        self._pause_event.set()

        # cancel any running task
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Snapshot timing values before clearing them for event emission
        effective_duration_ms = self._item_effective_duration_ms
        remaining_ms = self._remaining_ms

        # clear timing state
        self._item_start_ts = None
        self._item_effective_duration_ms = None
        self._remaining_ms = None
        self._remaining_for_order_pos = None
        # clear any runtime-only overrides and resolved items
        self._mode_override = None
        self._timing_override = None
        self._runtime_items = None

        try:
            if pid:
                self._core.events.fire_event(
                    PlaylistStoppedEvent(
                        pid,
                        scene_id,
                        effective_duration_ms=effective_duration_ms,
                        remaining_ms=remaining_ms,
                    )
                )
        except Exception:
            pass

    async def pause(self) -> bool:
        """Pause playlist progression (takes effect between items)."""
        if not self._active_playlist_id:
            return False
        self._paused = True
        self._pause_event.clear()
        # Cancel current runner so it doesn't advance while paused
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # compute remaining_ms eagerly if we have an active item running
        try:
            if self._item_start_ts and self._item_effective_duration_ms:
                elapsed_ms = int(
                    (time.monotonic() - self._item_start_ts) * 1000
                )
                remaining = max(
                    0, self._item_effective_duration_ms - elapsed_ms
                )
                self._remaining_ms = remaining
                self._remaining_for_order_pos = (
                    self._active_index % len(self._order)
                    if self._order
                    else self._active_index
                )
        except Exception:
            # leave remaining as-is
            pass
        try:
            if self._active_playlist_id:
                try:
                    _, _, _, _, scene_id, _ = self._current_item_info()
                except Exception:
                    scene_id = None
                self._core.events.fire_event(
                    PlaylistPausedEvent(
                        self._active_playlist_id,
                        self._active_index,
                        scene_id,
                        effective_duration_ms=self._item_effective_duration_ms,
                        remaining_ms=self._remaining_ms,
                    )
                )
        except Exception:
            pass
        return True

    async def resume(self) -> bool:
        """Resume a paused playlist."""
        if not self._active_playlist_id:
            return False
        self._paused = False
        self._pause_event.set()
        # restart runner if needed; runner will use _remaining_ms if present
        if not self._task:
            self._task = asyncio.create_task(
                self._runner(self._active_playlist_id)
            )
        try:
            # include scene_id where possible
            scene_id = None
            try:
                _, _, _, _, scene_id, _ = self._current_item_info()
            except Exception:
                scene_id = None
            self._core.events.fire_event(
                PlaylistResumedEvent(
                    self._active_playlist_id,
                    self._active_index,
                    scene_id,
                    effective_duration_ms=self._item_effective_duration_ms,
                    remaining_ms=self._remaining_ms,
                )
            )
        except Exception:
            pass
        return True

    async def _advance_index(self, direction: int) -> bool:
        """Common logic for advancing playlist index forward or backward.

        Args:
            direction: +1 for next, -1 for prev

        Returns:
            True if successful, False if no active playlist
        """
        if not self._active_playlist_id:
            return False

        playlist = self._playlists.get(self._active_playlist_id)

        # Check if we're wrapping around
        if direction > 0:
            will_wrap = self._active_index == len(self._order) - 1
        else:
            will_wrap = self._active_index == 0

        # Ensure order exists, regenerating shuffle if wrapping
        if will_wrap:
            self._ensure_order(
                playlist,
                self._runtime_items,
                desired_mode=self._effective_mode(playlist),
            )
        else:
            self._ensure_order(playlist, self._runtime_items)

        self._active_index = (self._active_index + direction) % len(
            self._order
        )

        # Restart runner to pick up new index immediately
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = asyncio.create_task(
            self._runner(self._active_playlist_id)
        )
        return True

    async def prev(self) -> bool:
        """Go to previous item immediately."""
        return await self._advance_index(-1)

    async def next(self) -> bool:
        """Skip to the next item immediately."""
        return await self._advance_index(+1)

    async def get_state(self) -> dict:
        """Return the current runtime state of playlists.

        This is async to keep the public API consistent with callers that
        await the result (e.g. REST handlers).
        """
        # No awaitable operations today, but keep async for API stability.
        # Provide richer state: include concrete order and current scene_id
        state = {
            "active_playlist": self._active_playlist_id,
            "index": self._active_index,
            "paused": self._paused,
        }
        try:
            if self._active_playlist_id:
                playlist = self._playlists.get(self._active_playlist_id)
                items = self._runtime_items
                if items:
                    if self._order and len(self._order) == len(items):
                        state["order"] = list(self._order)
                        # include scenes list matching the concrete order
                        try:
                            state["scenes"] = [
                                items[i].get("scene_id")
                                for i in state["order"]
                            ]
                        except Exception:
                            state["scenes"] = []
                        # compute scene_id from order
                        item_idx = self._order[
                            self._active_index % len(self._order)
                        ]
                        state["scene_id"] = items[item_idx].get("scene_id")
                        # include effective timing info (runtime override wins)
                        state["timing"] = self._get_timing_for_playlist(
                            playlist
                        )
                        # include effective mode (runtime override wins)
                        state["mode"] = self._effective_mode(playlist)
                        # include timing info when available
                        if self._item_effective_duration_ms is not None:
                            state["effective_duration_ms"] = (
                                self._item_effective_duration_ms
                            )
                        # remaining_ms: if we have a stored remaining, use it; otherwise compute on-the-fly
                        if (
                            self._remaining_ms is not None
                            and self._remaining_for_order_pos
                            == (self._active_index % len(self._order))
                        ):
                            state["remaining_ms"] = int(self._remaining_ms)
                        else:
                            if (
                                self._item_start_ts
                                and self._item_effective_duration_ms
                            ):
                                elapsed = int(
                                    (time.monotonic() - self._item_start_ts)
                                    * 1000
                                )
                                state["remaining_ms"] = max(
                                    0,
                                    self._item_effective_duration_ms - elapsed,
                                )
                    else:
                        # no concrete order available; expose basic info
                        state["order"] = list(range(len(items)))
                        # include scenes mapping for the simple sequence order
                        try:
                            state["scenes"] = [
                                items[i].get("scene_id")
                                for i in state["order"]
                            ]
                        except Exception:
                            state["scenes"] = []
                        item_idx = self._active_index % len(items)
                        state["scene_id"] = items[item_idx].get("scene_id")
                        if self._item_effective_duration_ms is not None:
                            state["effective_duration_ms"] = (
                                self._item_effective_duration_ms
                            )
                        # include effective mode (runtime override wins)
                        state["mode"] = (
                            self._mode_override
                            if self._mode_override is not None
                            else playlist.get("mode", "sequence")
                        )
                        if self._remaining_ms is not None:
                            state["remaining_ms"] = int(self._remaining_ms)
        except Exception:
            # fall back to minimal state
            pass
        return state
