# LedFx Now Playing Service - Design Proposal

## Purpose

This proposal introduces a centralized **Now Playing Service** for LedFx.

The service is intended to provide one internal source of truth for:

- current track metadata
- current album artwork
- current artwork-derived gradients
- temporary or continuous track text display
- temporary or continuous album artwork display
- provider-neutral media events
- future metadata providers beyond Sendspin

The first implementation target should be **Sendspin**, but the design should not be Sendspin-specific.

Future providers may include:

- Music Assistant
- Spotify
- YouTube Music
- Linux MPRIS
- Windows media session APIs
- browser integrations
- local file playback integrations
- REST/websocket integrations

---

## Important Existing LedFx Capability

LedFx already has an image-to-gradient extraction system.

This proposal should build on that system rather than creating a separate album-art gradient generator.

The existing gradient extraction system:

- extracts LED-optimized gradients from loaded images
- supports album art, user uploads, cached images, and assets
- produces multiple variants:
  - `led_safe`
  - `led_punchy`
  - `led_max`
- stores gradient metadata alongside cached image/asset metadata
- exposes gradient metadata through existing image/cache/asset APIs
- avoids runtime extraction cost after the image has been loaded and cached

The Now Playing design should therefore treat album artwork as an image entering the existing image/cache pipeline.

---

## Current LedFx Gradient Extraction Architecture

Current documented flow:

```text
Image Source
    ↓
Image Loading
    ↓
PIL Image
    ↓
Metadata Extraction
    ↓
Gradient Extraction
    ↓
Cache / Asset Metadata
    ↓
Frontend / Effects
```

The existing implementation has two main integration points:

```text
ImageCache
    - extracts gradients during cache put()
    - skips thumbnails
    - stores gradient metadata in cache metadata

Asset Storage
    - extracts gradients during asset listing
    - caches metadata in .asset_metadata_cache.json
    - invalidates when files change
```

The Now Playing Service uses the Asset Storage path via `save_asset()` and `list_assets()`.

---

## Design Rule

Do not implement a new one-off album-art-to-gradient path.

Instead:

```text
Provider artwork
    ↓
Now Playing Service
    ↓
save_asset() → assets/now_playing/now_playing.{ext}
    ↓
list_assets() → .asset_metadata_cache.json with gradients
    ↓
Gradient applied to target virtuals via apply_global code path
```

---

## Existing Gradient Variants

The Now Playing Service should expose a configurable preferred gradient variant:

```text
led_safe
led_punchy
led_max
```

Suggested default:

```text
led_punchy
```

Rationale:

- `led_safe` is closest to the source image
- `led_punchy` is likely the best default for physical LEDs
- `led_max` is useful for high-impact visuals, but may be too aggressive for all users

---

## High-Level Architecture

```text
Metadata Providers
    ↓
Now Playing Service
    ↓
Normalized Metadata + Artwork Reference
    ↓
Existing Image Cache / Gradient Extraction
    ↓
Events
    ↓
Consumers
```

Consumers may include:

- current track gradient alias
- text display fallback effect
- album-art display fallback effect
- yzflow routing
- frontend UI
- future automations

---

## Core Design Principles

### 1. Providers Publish State

Providers only publish normalized metadata and artwork references/data.

Providers should not:

- directly change effects
- directly switch virtuals
- directly create gradients
- directly route displays

---

### 2. Now Playing Owns Current Media State

The Now Playing Service owns:

- active source
- current metadata
- current artwork reference
- artwork cache status
- selected gradient variant
- display routing configuration

---

### 3. Existing LedFx Image Infrastructure Owns Gradient Extraction

Gradient extraction remains owned by the existing image/cache/asset system.

The Now Playing Service should request or cause artwork to enter that pipeline, then consume the resulting gradient metadata.

---

### 4. Effects Remain Provider-Agnostic

Effects should not know whether the current track came from:

- Sendspin
- Spotify
- YouTube Music
- Music Assistant
- any future provider

Effects should consume LedFx-native concepts:

- gradients
- images
- events

---

## Proposed Service Name

```text
ledfx.now_playing
```

---

## Proposed Data Models

### TrackMetadata

```python
@dataclass
class TrackMetadata:
    source_id: str

    title: str | None = None
    artist: str | None = None
    album: str | None = None

    duration: float | None = None
    position: float | None = None

    track_id: str | None = None

    artwork_url: str | None = None
    artwork_hash: str | None = None

    updated_at: float | None = None
```

---

### ArtworkReference

Prefer an artwork reference over permanently storing a PIL image in the Now Playing state.

```python
@dataclass
class ArtworkReference:
    source_id: str

    url: str | None = None
    cache_key: str | None = None
    asset_path: str | None = None

    content_type: str | None = None
    hash: str | None = None

    width: int | None = None
    height: int | None = None

    gradients: dict | None = None
```

---

### NowPlayingState

```python
@dataclass
class NowPlayingState:
    active_source_id: str | None = None

    metadata: TrackMetadata | None = None
    artwork: ArtworkReference | None = None

    selected_gradient_variant: str = "led_punchy"
    current_gradient: str | None = None

    updated_at: float | None = None
```

---

## Proposed Internal API

### Set Metadata

```python
ledfx.now_playing.set_metadata(source_id, metadata)
```

Responsibilities:

- normalize metadata
- compare against current metadata
- detect track changes
- fire metadata/track events as appropriate

---

### Set Artwork URL

```python
ledfx.now_playing.set_artwork_url(
    source_id,
    artwork_url,
    content_type=None,
    artwork_hash=None,
)
```

Responsibilities:

- store artwork reference
- optionally trigger download/cache
- use existing image cache pipeline
- collect gradient metadata from cached image entry
- update current track gradient alias

---

### Set Artwork Bytes

```python
ledfx.now_playing.set_artwork_bytes(
    source_id,
    data,
    content_type,
    artwork_hash=None,
)
```

Responsibilities:

- support providers that supply image bytes instead of a URL
- store/cache image through a path compatible with existing image cache behavior
- extract gradients using the existing gradient extraction code path
- update artwork reference and current gradient

---

### Clear Provider

```python
ledfx.now_playing.clear(source_id)
```

Responsibilities:

- clear provider-owned state
- clear current state if this provider is active
- fire clear event

---

### Get Current State

```python
ledfx.now_playing.get_current()
```

Returns the normalized current state.

---

## How Album Art Should Enter the Existing Gradient System

There are two practical cases.

---

### Case 1: Artwork Provider Supplies a URL

Preferred flow:

```text
artwork_url
    ↓
download with security validation
    ↓
save_asset(config_dir, "now_playing/now_playing.{ext}", data, allow_overwrite=True)
    ↓
list_assets() → asset metadata cache with gradients
    ↓
Now Playing reads selected variant
```

This uses LedFx's asset management system which provides:
- path traversal protection
- content validation (extension, MIME, PIL format)
- size limits
- atomic writes
- metadata caching with gradient extraction
- thumbnail cache invalidation

---

### Case 2: Artwork Provider Supplies Raw Bytes

Preferred flow:

```text
artwork bytes
    ↓
save_asset(config_dir, "now_playing/now_playing.{ext}", data, allow_overwrite=True)
    ↓
list_assets() → asset metadata cache with gradients
    ↓
Now Playing reads selected variant
```

Artwork is stored at a fixed path `assets/now_playing/now_playing.{ext}` and overwritten on each change. The asset system handles extension changes by deleting old files first.

---

## Gradient Application via Globals API

Instead of exposing a `system/current_track` gradient alias that effects must individually select, the Now Playing Service applies the current track gradient directly to target virtuals using the same code path as the `apply_global` action on `PUT /api/effects`.

This approach:

- avoids changes to gradient pickers or effect schemas
- reuses the existing, tested `apply_global` logic (key filtering, HIDDEN_KEYS, color group sampling, config persistence)
- gives the user a simple virtual list picker: "apply Now Playing gradients to these virtuals"
- supports an "all virtuals" option naturally (omit or empty list = all)
- keeps effects completely provider-agnostic — they receive a normal gradient update, not a special alias

---

## Gradient Application Configuration

Now Playing configuration should include:

```json
{
  "gradient": {
    "enabled": true,
    "variant": "led_punchy",
    "virtual_ids": []
  }
}
```

- `enabled`: whether to apply gradients on track change
- `variant`: which extracted variant to use (`led_safe`, `led_punchy`, `led_max`)
- `virtual_ids`: list of virtual ids to target. Empty list means all virtuals (same semantics as the globals API `virtuals` field)

Supported variants:

```text
led_safe
led_punchy
led_max
```

When the selected variant changes, the service can re-resolve from cached metadata without re-extracting the image.

---

## Gradient Update Flow

```text
now_playing_artwork_changed
    ↓
ensure artwork is cached
    ↓
retrieve existing extracted gradients
    ↓
select configured variant
    ↓
store resolved gradient string in state.current_gradient
    ↓
emit now_playing_gradient_changed
    ↓
if gradient.enabled:
    apply gradient to target virtuals via apply_global code path
    (gradient + color group sampling, per the globals API behavior)
```

---

## Important Runtime Rule

Do not regenerate gradients every frame.

Gradient extraction should happen only when:

- new artwork is received
- artwork hash changes
- artwork URL changes
- cache is refreshed
- extraction algorithm is manually refreshed

---

## Change Detection

The service should determine whether an update is meaningful.

### No Significant Event

```text
same track
same artwork hash
same artwork URL
same metadata
```

---

### Lightweight Event

```text
same track
new playback position
```

Potential future event:

```text
now_playing_position_changed
```

---

### Significant Events

```text
new track
new title / artist / album
new artwork hash
new artwork URL
new active source
```

---

## Proposed Events

### Initial Events

```text
now_playing_track_changed
now_playing_metadata_changed
now_playing_artwork_changed
now_playing_gradient_changed
now_playing_cleared
```

---

### Future Events

```text
now_playing_position_changed
now_playing_source_changed
now_playing_provider_available
now_playing_provider_lost
```

---

## Proposed REST API

### Get Current Now Playing State

```text
GET /api/now-playing
```

Example response:

```json
{
  "active_source_id": "sendspin",
  "metadata": {
    "title": "Example Track",
    "artist": "Example Artist",
    "album": "Example Album",
    "duration": 240,
    "position": 42,
    "track_id": "example-track-id",
    "artwork_url": "https://example.com/art.jpg",
    "artwork_hash": "abc123"
  },
  "artwork": {
    "url": "https://example.com/art.jpg",
    "cache_key": "abc123",
    "content_type": "image/jpeg",
    "width": 1200,
    "height": 1200",
    "gradients": {
      "led_safe": {
        "gradient": "linear-gradient(...)"
      },
      "led_punchy": {
        "gradient": "linear-gradient(...)"
      },
      "led_max": {
        "gradient": "linear-gradient(...)"
      },
      "metadata": {
        "pattern": "interleaved",
        "has_dominant_background": true
      }
    }
  },
  "current_gradient": {
    "variant": "led_punchy",
    "gradient": "linear-gradient(...)"
  }
}
```

---

## REST Debug/Refresh Support

A future debug endpoint may be useful:

```text
POST /api/now-playing/artwork/refresh
```

Purpose:

- force cache refresh
- force gradient re-extraction
- useful while tuning the extraction algorithm

This should ideally use the existing cache refresh semantics where possible.

---

## Initial Provider: Sendspin

Sendspin should be the first metadata provider.

Responsibilities:

- receive Sendspin metadata
- receive Sendspin artwork URL or artwork data
- normalize into TrackMetadata
- call Now Playing APIs

Sendspin should not:

- directly update gradients
- directly switch effects
- directly choose display virtuals
- directly display artwork

---

## Sendspin Metadata Flow

```text
Sendspin metadata message
    ↓
normalize title / artist / album / duration / position / IDs
    ↓
ledfx.now_playing.set_metadata("sendspin", metadata)
```

---

## Sendspin Artwork Flow

If artwork is URL-based:

```text
Sendspin artwork URL
    ↓
ledfx.now_playing.set_artwork_url("sendspin", url, ...)
```

If artwork is byte-based:

```text
Sendspin artwork bytes
    ↓
ledfx.now_playing.set_artwork_bytes("sendspin", bytes, content_type, ...)
```

---

## Effect Gradient Consumption

Effects do not need to know about Now Playing at all.

When the Now Playing gradient is applied, it flows through the same `apply_global` code path used by the frontend's global configuration controls. Each effect receives a normal gradient + color group update — identical to what happens when a user manually applies a global gradient.

This means:

- no `system/current_track` alias needed
- no gradient picker changes needed
- no effect schema changes needed
- effects remain completely provider-agnostic

---

## Track Text Display

Track metadata changes may optionally trigger text display.

This should be configured centrally in the Now Playing Service, not individually per effect.

---

## Album Artwork Display

Artwork changes may optionally trigger album artwork display.

This should also be configured centrally in the Now Playing Service.

---

## Centralized Display Routing

Display routing should be configured in the Now Playing Service configuration dialog.

Suggested sections:

```text
Now Playing
├─ Metadata Sources
├─ Gradient Application
│   ├─ Enabled
│   ├─ Variant (led_safe / led_punchy / led_max)
│   └─ Target Virtuals (list picker, empty = all)
├─ Track Text Display Targets
└─ Album Artwork Display Targets
```

---

## Matrix Virtual Filtering

Track text and album artwork display target pickers should only show matrix-capable virtuals.

Suggested filter:

```text
rows > 1
```

or the existing LedFx matrix detection logic.

Do not show 1D strip virtuals in these pickers.

---

## Track Text Display Configuration

```json
{
  "track_text": {
    "mode": "temporary",
    "duration": 8,
    "virtual_ids": [
      "matrix1",
      "matrix2"
    ],
    "fallback_effect": "text"
  }
}
```

Supported modes:

```text
off
temporary
continuous
```

---

## Track Text Temporary Mode

```text
now_playing_track_changed
    ↓
save current effect on target virtual
    ↓
switch to text fallback effect
    ↓
display "Artist - Title" for N seconds
    ↓
restore previous effect
```

---

## Track Text Continuous Mode

```text
target virtual remains dedicated to current track text
metadata changes update displayed text
```

---

## Album Artwork Display Configuration

```json
{
  "album_art": {
    "mode": "off",
    "duration": 10,
    "virtual_ids": [
      "album_matrix"
    ],
    "fallback_effect": "image"
  }
}
```

Supported modes:

```text
off
temporary
continuous
```

---

## Album Artwork Temporary Mode

```text
now_playing_artwork_changed
    ↓
save current effect on target virtual
    ↓
switch to artwork/image fallback effect
    ↓
display current artwork for N seconds
    ↓
restore previous effect
```

---

## Album Artwork Continuous Mode

```text
target virtual remains dedicated to current album art
artwork changes update displayed image
```

---

## Proposed Configuration Example

```json
{
  "now_playing": {
    "enabled": true,

    "sources": {
      "sendspin": {
        "enabled": true
      }
    },

    "gradient": {
      "enabled": true,
      "variant": "led_punchy",
      "virtual_ids": []
    },

    "track_text": {
      "mode": "temporary",
      "duration": 8,
      "virtual_ids": [
        "matrix1",
        "matrix2"
      ],
      "fallback_effect": "text"
    },

    "album_art": {
      "mode": "off",
      "duration": 10,
      "virtual_ids": [
        "album_matrix"
      ],
      "fallback_effect": "image"
    }
  }
}
```

---

## yzflow Integration

yzflow should eventually act as an orchestration layer.

Examples:

```text
now_playing_track_changed
    ↓
trigger track text display

now_playing_artwork_changed
    ↓
refresh album art display

now_playing_gradient_changed
    ↓
apply gradient to target virtuals via apply_global code path
```

The Now Playing Service provides the state and events.

yzflow decides what to do with them.

---

# Staged Implementation Plan

## Phase 1 - Now Playing Service Skeleton

Implement:

- `ledfx.now_playing`
- normalized dataclasses
- current state cache
- source-neutral setters
- `get_current()`
- no UI yet
- no effect switching yet

Deliverables:

- service object available from core
- internal API usable by providers
- unit tests for metadata/state updates

---

## Phase 2 - REST Debug Endpoint

Implement:

```text
GET /api/now-playing
```

Deliverables:

- current metadata visible in API
- artwork reference visible in API
- current gradient state visible in API
- useful manual debugging during Sendspin integration

---

## Phase 3 - Now Playing Events

Implement normalized events:

```text
now_playing_track_changed
now_playing_metadata_changed
now_playing_artwork_changed
now_playing_gradient_changed
now_playing_cleared
```

Deliverables:

- event tests
- frontend can subscribe
- yzflow can consume later

---

## Phase 4 - Sendspin Metadata Provider

Implement:

- Sendspin metadata ingestion
- metadata normalization
- calls to `set_metadata("sendspin", metadata)`

Deliverables:

- title/artist/album visible through `/api/now-playing`
- track changes detected
- no artwork or gradients required yet

---

## Phase 5 - Sendspin Artwork Provider Using Asset System

Implement:

- Sendspin artwork URL handling if available
- Sendspin artwork byte handling if needed
- artwork storage via `save_asset()` at `assets/now_playing/now_playing.{ext}`
- gradient extraction via `list_assets()` metadata cache
- no custom gradient extraction path

Deliverables:

- artwork stored as managed asset
- width/height/content type available
- gradient metadata produced by asset metadata cache (`list_assets`)

---

## Phase 6 - Gradient Application via Globals API

Implement:

- gradient application to target virtuals on artwork/gradient change
- reuse `apply_global` code path from `EffectsEndpoint`
- virtual list picker in Now Playing config (empty = all virtuals)

Deliverables:

- selected variant applied as normal gradient + color updates to target virtuals
- uses same key filtering, HIDDEN_KEYS, color group sampling as globals API
- no gradient alias, no gradient picker changes, no effect schema changes
- `now_playing_gradient_changed` emitted
- no per-frame extraction

---

## Phase 7 - Now Playing Configuration

Implement service configuration dialog:

```text
Now Playing
├─ Sources
├─ Gradient Application
│   ├─ Enabled
│   ├─ Variant (led_safe / led_punchy / led_max)
│   └─ Target Virtuals (list picker, empty = all)
├─ Track Text Display Targets
└─ Album Artwork Display Targets
```

Deliverables:

- gradient enable/disable
- gradient variant picker
- gradient target virtual list picker (empty = all virtuals)
- track text mode/duration/virtual picker
- album art mode/duration/virtual picker
- virtual picker filters to matrix virtuals only

---

## Phase 8 - Track Text Temporary Display

Implement:

- temporary fallback text display
- save/restore previous virtual effect
- duration-based restoration

Deliverables:

- target matrix virtuals show track text on track change
- previous effect restored after timeout

---

## Phase 9 - Album Artwork Temporary Display

Implement:

- temporary fallback artwork/image display
- save/restore previous virtual effect
- duration-based restoration

Deliverables:

- target matrix virtuals show album art on artwork change
- previous effect restored after timeout

---

## Phase 10 - Continuous Display Modes

Implement:

- continuous track text virtuals
- continuous album art virtuals

Deliverables:

- selected virtuals stay dedicated to Now Playing display
- updates happen on metadata/artwork changes

---

## Phase 11 - yzflow Integration

Implement:

- event routing
- gradient routing
- optional display triggers

Deliverables:

- yzflow can orchestrate Now Playing behavior
- Now Playing remains source-of-truth
- effects remain provider-agnostic

---

## Phase 12 - Additional Providers

Add providers incrementally.

Candidate order:

1. Music Assistant native metadata, if available separately from Sendspin
2. Linux MPRIS
3. Windows media session
4. Spotify
5. YouTube Music
6. browser/manual websocket provider

Each provider only needs to publish normalized state:

```python
set_metadata(...)
set_artwork_url(...)
set_artwork_bytes(...)
clear(...)
```

---

# Open Design Questions

## Source Priority

If multiple providers are active, which one wins?

Initial answer:

```text
Single active provider only.
First implementation uses Sendspin.
```

Future options:

- explicit provider priority
- most recently updated source wins
- user-selected active provider
- provider bound to audio input

---

## Artwork Storage

Should Now Playing artwork be:

```text
cache only
```

or:

```text
asset persisted
```

**Resolved**: Asset persisted at `assets/now_playing/now_playing.{ext}`.

Rationale:

- uses the existing asset management system (`save_asset`/`list_assets`)
- gets security validation, atomic writes, and metadata caching for free
- gradient extraction is handled by `list_assets` metadata cache
- single fixed path avoids accumulation (overwritten each time)
- no synthetic cache URL needed — uses standard asset path
- metadata alignment across the system is maintained

---

## Current Track Gradient Persistence

Should the current gradient be serialized?

Initial answer:

```text
No.
```

The resolved gradient string is kept in memory (`state.current_gradient`) and applied to target virtuals on each artwork change. The per-virtual effect configs are persisted normally through the existing `save_config` path (same as when a user applies a global gradient manually).

---

## Fallback Effect Contract

Need to define how Now Playing temporarily switches to fallback effects and restores previous effects.

Important concerns:

- existing effect state restoration
- scene interactions
- user manually changing effect during temporary display
- virtual stopped/disabled during temporary display
- multiple track changes inside the display duration

---

# Summary

This design adds a provider-neutral Now Playing Service while reusing LedFx's existing image-to-gradient infrastructure.

Key decisions:

- Sendspin is the first provider, not the owner of the feature
- album art enters the existing image cache / gradient extraction path
- gradients are extracted once and cached
- gradients are applied to target virtuals via the existing `apply_global` code path (same as the frontend global configuration controls)
- no `system/current_track` alias needed — effects receive normal gradient updates
- no gradient picker changes needed — users configure target virtuals in Now Playing config
- users can select specific virtuals or all virtuals for gradient application
- track text and album art display routing is centralized in Now Playing config
- display target pickers only show matrix virtuals
- effects remain provider-agnostic
- yzflow can later orchestrate events and routing

---
---

# Implementation Plan

## Status Key

| Symbol | Meaning |
|--------|---------|
| `[ ]`  | Not started |
| `[~]`  | In progress |
| `[x]`  | Complete |
| `[!]`  | Blocked / needs decision |

---

## Current Implementation State

```text
ledfx/nowplaying/__init__.py  ← module init, exports NowPlayingService
ledfx/nowplaying/models.py   ← TrackMetadata, ArtworkReference, NowPlayingState
ledfx/nowplaying/service.py  ← NowPlayingService with set/get/clear API + event firing
                                Uses save_asset for artwork storage
                                Uses extract_gradient_metadata() for gradient extraction
                                apply_gradient_to_virtuals() for gradient application (Phase 6)
                                NOW_PLAYING_CONFIG_SCHEMA + update_config() + _save_config() (Phase 7)
                                Config loaded from ledfx.config["now_playing"] on init
ledfx/nowplaying/providers/__init__.py ← providers package
ledfx/nowplaying/providers/sendspin.py ← SendspinNowPlayingProvider (Phase 4)
ledfx/api/now_playing.py     ← GET + PUT /api/now-playing endpoint
ledfx/core.py               ← registers service as self.now_playing
ledfx/events.py             ← 5 NowPlaying event types + subclasses (Phase 3)
ledfx/sendspin/stream.py    ← wired with metadata listener + METADATA role (Phase 4)
ledfx/effects/audio.py      ← passes ledfx to SendspinAudioStream (Phase 4)
ledfx/assets.py             ← save_asset/list_assets/delete_asset (artwork storage + gradients)
ledfx/libraries/cache.py   ← ImageCache with auto gradient extraction on put()
ledfx/utilities/gradient_extraction.py ← extract_gradient_metadata() → led_safe/punchy/max
ledfx/utilities/security_utils.py ← URL validation, image validation, download helpers
ledfx/color.py              ← resolve_gradient(), get_color_at_position(), COLOR_GROUPS (Phase 6)
ledfx/config.py             ← save_config() for persisting effect config changes (Phase 6)
tests/test_now_playing_service.py  ← 76+ tests (models, service, events, artwork, gradient application, config schema, config loading, config updates)
tests/test_api_now_playing.py      ← 11 API integration tests (GET state, PUT config, validation errors)
tests/test_now_playing_sendspin.py ← 11 provider tests
```

---

## Phase 1 — Now Playing Service Skeleton

**Goal**: Establish the service module, dataclasses, and internal state management.

**Status**: `[x]` Complete

### Tasks

- [x] 1.1 Create `ledfx/nowplaying/__init__.py` with module docstring and exports
- [x] 1.2 Create `ledfx/nowplaying/models.py` with dataclasses:
  - `TrackMetadata`
  - `ArtworkReference`
  - `NowPlayingState`
- [x] 1.3 Create `ledfx/nowplaying/service.py` with `NowPlayingService` class:
  - `__init__(self, ledfx)` — store core ref, initialize empty state
  - `set_metadata(source_id, metadata)` — normalize and detect changes
  - `set_artwork_url(source_id, url, content_type, artwork_hash)` — store ref
  - `set_artwork_bytes(source_id, data, content_type, artwork_hash)` — store ref
  - `clear(source_id)` — clear provider state
  - `get_current()` → `NowPlayingState`
- [x] 1.4 Register service on `LedFxCore` (add to `core.py` startup)
- [x] 1.5 Write unit tests `tests/test_now_playing_service.py` (24 service tests, all passing):
  - metadata set/get round-trip
  - track change detection (same metadata → no change, new title → change)
  - clear resets state
  - source_id filtering (only active source updates state)

### Key Decisions for This Phase

- Service is a plain class, not a `BaseRegistry` subclass (no discovery needed)
- No config schema yet — purely in-memory state
- Events fired via Phase 3 (metadata, track, artwork, cleared)
- No async required yet — setters are synchronous

### File Inventory After Phase 1

```text
ledfx/nowplaying/__init__.py
ledfx/nowplaying/models.py
ledfx/nowplaying/service.py
tests/test_now_playing_service.py
```

---

## Phase 2 — REST Debug Endpoint

**Goal**: Expose current Now Playing state via API for debugging and frontend integration.

**Status**: `[x]` Complete

### Tasks

- [x] 2.1 Create `ledfx/api/now_playing.py` with `GET /api/now-playing`
  - Returns serialized `NowPlayingState`
  - Uses `bare_request_success()` helper
- [x] 2.2 Write integration test `tests/test_api_now_playing.py` (4 tests passing)
  - GET with no state returns empty/null fields
  - GET after set_metadata returns expected data
  - GET with artwork URL
  - GET after clear
- [x] 2.3 Verified endpoint auto-registers via RegistryLoader (`RestEndpoint._registry['now_playing']`)

### Dependencies

- Phase 1 complete

---

## Phase 3 — Now Playing Events

**Goal**: Fire LedFx events on state changes so other systems can react.

**Status**: `[x]` Complete

### Tasks

- [x] 3.1 Add event type constants to `ledfx/events.py`:
  - `NOW_PLAYING_TRACK_CHANGED`
  - `NOW_PLAYING_METADATA_CHANGED`
  - `NOW_PLAYING_ARTWORK_CHANGED`
  - `NOW_PLAYING_GRADIENT_CHANGED`
  - `NOW_PLAYING_CLEARED`
- [x] 3.2 Create Now Playing event subclasses in `events.py`:
  - `NowPlayingTrackChangedEvent`
  - `NowPlayingMetadataChangedEvent`
  - `NowPlayingArtworkChangedEvent`
  - `NowPlayingGradientChangedEvent`
  - `NowPlayingClearedEvent`
- [x] 3.3 Update `NowPlayingService.set_metadata()` to fire events:
  - `NOW_PLAYING_METADATA_CHANGED` on any metadata update
  - `NOW_PLAYING_TRACK_CHANGED` when title/artist/album changes
- [x] 3.4 Update `NowPlayingService.set_artwork_url()` and `set_artwork_bytes()` to fire `NOW_PLAYING_ARTWORK_CHANGED`
- [x] 3.5 Update `NowPlayingService.clear()` to fire `NOW_PLAYING_CLEARED`
- [x] 3.6 Write event tests in `tests/test_now_playing_service.py` (11 event tests, all passing)

### Dependencies

- Phase 1 complete

---

## Phase 4 — Sendspin Metadata Provider

**Goal**: Wire Sendspin's existing stream metadata into the Now Playing Service.

**Status**: `[x]` Complete

### Tasks

- [x] 4.1 Identify where Sendspin currently receives track metadata
  - aiosendspin v4.4.0 exposes `add_metadata_listener(callback)` on `SendspinClient`
  - Callback receives `ServerStatePayload` with `.metadata: SessionUpdateMetadata`
  - Fields: title, artist, album, album_artist, artwork_url, year, track, progress
  - Progress contains track_progress (ms), track_duration (ms), playback_speed (×1000)
  - Requires `Roles.METADATA` in client roles
- [x] 4.2 Create `ledfx/nowplaying/providers/__init__.py`
- [x] 4.3 Create `ledfx/nowplaying/providers/sendspin.py`:
  - `SendspinNowPlayingProvider` class
  - Receives `ServerStatePayload` from metadata listener
  - Handles `UndefinedField` sentinel (field not sent vs explicitly null)
  - Normalizes into `TrackMetadata` (ms→seconds conversion for progress)
  - Calls `ledfx.now_playing.set_metadata("sendspin", metadata)`
  - Calls `ledfx.now_playing.set_artwork_url("sendspin", url)` on artwork changes
  - Tracks last artwork URL to avoid redundant updates
- [x] 4.4 Hook provider into `SendspinAudioStream`:
  - Added `ledfx` parameter to constructor
  - Added `Roles.METADATA` to client roles
  - Registered `add_metadata_listener()` in `_connect_and_receive()`
  - Provider cleared on `close()`
  - Passed `ledfx` from `AudioInputSource` in `effects/audio.py`
- [x] 4.5 Write tests `tests/test_now_playing_sendspin.py` (11 tests, all passing):
  - Metadata forwarding (title, artist, album)
  - UndefinedField handling
  - Progress ms→seconds conversion
  - Zero duration → None
  - None metadata ignored
  - Artwork URL forwarding and deduplication
  - Clear resets state
  - Graceful handling when ledfx.now_playing missing

### Key Answers

- aiosendspin exposes `add_metadata_listener(callback: MetadataCallback)` → `ServerStatePayload`
- Metadata delivered via same WebSocket as audio (server/state messages)
- Artwork is URL-only (no binary), provided as `artwork_url` field

### Dependencies

- Phase 1 complete
- Understanding of aiosendspin metadata API

---

## Phase 5 — Sendspin Artwork Provider + Gradient Extraction

**Goal**: Download/store Sendspin artwork, extract gradients, expose via API.

**Status**: `[x]` Complete

### Tasks

- [x] 5.1 Determine how Sendspin provides artwork (URL vs bytes)
  - Sendspin provides artwork as a URL (`artwork_url` field in metadata)
- [x] 5.2 Implement `set_artwork_url()` path:
  - Download image via `urllib.request` with security validation (`validate_url_safety`, `build_browser_request`, size limits)
  - Store via `save_asset()` at `assets/now_playing/now_playing.{ext}` (overwriting previous)
  - Asset system handles: path validation, content validation (PIL), size limits, atomic write
  - Retrieve gradients via `list_assets()` metadata cache
  - Update `ArtworkReference` with path, dimensions, and gradients
- [x] 5.3 Implement `set_artwork_bytes()` path:
  - Compute SHA-256 hash for change detection
  - Store via `save_asset()` at same location
  - Retrieve gradients identically to URL path
  - Update `ArtworkReference`
- [x] 5.4 Fire `NOW_PLAYING_ARTWORK_CHANGED` event (with artwork dict payload)
- [x] 5.5 Fire `NOW_PLAYING_GRADIENT_CHANGED` event when gradient resolves to a new value
- [x] 5.6 Artwork fields already exposed via `GET /api/now-playing` (ArtworkReference.to_dict())
- [x] 5.7 Tests written:
  - Artwork URL: mocked `_download_image`, verifies ArtworkReference populated with gradients
  - Artwork bytes: real PNG/JPEG via Pillow, verifies file write and gradient extraction
  - File write/overwrite tests: confirms single-file replacement behavior
  - Duplicate detection: same URL/hash returns False
  - Download failure: returns False gracefully
  - Event firing: artwork changed + gradient changed events verified
  - API test: GET /api/now-playing with artwork URL (mocked download)

### Implementation Notes

The service uses `save_asset()` from the asset management system for secure, validated, atomic writes. Gradients are retrieved via `list_assets()` which maintains a metadata cache (`.asset_metadata_cache.json`) with modification-time-based invalidation. Old artwork files are cleaned up via `delete_asset()` when the extension changes.

The `_update_current_gradient()` helper selects the configured variant (default: `led_punchy`) from extracted gradients, stores it in `state.current_gradient`, and fires `NowPlayingGradientChangedEvent` when the value changes.

### Dependencies

- Phase 1, Phase 3, Phase 4 complete
- `ledfx/assets.py` provides `save_asset()`, `list_assets()`, `delete_asset()`, `get_asset_path()`
- `ledfx/utilities/security_utils.py` provides URL/image validation and download helpers

---

## Phase 6 — Gradient Application via Globals API

**Goal**: On artwork/gradient change, apply the extracted gradient to target virtuals using the same logic as the `apply_global` action.

**Status**: `[x]` Complete

### Tasks

- [x] 6.1 Implement `apply_gradient_to_virtuals()` as a public method on `NowPlayingService`:
  - Mirrors the `apply_global` logic from `EffectsEndpoint` directly in the service
  - Gradient resolution via `resolve_gradient()` from `ledfx/color.py`
  - Color group sampling via `get_color_at_position()` with `COLOR_GROUPS`
  - Per-effect schema key filtering (only updates keys the effect supports)
  - Normalizes Voluptuous `Optional`/`Required` schema key wrappers
  - HIDDEN_KEYS exclusion
  - `update_config()` + `update_effect_config()` per virtual
  - Config persistence via `save_config()`
  - Returns count of updated effects
- [x] 6.2 Add `gradient_enabled` property (default: True) — controls whether gradient is applied to virtuals
- [x] 6.3 Add `gradient_virtual_ids` property (default: []) — target virtual list; empty = all virtuals
  - Returns a defensive copy to prevent external mutation
- [x] 6.4 Wire `apply_gradient_to_virtuals()` into `_update_current_gradient()`:
  - Called when `current_gradient` changes and `gradient_enabled` is True
  - Triggered by artwork changes (both URL and bytes paths)
- [x] 6.5 Write 20 Phase 6 tests in `tests/test_now_playing_service.py` (58 total, all passing):
  - **Config tests** (5): gradient_enabled default/set, gradient_virtual_ids default/set/copy
  - **apply_gradient_to_virtuals tests** (12): no gradient → 0, no virtuals → 0, single effect, multiple virtuals, skips DummyEffect, skips None effect, filters by virtual_ids, empty ids = all, HIDDEN_KEYS skipped, color-only effects, config save on updates, no save when nothing updated
  - **Auto-application tests** (3): gradient applied on artwork bytes, not applied when disabled, gradient event still fires when disabled

### Implementation Notes

Rather than extracting `apply_global` into a shared utility (as originally proposed in 6.1/6.2), the gradient application logic was implemented directly on `NowPlayingService.apply_gradient_to_virtuals()`. This avoids modifying the existing `EffectsEndpoint._apply_global()` code path and keeps the two callers independent. Both use the same underlying primitives (`resolve_gradient`, `get_color_at_position`, `COLOR_GROUPS`, `save_config`) so behavior is consistent.

The `_DummyLedFxWithVirtuals` test stub provides a `virtuals` dict and `gradients` collection to exercise the full application path with mock effects and mock virtuals.

### Dependencies

- Phase 5 complete
- `ledfx/color.py`: `resolve_gradient()`, `get_color_at_position()`, `COLOR_GROUPS`
- `ledfx/config.py`: `save_config()`
- `ledfx/effects/__init__.py`: `DummyEffect` (for skip detection)

---

## Phase 7 — Now Playing Configuration + Persistence

**Goal**: Add configurable settings for the Now Playing Service to LedFx config.

**Status**: `[x]` Complete

### Tasks

- [x] 7.1 Define config schema (`NOW_PLAYING_CONFIG_SCHEMA` in `service.py`):
  - `gradient.enabled: bool` (default: True)
  - `gradient.variant: str` (led_safe | led_punchy | led_max, default: led_punchy)
  - `gradient.virtual_ids: list[str]` (empty = all virtuals)
  - `track_text.mode: str` (off | temporary | continuous, default: off)
  - `track_text.duration: int` (1–60, default: 8)
  - `track_text.virtual_ids: list[str]`
  - `track_text.fallback_effect: str` (default: "text")
  - `album_art.mode: str` (off | temporary | continuous, default: off)
  - `album_art.duration: int` (1–60, default: 10)
  - `album_art.virtual_ids: list[str]`
  - `album_art.fallback_effect: str` (default: "image")
- [x] 7.2 Load/save config via LedFx config system:
  - Config loaded from `ledfx.config["now_playing"]` on service init
  - Validated through Voluptuous schema with defaults for missing keys
  - `_save_config()` persists to `config.json` via `save_config()`
  - Gradient settings (`enabled`, `virtual_ids`, `variant`) applied to service properties on load
- [x] 7.3 Add `PUT /api/now-playing` endpoint (on same `NowPlayingEndpoint` class):
  - Accepts partial or full config dict (gradient, track_text, album_art sections)
  - Merges with current config, validates via schema
  - Applies settings and persists to disk
  - Returns validated complete config
  - Re-resolves gradient when variant changes
- [x] 7.4 Write config validation and API tests:
  - 6 schema validation tests (`TestNowPlayingConfigSchema`)
  - 3 config loading tests (`TestServiceConfigFromInit`)
  - 9 `update_config()` method tests (`TestUpdateConfig`)
  - 7 PUT API tests in `test_api_now_playing.py` (gradient config, track_text config, album_art config, invalid variant, invalid JSON, non-dict body, reflects in GET)
  - GET endpoint updated to include `config` in response

### Implementation Notes

The `PUT /api/now-playing` endpoint reuses the same `NowPlayingEndpoint` class as the GET endpoint (one class per file rule). Configuration is merged section-by-section: providing `{"gradient": {"enabled": false}}` only updates the gradient section, preserving track_text and album_art. The `update_config()` method on `NowPlayingService` handles validation, application, and persistence in a single call.

When the gradient variant changes, `_update_current_gradient()` is called to re-resolve from cached artwork gradients without re-extracting. This allows instant variant switching.

The `enabled`/`sources` top-level fields from the original design were deferred — the current schema focuses on the three actionable sections (gradient, track_text, album_art) that are needed by Phases 8–10.

### Dependencies

- Phase 2 complete

---

## Phase 8 — Track Text Temporary Display

**Goal**: On track change, temporarily show "Artist - Title" on target matrix virtuals.

**Status**: `[ ]` Not started

### Tasks

- [ ] 8.1 Implement effect save/restore mechanism for virtuals
- [ ] 8.2 On `NOW_PLAYING_TRACK_CHANGED`:
  - Save current effect on configured virtual_ids
  - Apply text fallback effect with formatted track info
  - Schedule restoration after `duration` seconds
- [ ] 8.3 Handle edge cases:
  - Track changes during display (reset timer)
  - Virtual stopped/disabled during display
  - User manually changes effect during display (cancel restore)
- [ ] 8.4 Filter virtual picker to matrix-capable only (rows > 1)
- [ ] 8.5 Write tests

### Dependencies

- Phase 3, Phase 7 complete
- Text effect must support programmatic text setting

---

## Phase 9 — Album Artwork Temporary Display

**Goal**: On artwork change, temporarily show album art on target matrix virtuals.

**Status**: `[ ]` Not started

### Tasks

- [ ] 9.1 On `NOW_PLAYING_ARTWORK_CHANGED`:
  - Save current effect on configured virtual_ids
  - Apply image fallback effect with current artwork
  - Schedule restoration after `duration` seconds
- [ ] 9.2 Handle same edge cases as Phase 8
- [ ] 9.3 Write tests

### Dependencies

- Phase 5, Phase 8 complete (reuses save/restore mechanism)

---

## Phase 10 — Continuous Display Modes

**Goal**: Dedicated virtuals that permanently show track text or album art.

**Status**: `[ ]` Not started

### Tasks

- [ ] 10.1 Continuous text mode: lock virtual to text effect, update on metadata change
- [ ] 10.2 Continuous art mode: lock virtual to image effect, update on artwork change
- [ ] 10.3 Handle virtual unlock (user disables continuous mode)
- [ ] 10.4 Write tests

### Dependencies

- Phase 8, Phase 9 complete

---

## Phase 11 — yzflow Integration

**Goal**: Allow yzflow to orchestrate Now Playing events and routing.

**Status**: `[ ]` Not started

### Tasks

- [ ] 11.1 Expose Now Playing events as yzflow triggers
- [ ] 11.2 Expose gradient routing as yzflow actions
- [ ] 11.3 Expose display triggers as yzflow actions
- [ ] 11.4 Document yzflow integration patterns

### Dependencies

- Phases 1–10 complete
- yzflow system available

---

## Phase 12 — Additional Providers

**Goal**: Add providers beyond Sendspin incrementally.

**Status**: `[ ]` Not started

### Candidate Provider Order

1. Music Assistant (if metadata API available independently)
2. Linux MPRIS (D-Bus)
3. Windows Media Session (winrt)
4. Spotify (Web API)
5. YouTube Music
6. Generic WebSocket/REST provider

### Per-Provider Tasks Template

- [ ] Implement provider class in `ledfx/nowplaying/providers/<name>.py`
- [ ] Normalize metadata to `TrackMetadata`
- [ ] Handle artwork (URL or bytes)
- [ ] Register with Now Playing Service
- [ ] Write tests
- [ ] Document configuration

### Dependencies

- Phases 1–5 complete (provider interface stable)

---

## Implementation Notes & Conventions

### File Locations

| Component | Path |
|-----------|------|
| Service | `ledfx/nowplaying/service.py` |
| Models | `ledfx/nowplaying/models.py` |
| Module init | `ledfx/nowplaying/__init__.py` |
| Providers | `ledfx/nowplaying/providers/<name>.py` |
| REST API | `ledfx/api/now_playing.py` |
| Tests | `tests/test_now_playing_*.py` |

### Key Existing Files to Integrate With

| File | Integration Point |
|------|-------------------|
| `ledfx/core.py` | Service registration on startup |
| `ledfx/events.py` | Event constants + NowPlayingEvent class |
| `ledfx/libraries/cache.py` | `ImageCache.put()` for artwork → gradient |
| `ledfx/utilities/gradient_extraction.py` | `extract_gradient_metadata()` (called by cache) |
| `ledfx/color.py` | Gradient resolution via `resolve_gradient()`, color sampling via `get_color_at_position()`, `COLOR_GROUPS` (used by apply_global and Phase 6), `build_gradient_config()` |
| `ledfx/virtuals.py` | `apply_config_to_active_effects()` for per-virtual gradient application (Phase 6) |
| `ledfx/config.py` | `save_config()` for persisting effect and now_playing config changes |
| `ledfx/sendspin/stream.py` | Metadata source hookup |

### Design Constraints

- All Python commands via `uv run`
- Use `os.path` not `pathlib`
- One `RestEndpoint` class per API file
- Use `RestEndpoint` helper methods, not `web.json_response()`
- Imports at top of file
- `_LOGGER.warning()` for client errors, `.error()` for system errors

---

## Decision Log

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Source priority with multiple providers | Single active provider (first: Sendspin) | Keep initial implementation simple |
| 2 | Artwork storage | Cache only (not assets) | Transient data, avoid filling user assets |
| 3 | Synthetic cache URL format | Not used — single `now_playing.{ext}` file approach instead | Simpler than cache-keyed storage; artwork is transient, only one file needed |
| 4 | Gradient application strategy | Via globals API code path, not alias | Reuses existing apply_global logic; no gradient picker or effect schema changes needed |
| 5 | Fallback effect restore contract | TBD — Phase 8 | Need to handle edge cases (manual override, etc.) |
| 6 | BaseRegistry vs plain class | Plain class for service | No auto-discovery needed for singleton service |

---

## Progress Tracker

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Service Skeleton | `[x]` Complete |
| 2 | REST Debug Endpoint | `[x]` Complete |
| 3 | Now Playing Events | `[x]` Complete |
| 4 | Sendspin Metadata Provider | `[x]` Complete |
| 5 | Sendspin Artwork + Gradient Extraction | `[x]` Complete |
| 6 | Gradient Application via Globals API | `[x]` Complete |
| 7 | Now Playing Configuration | `[x]` Complete |
| 8 | Track Text Temporary Display | `[ ]` Not started |
| 9 | Album Artwork Temporary Display | `[ ]` Not started |
| 10 | Continuous Display Modes | `[ ]` Not started |
| 11 | yzflow Integration | `[ ]` Not started |
| 12 | Additional Providers | `[ ]` Not started |
