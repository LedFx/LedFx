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
            description="Ordered list of items (scene_id + optional duration)",
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
        """Internal runner that activates scenes in order for the active playlist."""
        try:
            while self._active_playlist_id == pid:
                playlist = self._playlists.get(pid)
                if not playlist or not playlist.get("items"):
                    break
                items = playlist["items"]
                if not self._order or len(self._order) != len(items):
                    # Generate concrete order for the new cycle. Use runtime override
                    # if present, otherwise fall back to configured playlist mode.
                    effective_mode = (
                        self._mode_override
                        if self._mode_override is not None
                        else playlist.get("mode", "sequence")
                    )
                    if effective_mode == "shuffle":
                        self._order = random.sample(
                            list(range(len(items))), len(items)
                        )
                    else:
                        # sequence
                        self._order = list(range(len(items)))

                # position within the concrete order
                order_pos = self._active_index % len(self._order)
                item_idx = self._order[order_pos]
                item = items[item_idx]
                scene_id = item.get("scene_id")
                base_duration_ms = item.get(
                    "duration_ms",
                    playlist.get("default_duration_ms", 500),
                )

                # Determine jitter and effective duration
                # Use runtime timing override if provided, otherwise use configured timing
                timing = (
                    self._timing_override
                    if self._timing_override is not None
                    else (playlist.get("timing", {}) or {})
                )
                jitter = timing.get("jitter", {}) or {}
                jitter_enabled = bool(jitter.get("enabled", False))

                # Sample a factor only when we don't have a preserved effective duration
                # for a paused/resumed item. If this order position was paused and
                # _item_effective_duration_ms contains the previously sampled value,
                # reuse it to avoid resampling jitter on resume.
                if (
                    self._remaining_ms is not None
                    and self._remaining_for_order_pos == order_pos
                    and self._item_effective_duration_ms is not None
                ):
                    # Resuming: reuse previously sampled effective duration
                    effective_duration_ms = int(
                        self._item_effective_duration_ms
                    )
                else:
                    if jitter_enabled:
                        fmin = float(jitter.get("factor_min", 1.0))
                        fmax = float(jitter.get("factor_max", 1.0))
                        # sample factor uniformly
                        factor = random.uniform(fmin, fmax)
                    else:
                        factor = 1.0
                    effective_duration_ms = max(
                        500, int(base_duration_ms * factor)
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
                    try:
                        if hasattr(self._core, "scenes"):
                            self._core.scenes.activate(scene_id)
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
                            effective_mode = (
                                self._mode_override
                                if self._mode_override is not None
                                else playlist.get("mode", "sequence")
                            )
                            if effective_mode == "shuffle":
                                self._order = random.sample(
                                    list(range(len(items))), len(items)
                                )
                            else:
                                self._order = list(range(len(items)))
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
        """
        if pid not in self._playlists:
            return False

        # reject starting an empty playlist
        if not self._playlists[pid].get("items"):
            return False

        # stop existing
        await self.stop()

        # apply runtime mode and timing overrides if provided
        self._mode_override = mode
        # set timing override (None means use configured timing)
        self._timing_override = timing

        self._active_playlist_id = pid
        self._active_index = 0

        # initialize concrete order per playlist mode (respect runtime override)
        playlist = self._playlists.get(pid)
        if playlist and playlist.get("items"):
            items = playlist["items"]
            effective_mode = (
                self._mode_override
                if self._mode_override is not None
                else playlist.get("mode", "sequence")
            )
            if effective_mode == "shuffle":
                self._order = random.sample(
                    list(range(len(items))), len(items)
                )
            else:
                self._order = list(range(len(items)))

        self._paused = False
        self._pause_event.set()

        # start runner
        self._task = asyncio.create_task(self._runner(pid))
        try:
            # fire playlist started event (include scene_id if available)
            scene_id = None
            try:
                if playlist and playlist.get("items"):
                    # derive actual item index from concrete order
                    if self._order:
                        item_idx = self._order[self._active_index]
                    else:
                        item_idx = self._active_index
                    scene_id = playlist["items"][item_idx].get("scene_id")
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
                playlist = self._playlists.get(pid)
                if playlist and playlist.get("items"):
                    if self._order and len(self._order) > 0:
                        item_idx = self._order[
                            self._active_index % len(self._order)
                        ]
                    else:
                        item_idx = self._active_index % len(playlist["items"])
                    scene_id = playlist["items"][item_idx].get("scene_id")
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
        # clear any runtime-only overrides
        self._mode_override = None
        self._timing_override = None

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
                scene_id = None
                try:
                    playlist = self._playlists.get(self._active_playlist_id)
                    if playlist and playlist.get("items"):
                        if self._order and len(self._order) > 0:
                            item_idx = self._order[
                                self._active_index % len(self._order)
                            ]
                        else:
                            item_idx = self._active_index % len(
                                playlist["items"]
                            )
                        scene_id = playlist["items"][item_idx].get("scene_id")
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
            playlist = self._playlists.get(self._active_playlist_id)
            if playlist and playlist.get("items"):
                if self._order and len(self._order) > 0:
                    item_idx = self._order[
                        self._active_index % len(self._order)
                    ]
                else:
                    item_idx = self._active_index % len(playlist["items"])
                scene_id = playlist["items"][item_idx].get("scene_id")
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

    async def next(self) -> bool:
        """Skip to the next item immediately."""
        if not self._active_playlist_id:
            return False
        # advance the position within the concrete order
        items = self._playlists[self._active_playlist_id]["items"]
        if not self._order or len(self._order) != len(items):
            # regenerate order to be safe
            if (
                self._playlists[self._active_playlist_id].get(
                    "mode", "sequence"
                )
                == "shuffle"
            ):
                self._order = random.sample(
                    list(range(len(items))), len(items)
                )
            else:
                self._order = list(range(len(items)))

        self._active_index = (self._active_index + 1) % len(self._order)
        # restart runner to pick up new index immediately
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
        if not self._active_playlist_id:
            return False
        items = self._playlists[self._active_playlist_id]["items"]
        if not self._order or len(self._order) != len(items):
            if (
                self._playlists[self._active_playlist_id].get(
                    "mode", "sequence"
                )
                == "shuffle"
            ):
                self._order = random.sample(
                    list(range(len(items))), len(items)
                )
            else:
                self._order = list(range(len(items)))

        self._active_index = (self._active_index - 1) % len(self._order)
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
                if playlist and playlist.get("items"):
                    items = playlist["items"]
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
                        state["timing"] = (
                            self._timing_override
                            if self._timing_override is not None
                            else playlist.get("timing", {})
                        )
                        # include effective mode (runtime override wins)
                        state["mode"] = (
                            self._mode_override
                            if self._mode_override is not None
                            else playlist.get("mode", "sequence")
                        )
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
