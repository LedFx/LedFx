# LedFx Now Playing Integration Strategy and Implementation Tracker

## Purpose

This document is the **single source of truth** for the `aionowplaying`-based now playing integration in LedFx.

It is intentionally designed to survive GitHub Copilot context loss. It combines:

- feature intent,
- architectural decisions,
- implementation plan,
- file-level work items,
- progress tracking,
- recovery notes for resuming work,
- a Copilot implementation prompt.

Do **not** split this into a separate design doc and implementation doc. Keep all ongoing decisions and progress updates here.

---

## Feature goal

Add a new LedFx subsystem that can:

1. observe current now-playing metadata using `aionowplaying` as the initial backend,
2. obtain album art for the active track when available,
3. optionally derive a color palette from that album art using existing LedFx palette/color capabilities,
4. optionally apply that palette to all currently running effects using existing LedFx mechanisms,
5. emit LedFx backend events so connected clients can react in real time,
6. remain extensible so future reinforcement backends can be added without redesigning the feature.

The first user-visible outcome is:

> when now playing changes, LedFx can fetch album art, derive a palette from it, and switch active effects to that palette if enabled.

---

## Desired product behaviour

When enabled:

- LedFx starts a now-playing manager during normal runtime startup.
- The manager listens for metadata updates from the configured provider.
- When a track change is detected and stabilised:
  - LedFx normalises the metadata,
  - emits a now-playing event to clients,
  - resolves album art,
  - optionally derives a palette from the album art,
  - optionally applies that palette to all currently running effects,
  - emits follow-up events for album art and palette actions.

When disabled or unavailable:

- LedFx continues running normally.
- No effect rendering or audio pipeline functionality should be impacted.
- The subsystem should fail soft and log clearly.

---

## Non-goals for v1

Not part of the first implementation:

- direct Spotify API integration,
- direct browser extension integration,
- YouTube Music-specific handling,
- trying to perfectly arbitrate every platform/media-session edge case,
- new image analysis algorithms if existing LedFx functionality can already generate palettes,
- a fully polished client UI beyond surfacing backend events and current state,
- persistent history of track changes,
- rollback to prior palettes when playback stops.

---

## Core design position

### Why `aionowplaying` first

Use `aionowplaying` as the first backend because it reduces LedFx-owned cross-platform surface area.

That is the right default for a multi-platform project: prefer a thin existing dependency over LedFx re-owning Windows/Linux/macOS now-playing plumbing.

### Why still keep one small integration seam

We do **not** want a large LedFx-owned abstraction framework.

We **do** want one small, localised seam so the integration can later be reinforced if real-world edge cases require it.

This seam should be no larger than necessary:

- one manager,
- one normalized track model,
- one tiny provider contract,
- one initial provider implementation.

That is not speculative architecture. It is the minimum shape that allows later hardening without scattering dependency-specific logic across LedFx.

### Surface area rule

All direct `aionowplaying` usage must live in one provider file.

The rest of LedFx should only depend on:

- normalized now-playing state,
- LedFx events,
- optional REST endpoint state,
- existing palette/effect update flows.

---

## Architecture overview

### New subsystem layout

Suggested files:

- `ledfx/nowplaying/__init__.py`
- `ledfx/nowplaying/manager.py`
- `ledfx/nowplaying/models.py`
- `ledfx/nowplaying/providers/__init__.py`
- `ledfx/nowplaying/providers/base.py`
- `ledfx/nowplaying/providers/aionowplaying_provider.py`

Possible future reinforcement backends:

- `ledfx/nowplaying/providers/linux_mpris_fallback.py`
- `ledfx/nowplaying/providers/windows_smtc_fallback.py`
- `ledfx/nowplaying/providers/browser_bridge.py`

### Responsibilities

#### Manager

Owns:

- lifecycle,
- active state,
- dedupe/debounce/stabilisation,
- album art resolution,
- album art caching,
- palette generation trigger,
- palette application trigger,
- LedFx event emission,
- optional REST-facing current state,
- future multi-provider arbitration if needed.

#### Provider

Owns only:

- metadata acquisition,
- conversion into normalized updates,
- feeding updates into the manager.

Provider must **not**:

- apply palettes,
- mutate effects,
- talk directly to websocket clients,
- own cache storage,
- own REST endpoints.

---

## Normalized model

### Track model

Use a conservative normalized model that is useful now and stable later.

```python
from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class NowPlayingTrack:
    source_id: str | None
    provider: str
    player_name: str | None
    title: str | None
    artist: str | None
    album: str | None
    art_url: str | None
    duration: float | None
    position: float | None
    is_playing: bool | None
    raw: dict[str, Any] | None = None
```

Notes:

- `provider` is explicit so events remain interpretable later.
- `raw` exists for diagnostics and future fallback logic.
- Avoid overfitting to `aionowplaying` field names.

### State model

```python
@dataclass(slots=True)
class NowPlayingState:
    enabled: bool
    status: str  # disabled, idle, starting, running, degraded, error
    provider_name: str | None
    active_track: NowPlayingTrack | None
    active_art_url: str | None
    active_art_cache_key: str | None
    active_palette_id: str | None
    palette_applied: bool
    last_update_ts: float | None
    last_track_signature: str | None
    last_error: str | None = None
```

---

## Provider contract

Keep this deliberately small.

```python
from typing import Awaitable, Callable, Protocol

class NowPlayingProvider(Protocol):
    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None: ...

    async def stop(self) -> None: ...
```

That is enough for v1.

Do not add provider registries, priorities, scores, confidence weighting, or arbitration logic yet.

---

## Initial provider: `AioNowPlayingProvider`

This provider must:

- import and isolate `aionowplaying`,
- subscribe or poll according to the library’s actual model,
- normalize incoming payloads,
- convert empty strings to `None` where sensible,
- guard against missing fields,
- push `NowPlayingTrack` into the manager callback,
- handle missing dependency or unsupported platform cleanly.

Rules:

- all direct `aionowplaying` references stay in this file,
- import failure must not break LedFx startup when the feature is disabled,
- if enabled but unavailable, the manager should enter a degraded/error state with clear logs.

---

## Configuration

Add a new top-level config section, for example:

```json
"now_playing": {
  "enabled": false,
  "provider": "aionowplaying",
  "generate_palette_from_album_art": false,
  "apply_palette_to_running_effects": false,
  "debounce_ms": 1500,
  "minimum_track_stable_ms": 750,
  "art_fetch_timeout_ms": 5000,
  "art_cache": true,
  "art_cache_max_items": 64
}
```

### Semantics

- `enabled`: master feature switch
- `provider`: initial value `aionowplaying`
- `generate_palette_from_album_art`: derive palette when album art changes
- `apply_palette_to_running_effects`: push that palette to running effects
- `debounce_ms`: suppress repeated equivalent updates
- `minimum_track_stable_ms`: optional stabilisation before artwork/palette action
- `art_fetch_timeout_ms`: bound external artwork fetch latency
- `art_cache`: enable cache reuse
- `art_cache_max_items`: prevent unbounded cache growth

Keep this feature opt-in initially.

---

## Track change and dedupe behaviour

The manager should compute a track signature using the best stable fields available, for example:

- provider
- player_name
- title
- artist
- album
- art_url

A metadata update should be treated as meaningful when:

- the signature changes, or
- the art URL changes, or
- the playing state changes in a way that matters to clients.

The manager should avoid:

- re-fetching identical art repeatedly,
- regenerating the same palette repeatedly,
- reapplying an identical palette on every refresh,
- spamming events for semantically identical updates.

---

## Album art strategy

### Primary path

Use the `art_url` supplied by metadata if available.

### Resolution flow

1. track change arrives,
2. dedupe/stabilisation passes,
3. manager resolves art URL,
4. manager downloads or reuses cached art,
5. manager exposes cache key / local path / LedFx-served URL,
6. manager emits event that includes the artwork reference,
7. optional palette extraction runs from the resolved image.

### Caching

Prefer bounded caching.

Cache key can be based on:

- art URL,
- or stable hash of URL/track signature.

Do not let cache grow unbounded.

### Failure handling

If artwork fetch fails:

- log at warning/debug as appropriate,
- keep metadata event flowing,
- skip palette generation,
- do not treat as fatal.

---

## Palette generation strategy

Requirement: reuse existing LedFx palette/color extraction capability.

Do **not** introduce a parallel custom palette extraction mechanism unless existing functionality genuinely cannot be reused.

### Expected flow

1. manager receives resolved album art image,
2. manager invokes existing LedFx capability to derive a palette,
3. manager stores the derived palette in the most natural existing LedFx form,
4. manager records the palette identifier or equivalent state reference,
5. manager optionally applies it to running effects,
6. manager emits a palette event.

### Important constraint

The manager should call into existing palette APIs/utilities, not duplicate their logic.

---

## Applying palette to running effects

Requirement: reuse existing LedFx effect/config update paths.

Do not special-case individual effects unless current LedFx architecture forces it.

### Expected behaviour

When `apply_palette_to_running_effects` is enabled and a new derived palette is available:

- enumerate running active effects using the existing LedFx model,
- update each effect using the existing effect configuration/update path,
- only touch effects that support palette/gradient changes through normal mechanisms,
- avoid breaking effects that do not consume palettes in the same way,
- log skipped effects clearly but do not fail the whole operation.

### Important caution

This is where implementation must inspect current LedFx effect configuration flow carefully.

The strategy is to reuse normal update semantics, not patch private internals.

---

## Events

LedFx needs backend events carrying now-playing data to clients.

### Recommendation

Add explicit now-playing events rather than overloading existing unrelated events too heavily.

Suggested event types:

- `NOW_PLAYING_UPDATED`
- `NOW_PLAYING_ART_UPDATED`
- `NOW_PLAYING_PALETTE_UPDATED`

If the existing event model makes this awkward, it is acceptable to extend an existing song-related event, but the cleaner path is dedicated events.

### `NOW_PLAYING_UPDATED` payload

Suggested fields:

- `provider`
- `source_id`
- `player_name`
- `title`
- `artist`
- `album`
- `art_url`
- `is_playing`
- `duration`
- `position`
- `track_signature`
- `timestamp`

### `NOW_PLAYING_ART_UPDATED` payload

Suggested fields:

- `provider`
- `track_signature`
- `art_url`
- `art_cache_key`
- `served_url` or equivalent LedFx-accessible image URL
- `timestamp`

### `NOW_PLAYING_PALETTE_UPDATED` payload

Suggested fields:

- `provider`
- `track_signature`
- `palette_id` or equivalent
- `palette_applied`
- `affected_effects`
- `skipped_effects`
- `timestamp`

### Event emission principles

- emit only on meaningful changes,
- keep payloads stable and explicit,
- keep them client-friendly,
- do not include huge raw provider payloads.

---

## REST surface

Optional but recommended: provide a simple endpoint for current now-playing state.

Suggested endpoint:

- `GET /api/now-playing`

Possible optional endpoints later:

- `POST /api/now-playing/reload`
- `POST /api/now-playing/test-apply`

For v1, `GET /api/now-playing` is enough if the UI or debugging needs it.

Return:

- feature enabled/disabled,
- provider,
- status,
- active track,
- art reference,
- active palette reference,
- last update/error state.

This helps both clients and debugging.

---

## Logging and diagnostics

The subsystem should log at a level that is actually useful in field debugging.

### Info-level

- manager start/stop,
- provider start/stop,
- track change accepted,
- palette apply success summary.

### Debug-level

- ignored duplicate metadata,
- stabilisation waiting,
- artwork cache hits,
- skipped effect updates,
- provider raw field normalization notes.

### Warning-level

- artwork fetch failure,
- palette generation failure,
- partial apply failures,
- provider unavailable while feature enabled.

### Error-level

- hard startup failure of the manager when enabled.

Do not let logs spam on repeated identical updates.

---

## Failure model

The feature must be fail-soft.

### If provider fails

- mark manager state degraded/error,
- keep LedFx running,
- do not interfere with audio or rendering.

### If artwork fetch fails

- keep metadata state,
- skip palette operations,
- keep running.

### If palette generation fails

- keep metadata and art state,
- skip apply,
- keep running.

### If effect update fails for some effects

- continue applying to remaining supported effects,
- emit partial result information,
- do not roll back the entire operation unless current LedFx semantics require atomicity.

---

## Startup and shutdown integration

The now-playing manager should be started and stopped in the normal LedFx lifecycle.

Requirements:

- start only when enabled,
- clean shutdown on LedFx stop/restart,
- no hanging background tasks,
- no blocking of startup on slow metadata/artwork fetches.

If initial provider startup is asynchronous and potentially slow, start it in a controlled background task and expose state as `starting` until ready.

---

## Dependency handling

`aionowplaying` should be added as an optional/managed dependency consistent with current LedFx packaging policy.

Implementation must inspect current dependency management and Python version support before finalizing.

Requirements:

- do not break supported LedFx Python versions,
- ensure import failure is handled cleanly,
- document platform caveats.

---

## Testing strategy

### Unit tests

Add tests for:

- track normalization,
- signature generation,
- dedupe/debounce behaviour,
- art cache key generation,
- palette generation trigger logic,
- event payload shape,
- provider unavailable behaviour.

### Mocked manager/provider tests

Use a fake provider to simulate:

- first track,
- repeated same track,
- art URL change only,
- missing fields,
- playback stop,
- provider exception.

### Integration-style tests

If practical, add manager tests that mock:

- image fetch,
- palette generation utility,
- effect update path,
- event dispatch path.

### Manual validation targets

At minimum validate on:

- Windows,
- Linux,
- at least one browser-backed or native media source,
- track changes with and without album art,
- multiple running effects,
- feature disabled behaviour.

---

## Implementation phases

### Phase 1: subsystem skeleton

- create now-playing package,
- add normalized models,
- add provider protocol,
- add manager skeleton,
- wire config scaffold.

### Phase 2: `aionowplaying` provider

- isolate dependency,
- implement provider start/stop,
- normalize updates,
- add basic manager ingest path.

### Phase 3: events and state exposure

- add event classes/types,
- emit now-playing update events,
- add optional current-state endpoint.

### Phase 4: album art

- implement art resolution,
- add bounded cache,
- emit art update event.

### Phase 5: palette generation and apply

- integrate existing palette extraction,
- integrate existing effect update flow,
- emit palette update event.

### Phase 6: tests and hardening

- add unit/integration tests,
- add logs,
- validate shutdown, repeated updates, degraded states.

---

## File-level implementation checklist

This section is intended to be updated during work.

### New files expected

- [x] `ledfx/nowplaying/__init__.py`
- [x] `ledfx/nowplaying/models.py`
- [x] `ledfx/nowplaying/manager.py`
- [x] `ledfx/nowplaying/providers/__init__.py`
- [x] `ledfx/nowplaying/providers/base.py`
- [x] `ledfx/nowplaying/providers/platform_media_provider.py` (renamed from `aionowplaying_provider.py` — see note below)
- [x] `ledfx/api/now_playing.py`
- [x] `tests/test_now_playing.py`

**Provider file naming note:** `aionowplaying` turned out to be a media-session *publisher* library (for advertising what your app plays), not a *reader*. The initial provider (`platform_media_provider.py`) reads Windows SMTC sessions directly via `winrt-windows-media-control`. The `aionowplaying` dependency is retained for potential future use.

### Existing files changed

- [x] `ledfx/core.py` — startup/lifecycle wiring (`NowPlayingManager` instantiated in `async_start`)
- [x] `ledfx/config.py` — `now_playing` section added to `CORE_CONFIG_SCHEMA`
- [x] `ledfx/events.py` — three new event types and classes added
- [x] `pyproject.toml` — `aionowplaying` and `winrt-windows-media-control` added as dependencies
- [ ] websocket/event broadcasting path — not needed; events flow through existing `Events` system
- [x] REST API registration — auto-discovered via `ledfx/api/now_playing.py`
- [x] palette/color utility integration — reuses `extract_gradient_metadata` from `ledfx/utilities/gradient_extraction.py`
- [x] effect update/config path — uses `effect.update_config({"gradient": ...})` via `GradientEffect` check

### Mandatory implementation checks

- [x] all platform-specific media reading isolated to one provider file
- [x] manager is fail-soft
- [x] repeated identical tracks do not churn art/palette/apply
- [x] no unbounded image cache growth (bounded `OrderedDict` with configurable max)
- [x] no blocking startup on artwork fetch (async with timeout)
- [x] no direct provider-to-client coupling
- [x] effect updates use existing LedFx mechanisms (`update_config`)
- [x] event payloads are stable and explicit

---

## Progress tracker

Update this section during implementation. Keep it current.

### Status summary

- Current phase: Phase 6 (tests and hardening) — initial implementation complete
- Branch / PR: `flac_part_2`
- Last updated: 2026-04-12

### Completed

- [x] strategy agreed
- [x] provider contract implemented
- [x] manager implemented
- [x] `aionowplaying` provider implemented (adapted: uses platform media reading instead of aionowplaying publisher API)
- [x] config added
- [x] events added
- [x] REST endpoint added
- [x] album art fetch/cache added
- [x] palette extraction wired
- [x] palette apply to running effects wired
- [x] tests added (23 tests, all passing)
- [ ] docs added

### In progress

- None

### Blockers / open questions

- **Resolved:** `aionowplaying` is a publisher library, not a reader. The initial provider uses `winrt-windows-media-control` on Windows to read media sessions directly. `aionowplaying` retained as dependency for future use.
- **Resolved:** Existing `extract_gradient_metadata()` from `ledfx/utilities/gradient_extraction.py` reused for palette extraction.
- **Resolved:** `effect.update_config({"gradient": ...})` via `GradientEffect` isinstance check used for palette application.
- **Resolved:** Dedicated event classes (`NowPlayingUpdatedEvent`, `NowPlayingArtUpdatedEvent`, `NowPlayingPaletteUpdatedEvent`) added — cleaner than extending existing events.
- **Resolved:** `GET /api/now-playing` included in initial implementation.
- Linux/macOS provider backends not yet implemented (platform_media_provider.py has stubs).
- No persistent history of track changes (non-goal for v1).

### Notes for resuming work

When resuming after context loss, first inspect:

1. the current contents of this document,
2. the actual `aionowplaying` API,
3. current LedFx event definitions,
4. existing palette extraction utilities,
5. current effect update/config flow,
6. startup/shutdown lifecycle integration points.

Then update the progress tracker before making new structural decisions.

---

## Implementation guidance for GitHub Copilot

Use this guidance when asking Copilot to continue work.

### Copilot operating rules

- Respect existing LedFx architecture and coding style.
- Reuse existing functionality rather than duplicating it.
- Keep changes incremental and reviewable.
- Do not invent broad new frameworks.
- Keep all direct `aionowplaying` usage in one provider file.
- Prefer small, well-named functions over sprawling logic.
- Add tests alongside implementation.
- Update this strategy document as progress is made.

### Specific architectural guardrails

- Do not create a large provider registry system.
- Do not build LedFx-owned cross-platform now-playing backends for all OSes.
- Do not hardcode service-specific assumptions like Spotify-only logic.
- Do not bypass normal effect update/configuration paths.
- Do not create parallel palette extraction logic if existing LedFx capability already exists.
- Do not let artwork caching grow unbounded.
- Do not block core startup on provider/artwork operations.

---

## Copilot implementation prompt

Use the following prompt with GitHub Copilot. Keep this prompt in this document so progress can be resumed from one place.

```text
Implement a now-playing integration for LedFx using `aionowplaying` as the initial metadata backend.

Read and follow the strategy in `strategy.md` exactly. This file is the single source of truth for both design and implementation tracking. Update its progress tracker as you complete work.

High-level requirements:

1. Add a new LedFx now-playing subsystem that is enabled by config and started/stopped with normal LedFx lifecycle.
2. Use `aionowplaying` as the first backend, but keep the integration localized so future provider reinforcement is possible without redesign.
3. The subsystem must normalize track metadata into a LedFx-owned model.
4. On meaningful track changes, emit LedFx backend events suitable for clients.
5. Resolve album art when available.
6. If enabled, derive a palette from the album art using existing LedFx palette/color functionality.
7. If enabled, apply that derived palette to all currently running effects using existing LedFx update/config mechanisms.
8. Fail soft. LedFx must keep running if metadata, art fetch, palette generation, or palette application fails.

Architecture constraints:

- All direct `aionowplaying` usage must live in one provider file.
- Keep the provider contract minimal.
- Do not build a broad plugin framework.
- Reuse existing LedFx event, API, palette, and effect update patterns wherever possible.
- Avoid repeated churn: dedupe identical metadata, avoid repeated art fetches, avoid reapplying identical palettes.
- Add tests.

Implementation steps:

A. Inspect current LedFx startup/lifecycle, event system, palette extraction utilities, effect update/config flow, and REST endpoint conventions.
B. Add the now-playing subsystem files from the strategy.
C. Add config support.
D. Implement the `aionowplaying` provider based on the library’s actual current API.
E. Add dedicated now-playing events or the cleanest equivalent consistent with LedFx’s current event architecture.
F. Add bounded album art fetch/caching.
G. Wire palette extraction to existing LedFx functionality.
H. Wire palette application to running effects through normal update mechanisms.
I. Add tests.
J. Update `strategy.md` progress tracker with what was completed, what remains, and any blockers.

Deliverables:

- complete code changes,
- tests,
- minimal docs/comments where helpful,
- updated `strategy.md` progress section.

Before making major structural choices, prefer the smallest implementation that satisfies the strategy and fits existing LedFx architecture.
```

---

## Recovery prompt for Copilot after context loss

Use this when Copilot loses context mid-implementation.

```text
Resume implementation of the LedFx now-playing feature.

First, read `strategy.md` fully. It is the single source of truth for both architecture and implementation progress.

Then inspect the current code changes already made and compare them to the file-level checklist and progress tracker in `strategy.md`.

Do not redesign the architecture. Continue from the current plan.

Priorities when resuming:
1. finish any partially implemented file,
2. add or repair tests for that work,
3. update the progress tracker in `strategy.md`,
4. only then move to the next unchecked item.

Keep all direct `aionowplaying` usage in one provider file and reuse existing LedFx mechanisms for events, palettes, and effect updates.
```

---

## Acceptance criteria

The feature is ready for review when all of the following are true:

- LedFx can start with the feature disabled and behave exactly as before.
- LedFx can start with the feature enabled without crashing if no now-playing source is available.
- A track change can produce a normalized now-playing event.
- Album art can be resolved when metadata provides it.
- A palette can be derived from that album art using existing LedFx capability.
- That palette can be applied to running effects using existing LedFx mechanisms when enabled.
- Repeated identical metadata does not cause repeated churn.
- Failures in any part of the feature do not destabilize LedFx.
- Tests cover the manager/provider/event behaviour sufficiently for confidence.
- `strategy.md` progress tracker reflects the actual implementation state.

---

## Final note

This document should stay with the PR and continue to be updated while the work is active.

It is not just a proposal. It is the implementation map and recovery anchor.
