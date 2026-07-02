# Linux Now Playing Provider — Design Reference

Primary implementation: `ledfx/nowplaying/providers/mpris.py`
Related architecture note: `docs/developer/dev_notes/now_playing_architecture.md`

---

## Purpose

This document describes the Linux now-playing design used by LedFx for future
maintenance and extension. It captures the current architecture and behavior
of the MPRIS provider rather than an implementation roadmap.

Linux now-playing integration is based on **MPRIS2** over session **D-Bus** and
feeds metadata/artwork into the provider-neutral `NowPlayingService`.

---

## Runtime Placement

Source ID: `"mpris"`
Source priority: `2` in `NowPlayingService` (`sendspin=10`, `mpris=2`, `smtc=1`)
Platform guard: provider starts only when `sys.platform == "linux"`

Lifecycle contract:

```
start()   -> connect, subscribe, discover active player
stop()    -> cancel tasks, remove handlers, disconnect bus
clear()   -> reset provider-local state and call now_playing.clear("mpris")
```

Core wiring:
- `ledfx/core.py` creates and starts/stops `MPRISNowPlayingProvider`.
- `ledfx/nowplaying/service.py` source arbitration pre-empts lower-priority sources.

---

## D-Bus / MPRIS Model

```
Session bus names       : org.mpris.MediaPlayer2.<PlayerName>
Object path             : /org/mpris/MediaPlayer2
Player interface        : org.mpris.MediaPlayer2.Player
Properties interface    : org.freedesktop.DBus.Properties
Bus daemon interface    : org.freedesktop.DBus
```

Key signals consumed:
- `NameOwnerChanged` on `org.freedesktop.DBus` for player appear/disappear
- `PropertiesChanged` on `org.freedesktop.DBus.Properties` for player metadata updates

Key properties consumed from `org.mpris.MediaPlayer2.Player`:
- `PlaybackStatus`
- `Metadata`

Metadata mappings:
- `xesam:title` -> `TrackMetadata.title`
- `xesam:artist` (array) -> first element -> `TrackMetadata.artist`
- `xesam:album` -> `TrackMetadata.album`
- `mpris:trackid` -> `TrackMetadata.track_id`
- `mpris:artUrl` -> routed through artwork pipeline

---

## Active Player Selection

Selection flow:
1. Query `ListNames` and keep names matching `org.mpris.MediaPlayer2.*`
2. Query each candidate's `PlaybackStatus`
3. Rank by status:
   - `Playing` > `Paused` > `Stopped` > unknown
4. Use lexicographic bus-name order as current tie-breaker
5. Store active player bus name and unique owner name (`GetNameOwner`)
6. Trigger immediate metadata refresh after active-player change

Re-selection triggers:
- provider initialization
- every relevant `NameOwnerChanged` signal

If no players remain, provider clears mpris state in `NowPlayingService`.

---

## Metadata Flow

Metadata refresh source:
- On each relevant `PropertiesChanged` signal (filtered to active player owner)
- On active-player switch (forced immediate refresh)

Refresh operation:
1. Call `GetAll("org.mpris.MediaPlayer2.Player")`
2. Read `PlaybackStatus` and `Metadata`
3. Normalize title/artist/album/track_id
4. Forward `TrackMetadata(source_id="mpris", ...)` via `now_playing.set_metadata(...)`

Clear behavior:
- If status is `Stopped` and metadata has no content fields, provider calls
  `now_playing.clear("mpris")`.

---

## Artwork Flow

Linux MPRIS artwork is resolver-driven, matching the SMTC model.

Current behavior:
- Provider does **not** directly call `set_artwork_url()` or `set_artwork_bytes()`.
- Provider forwards track metadata only (`title`, `artist`, `album`, `track_id`) via `set_metadata()`.
- `NowPlayingService` triggers `AlbumArtResolver` for `mpris` track changes.
- Resolver uses MusicBrainz + Cover Art Archive to populate artwork through
  `set_artwork_resolved()`.

Rationale:
- Consistent cross-platform behavior with Windows SMTC path.
- Avoids relying on player-specific `mpris:artUrl` quality/format/availability.
- Keeps all fallback and scoring logic centralized in the resolver pipeline.

---

## Dependency Decision

Library: `dbus-fast`

Pinned dependency in `pyproject.toml`:
- `dbus-fast>=5.0.22,<6.0.0; sys_platform == "linux"`

Selection rationale:
- asyncio-native API matching LedFx runtime model
- pure Python (no GLib mandatory runtime coupling)
- active upstream maintenance and recent releases

Alternatives considered but not chosen:
- `dbus-next` (stale cadence)
- `dbus-python` / `dasbus` / `pydbus` (loop/runtime mismatch or stale)
- `mpris2` helper package (stale)

---

## Validation Coverage

Unit tests:
- `tests/test_now_playing_mpris.py`

Covered behaviors:
- lifecycle no-op/reset behavior
- active-player ranking/selection
- metadata forwarding and clear behavior
- provider does not set artwork directly (resolver-driven artwork path)

Outstanding operational check:
- manual Linux smoke test with at least two simultaneous MPRIS sources
  (for example Spotify + Firefox) to validate real-world arbitration behavior.

---

## Extension Points

Known future enhancements:
1. Preferred-player policy override (user-configurable tie-break)
2. Optional polling fallback for players with unreliable signal emission
3. Additional hardening policy for `file://` artwork path trust model

When changing provider behavior, keep this document aligned with:
- `ledfx/nowplaying/providers/mpris.py`
- `ledfx/core.py`
- `ledfx/nowplaying/service.py`
- `tests/test_now_playing_mpris.py`
