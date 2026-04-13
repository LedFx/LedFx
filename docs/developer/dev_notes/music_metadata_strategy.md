# LedFx Now Playing — Design & Strategy

## Purpose

This document is the **single source of truth** for the LedFx now-playing integration: its goals, architecture, contracts, and implementation status.

---

## Feature goal

LedFx must:

1. Observe current now-playing metadata from the host OS
2. Obtain album art
3. Optionally derive a color palette from that art
4. Optionally apply that palette to running effects
5. Emit events to the frontend and other subsystems
6. Work on Windows today; be straightforward to extend to Linux and macOS

---

## Core design principle: single interface, platform details hidden

LedFx core code interacts with **one object**: `NowPlayingManager`.

The manager is the sole interface. No other part of LedFx imports from `providers/`, checks `sys.platform`, or knows which media API is in use. The rest of LedFx sees:

```
core.py  ──►  NowPlayingManager  ──►  events / state / palette
```

Everything below the manager — platform detection, session reading, thumbnail extraction — is an implementation detail. The manager selects the correct provider at startup based on `sys.platform` and config. If no provider is available, the manager reports `status: "error"` and LedFx continues normally.

---

## Architecture

### File layout

```
ledfx/nowplaying/
    __init__.py
    manager.py                          # Single interface for LedFx
    models.py                           # NowPlayingTrack, NowPlayingState
    providers/
        __init__.py
        base.py                         # NowPlayingProvider protocol
        platform_media_provider.py      # Concrete provider (Windows SMTC today)
```

### Data flow

```
┌─────────────────────────────────────────────────────────┐
│  Platform (OS media session)                            │
└──────────────┬──────────────────────────────────────────┘
               │ poll / subscribe
┌──────────────▼──────────────────────────────────────────┐
│  Provider (platform_media_provider.py)                  │
│  - reads platform API                                   │
│  - normalizes into NowPlayingTrack                      │
│  - calls manager callback                               │
└──────────────┬──────────────────────────────────────────┘
               │ NowPlayingTrack
┌──────────────▼──────────────────────────────────────────┐
│  Manager (manager.py)                                   │
│  - dedupe (signature-based)                             │
│  - art resolution (provider thumbnail → HTTP fallback)  │
│  - palette extraction (gradient_extraction)             │
│  - palette application (to running effects)             │
│  - event emission                                       │
│  - state management                                     │
└──────────────┬──────────────────────────────────────────┘
               │ Events + State
       ┌───────┴───────┐
       ▼               ▼
   REST API        Frontend / WS
```

---

## Contracts

### Manager (the single interface)

LedFx core calls only these:

```python
manager = NowPlayingManager(ledfx)
await manager.start()       # reads config, picks provider, begins
await manager.stop()        # clean shutdown
manager.state               # NowPlayingState — current track, palette, status
```

The manager owns:

* lifecycle (start/stop, shutdown listener)
* provider selection (automatic, based on platform + config)
* dedupe and stabilisation (signature-based, skip identical tracks/palettes)
* album art resolution (provider thumbnail, HTTP fallback, bounded cache)
* palette generation (via `extract_gradient_metadata`)
* palette application (to effects with gradient support, per-effect error isolation)
* event emission (`NOW_PLAYING_UPDATED`, `NOW_PLAYING_ART_UPDATED`, `NOW_PLAYING_PALETTE_UPDATED`)

### Provider protocol

```python
class NowPlayingProvider(Protocol):
    async def start(self, callback: Callable[[NowPlayingTrack], Awaitable[None]]) -> None: ...
    async def stop(self) -> None: ...
```

A provider:

* reads the platform media session
* normalizes metadata into a `NowPlayingTrack`
* pushes updates via the callback
* knows nothing about art fetching, palettes, effects, or events

Optional: a provider may implement `get_thumbnail_bytes() -> bytes | None` if it can supply raw art data natively (e.g. Windows SMTC thumbnail stream).

### Models

`NowPlayingTrack` — normalized track metadata with `signature()` for dedupe and `art_signature()` for art change detection.

`NowPlayingState` — subsystem state exposed via `manager.state` and the REST API.

Both are dataclasses, provider-agnostic, serializable via `.to_dict()`.

---

## Platform providers

### How provider selection works

The manager reads `config["now_playing"]["provider"]` (default: `"platform_media"`), then calls `_create_provider()`. The provider file itself checks `sys.platform` at import time and exposes `is_available()` / `unavailable_reason()`. If the provider isn't available for the current OS, the manager logs a warning and sets status to `"error"` — LedFx continues without now-playing.

### Windows — implemented

`platform_media_provider.py` uses `winrt-windows-media-control` to read Windows SMTC sessions. It polls on a configurable interval, reads `GlobalSystemMediaTransportControlsSessionManager`, and produces `NowPlayingTrack` instances.

Dependency: `winrt-windows-media-control >= 3.2.1` (platform-gated to `sys_platform == 'win32'` in `pyproject.toml`).

### Linux — not yet implemented

MPRIS2 over D-Bus is the clear path. Libraries like `dbus-next` provide async D-Bus access. A future `linux_mpris_provider.py` would:

* connect to the session bus
* watch `org.mpris.MediaPlayer2` interfaces
* normalize into `NowPlayingTrack`

No code changes to the manager are needed — just a new provider file and an `elif` in `_create_provider()`.

### macOS — not yet implemented

macOS has no unified media session API equivalent to SMTC or MPRIS. Options are limited:

* `NSAppleScript` / `osascript` to query specific apps (fragile, app-specific)
* `MediaRemote.framework` (private, undocumented)
* Polling specific player APIs

This is the lowest-priority platform. A stub that returns `is_available() = False` is acceptable until a viable approach is proven.

### Adding a new provider

1. Create `ledfx/nowplaying/providers/<platform>_provider.py`
2. Implement `NowPlayingProvider` protocol + `is_available()` / `unavailable_reason()`
3. Add an `elif` branch in `NowPlayingManager._create_provider()`
4. Add any platform-gated dependency to `pyproject.toml`
5. No changes to manager, models, events, API, or tests (beyond the new provider's own tests)

---

## Dedupe and stabilisation

Signature-based. `NowPlayingTrack.signature()` hashes `(provider, player_name, title, artist, album)`.

The manager skips updates when:

* track signature unchanged AND art signature unchanged AND playing state unchanged
* extracted gradient is identical to `state.active_gradient`
* an individual effect already has the same gradient applied

This prevents: repeated palette churn, redundant art fetches, event spam.

---

## Palette pipeline

1. Art resolved (provider thumbnail → HTTP fallback → bounded cache)
2. `extract_gradient_metadata()` extracts palette variants from PIL image
3. Configured variant selected (default: `led_punchy`)
4. Gradient applied to running effects that support it (GradientEffect or `_config["gradient"]`)
5. Per-effect error isolation — one failure doesn't block others
6. `NowPlayingPaletteUpdatedEvent` emitted with affected/skipped lists

---

## Events

| Event | Trigger |
|---|---|
| `NOW_PLAYING_UPDATED` | Track change or play/pause state change |
| `NOW_PLAYING_ART_UPDATED` | Album art resolved for current track |
| `NOW_PLAYING_PALETTE_UPDATED` | Palette extracted and optionally applied |

All events carry `provider`, `track_signature`, `timestamp`. Emitted only on meaningful change.

---

## REST API

`GET /api/now-playing` — returns `NowPlayingState.to_dict()`. Defined in `ledfx/api/now_playing.py`.

---

## Configuration

```json
"now_playing": {
  "enabled": false,
  "provider": "platform_media",
  "generate_palette_from_album_art": false,
  "apply_palette_to_running_effects": false,
  "gradient_variant": "led_punchy",
  "poll_interval_s": 2.0,
  "art_fetch_timeout_ms": 5000,
  "art_cache": true,
  "art_cache_max_items": 64
}
```

---

## Failure model

Fail-soft throughout:

* Provider unavailable → manager logs warning, sets status `"error"`, LedFx continues
* Provider crashes → `_poll_loop` catches exceptions, logs at DEBUG, retries next interval
* Art fetch fails → no palette, no event, no crash
* Palette extraction fails → logged at WARN, update continues without palette
* Effect update fails → logged per-effect, other effects still updated
* Subsystem startup fails → wrapped in try/except in `core.py`, never blocks boot

---

## Logging

| Level | What |
|---|---|
| INFO | Track changes, subsystem start/stop, palette applied |
| DEBUG | Dedupe skips, cache hits, provider polling, per-effect skips |
| WARNING | Provider unavailable, art/palette failures, effect update failures |
| ERROR | Subsystem startup failure |

---

## Testing

Covered in `tests/test_now_playing.py` (23 tests):

* Model signatures and serialization
* Manager disabled/missing config
* Dedupe (duplicate ignored, different track triggers, play state change)
* Art cache bounding
* Gradient application (gradient effects, non-gradient effects, dummy effects, none effects)
* Palette extraction from real image data
* Event class construction and types
* Provider protocol compliance

---

## Implementation status

| Area | Status |
|---|---|
| Manager | Done |
| Models | Done |
| Events | Done |
| Provider protocol | Done |
| Windows SMTC provider | Done |
| Linux MPRIS provider | Not started |
| macOS provider | Not started |
| REST API | Done |
| Palette pipeline | Done |
| Dedupe + stabilisation | Done |
| Fail-soft | Done |
| Tests | Done (23 passing) |
| `aionowplaying` removal | Done |

---

## Historical note

The original design used `aionowplaying` as a dependency, assuming it was a media session reader. It is actually a **publisher** (exposes what your app is playing to the OS). This was removed. The architecture was sound — only the dependency assumption was wrong. See git history for details.

---

## Copilot recovery guidance

If context is lost, re-anchor on these facts:

1. `NowPlayingManager` is the **single interface** — nothing else in LedFx touches providers directly
2. The problem is **reading** platform now-playing state, not publishing it
3. Platform specifics live **only** in provider files under `providers/`
4. The manager handles everything else: dedupe, art, palette, events, state
5. `aionowplaying` was removed — do not reintroduce it
6. Fail-soft: the now-playing subsystem must never block startup or crash the app
# LedFx Now Playing Integration Strategy and Implementation Tracker (Rewritten)

## Purpose

This document is the **single source of truth** for the LedFx now-playing integration.

It combines:

* feature intent
* architectural decisions
* implementation plan
* file-level work items
* progress tracking
* recovery guidance for Copilot context loss

This document must remain **accurate to reality**. If assumptions change (as they have), this document must be rewritten—not patched.

---

## Critical correction (must be understood)

The original design assumed:

> `aionowplaying` provides cross-platform now-playing metadata.

This is **incorrect**.

`aionowplaying` is a **publisher** (used to expose what *our app* is playing to the OS), not a **reader** of platform media sessions.

### Therefore:

* `aionowplaying` is **not suitable** for this feature
* The integration must be based on **platform media readers**
* The current PR direction (Windows SMTC) is aligned with the *real problem*

This is not a minor change—it redefines the provider layer.

---

## Feature goal (unchanged)

LedFx must:

1. Observe current now-playing metadata from the platform
2. Obtain album art
3. Optionally derive a color palette from that art
4. Optionally apply that palette to running effects
5. Emit events to clients
6. Remain extensible for future reinforcement

---

## Core design position (corrected)

### Reality-based provider strategy

We are solving:

> “What is currently playing on this system?”

There is no cross-platform API. The correct approach is:

* **Windows → SMTC (GlobalSystemMediaTransportControlsSessionManager)**
* **Linux → MPRIS (D-Bus)**
* **macOS → limited / app-specific approaches**

### Architectural rule

We do **not** build a large abstraction system.

We do:

* build a **small LedFx-owned integration seam**
* implement **one provider per platform as needed**
* keep all platform-specific logic isolated

---

## Architecture overview

### Subsystem layout

```
ledfx/nowplaying/
    manager.py
    models.py
    providers/
        base.py
        windows_smtc.py
        linux_mpris.py (future)
        macos_stub.py (future)
```

---

## Responsibilities

### Manager (unchanged, this part was correct)

Owns:

* lifecycle
* dedupe and stabilisation
* album art resolution
* caching
* palette generation
* palette application
* event emission
* current state

### Provider (corrected role)

Owns:

* reading platform metadata
* converting it into normalized track data
* pushing updates to manager

Providers must be:

* isolated
* replaceable
* minimal

---

## Provider contract

Keep it minimal:

```python
class NowPlayingProvider(Protocol):
    async def start(callback) -> None: ...
    async def stop() -> None: ...
```

No registry, no scoring, no abstraction framework.

---

## Initial provider (corrected)

### Windows SMTC provider (primary implementation)

This is now the **actual first provider**.

Responsibilities:

* use `winrt-windows-media-control`
* read active media session
* subscribe or poll updates
* normalize metadata

### Linux / macOS

* explicitly **not implemented in v1**
* stubs allowed
* must fail cleanly

---

## Remove `aionowplaying`

### Required action

* remove dependency
* remove references
* remove misleading naming

### Reason

* wrong direction (publisher vs reader)
* adds confusion and maintenance burden
* provides no value to this feature

---

## Normalized model (keep, this was good)

Keep the existing `NowPlayingTrack` and `NowPlayingState` models.

They are correct and decoupled from provider specifics.

---

## Track change and dedupe (keep)

The signature-based dedupe logic is correct.

Ensure:

* no repeated palette churn
* no repeated art fetch
* no event spam

---

## Album art (keep, lightly refine)

Keep:

* URL-based fetch
* bounded cache
* async resolution

Ensure:

* strict timeout
* no blocking
* cache bounded

---

## Palette generation (keep)

Correct approach:

* reuse existing `extract_gradient_metadata`
* do not duplicate logic

---

## Palette application (needs tightening)

Add explicit rules:

* apply only on real track change
* skip identical palettes
* skip unsupported effects
* do not fail entire update if one effect fails

---

## Events (keep, but clarify intent)

Events are correct and should remain:

* `NOW_PLAYING_UPDATED`
* `NOW_PLAYING_ART_UPDATED`
* `NOW_PLAYING_PALETTE_UPDATED`

Ensure:

* stable payload shape
* no large raw dumps
* only emit on meaningful change

---

## REST surface (keep)

`GET /api/now-playing` is valid and useful.

---

## Logging (tighten slightly)

Avoid spam:

* log track changes at INFO
* repeated dedupe decisions at DEBUG
* failures at WARN
* startup failures at ERROR

---

## Failure model (keep)

Fail-soft is correct.

Never impact:

* audio pipeline
* rendering
* startup

---

## Startup / lifecycle (keep)

* start only when enabled
* async start
* clean shutdown

---

## Configuration (corrected)

Remove provider illusion:

```json
"now_playing": {
  "enabled": false,
  "generate_palette_from_album_art": false,
  "apply_palette_to_running_effects": false,
  "debounce_ms": 1500,
  "minimum_track_stable_ms": 750
}
```

No fake “provider=aionowplaying”.

---

## Testing (adjust focus)

Add tests for:

* Windows provider normalization
* dedupe behavior
* palette application logic
* failure paths

Do not test `aionowplaying`.

---

## Implementation correction checklist

### Must fix immediately

* [x] remove `aionowplaying` dependency
* [x] rename provider to reflect reality (platform_media / Windows SMTC)
* [x] remove misleading comments/docs
* [x] update strategy document (this rewrite)

### Keep as-is

* [x] manager
* [x] models
* [x] event design
* [x] art + palette pipeline

### Improve

* [x] palette application robustness (identical palette skip, per-effect skip)
* [x] effect filtering (unified GradientEffect + _config check)
* [x] logging clarity

---

## Progress tracker (reset truthfully)

* Architecture: correct (after rewrite)
* Provider: platform_media (Windows SMTC, real)
* Cross-platform: not yet
* aionowplaying: removed
* Feature completeness: ~85%

---

## Copilot implementation prompt (corrected)

```text
We are implementing a now-playing feature for LedFx.

IMPORTANT CORRECTION:
aionowplaying is NOT a valid dependency for this feature.
It is a publisher, not a reader.
Do not use it.

Instead:
- Use platform-native media session APIs
- Current implementation uses Windows SMTC

Your task:

1. Remove aionowplaying dependency and references
2. Rename provider to reflect actual implementation
3. Keep manager/event/palette architecture
4. Ensure clean separation between provider and manager
5. Harden palette application logic
6. Ensure dedupe prevents repeated updates
7. Keep feature fail-soft

Do NOT:
- reintroduce aionowplaying
- build a large abstraction framework
- overcomplicate provider system

Focus on making the current architecture correct and honest.
```

---

## Recovery guidance

If context is lost:

Re-anchor on this:

> The problem is reading platform now-playing state, not publishing it.

Then:

1. verify provider reads system state
2. verify manager handles normalization + palette
3. verify events flow correctly

Do not reintroduce the original incorrect assumption.

---

## Final note

The architecture itself was not wrong.

The dependency assumption was.

Correct that, and the majority of the work remains valid.
