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

The Now Playing Service should reuse this model.

---

## Design Rule

Do not implement a new one-off album-art-to-gradient path.

Instead:

```text
Provider artwork
    ↓
Now Playing Service
    ↓
Image cache / asset-compatible storage path
    ↓
Existing gradient extraction
    ↓
Current track gradient alias
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
Image cache fetch/store
    ↓
ImageCache.put()
    ↓
extract_gradient_metadata()
    ↓
cache metadata includes gradients
    ↓
Now Playing reads selected variant
```

This aligns directly with LedFx's current image cache architecture.

---

### Case 2: Artwork Provider Supplies Raw Bytes

Preferred flow:

```text
artwork bytes
    ↓
synthetic now-playing cache URL
    ↓
ImageCache.put()
    ↓
extract_gradient_metadata()
    ↓
cache metadata includes gradients
    ↓
Now Playing reads selected variant
```

Suggested synthetic URL format:

```text
now-playing://<source_id>/<artwork_hash>
```

or:

```text
album-art://<source_id>/<track_id-or-hash>
```

The important point is that the cache key must be stable for the same artwork and different for changed artwork.

---

## Current Track Gradient Alias

The dynamic gradient should be exposed as a system gradient alias:

```text
system/current_track
```

This should not be a separate static gradient persisted like a user-created gradient.

It is a runtime alias that resolves to the current selected gradient variant from the current artwork metadata.

---

## Gradient Variant Selection

Now Playing configuration should include:

```json
{
  "gradient": {
    "enabled": true,
    "variant": "led_punchy",
    "name": "system/current_track"
  }
}
```

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
update system/current_track alias
    ↓
emit now_playing_gradient_changed
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
    "name": "system/current_track",
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

Effects that already support gradients should be able to select:

```text
system/current_track
```

This lets existing effects become album-art themed without knowing anything about album art.

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
├─ Current Track Gradient
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
      "name": "system/current_track",
      "variant": "led_punchy"
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
route system/current_track gradient to selected effects
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

## Phase 3 - Sendspin Metadata Provider

Implement:

- Sendspin metadata ingestion
- metadata normalization
- calls to `set_metadata("sendspin", metadata)`

Deliverables:

- title/artist/album visible through `/api/now-playing`
- track changes detected
- no artwork or gradients required yet

---

## Phase 4 - Sendspin Artwork Provider Using Existing Image Cache

Implement:

- Sendspin artwork URL handling if available
- Sendspin artwork byte handling if needed
- stable synthetic cache key for byte-based artwork
- image cache integration
- no custom gradient extraction path

Deliverables:

- artwork cached
- width/height/content type available
- existing gradient metadata produced by `ImageCache.put()`

---

## Phase 5 - Current Track Gradient Alias

Implement:

```text
system/current_track
```

as a runtime alias to the selected gradient variant in current artwork metadata.

Deliverables:

- selected variant resolved from cached gradient metadata
- alias updates on artwork change
- `now_playing_gradient_changed` emitted
- no per-frame extraction

---

## Phase 6 - Effect Gradient Picker Support

Implement:

- expose `system/current_track` in gradient picker
- allow existing gradient-aware effects to select it

Deliverables:

- existing effects can use album-art-derived gradients
- no provider-specific effect changes

---

## Phase 7 - Now Playing Events

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

## Phase 8 - Now Playing Configuration UI

Implement service configuration dialog:

```text
Now Playing
├─ Sources
├─ Gradient
├─ Track Text Display Targets
└─ Album Artwork Display Targets
```

Deliverables:

- gradient enable/disable
- gradient variant picker
- track text mode/duration/virtual picker
- album art mode/duration/virtual picker
- virtual picker filters to matrix virtuals only

---

## Phase 9 - Track Text Temporary Display

Implement:

- temporary fallback text display
- save/restore previous virtual effect
- duration-based restoration

Deliverables:

- target matrix virtuals show track text on track change
- previous effect restored after timeout

---

## Phase 10 - Album Artwork Temporary Display

Implement:

- temporary fallback artwork/image display
- save/restore previous virtual effect
- duration-based restoration

Deliverables:

- target matrix virtuals show album art on artwork change
- previous effect restored after timeout

---

## Phase 11 - Continuous Display Modes

Implement:

- continuous track text virtuals
- continuous album art virtuals

Deliverables:

- selected virtuals stay dedicated to Now Playing display
- updates happen on metadata/artwork changes

---

## Phase 12 - yzflow Integration

Implement:

- event routing
- gradient routing
- optional display triggers

Deliverables:

- yzflow can orchestrate Now Playing behavior
- Now Playing remains source-of-truth
- effects remain provider-agnostic

---

## Phase 13 - Additional Providers

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

Initial answer:

```text
cache only
```

Rationale:

- now playing artwork is transient
- existing image cache already supports metadata and gradients
- avoids filling user assets with temporary album art

---

## Synthetic Cache URL Format

Candidate formats:

```text
now-playing://sendspin/<artwork_hash>
album-art://sendspin/<track_id>
```

Need to verify best fit with existing cache assumptions.

---

## Current Track Gradient Persistence

Should `system/current_track` be serialized?

Initial answer:

```text
No.
```

It should be a runtime alias. Effects may reference it by name, but the actual gradient value is resolved dynamically.

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
- `system/current_track` is a runtime alias to an existing extracted gradient variant
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
ledfx/nowplaying/providers/__init__.py ← providers package
ledfx/nowplaying/providers/sendspin.py ← SendspinNowPlayingProvider (Phase 4)
ledfx/api/now_playing.py     ← GET /api/now-playing endpoint
ledfx/core.py               ← registers service as self.now_playing
ledfx/events.py             ← 5 NowPlaying event types + subclasses (Phase 3)
ledfx/sendspin/stream.py    ← wired with metadata listener + METADATA role (Phase 4)
ledfx/effects/audio.py      ← passes ledfx to SendspinAudioStream (Phase 4)
ledfx/libraries/cache.py   ← ImageCache with auto gradient extraction on put()
ledfx/utilities/gradient_extraction.py ← extract_gradient_metadata() → led_safe/punchy/max
ledfx/utilities/security_utils.py ← URL validation, image validation, download helpers
tests/test_now_playing_service.py  ← 38 tests (models, service, events, artwork URL/bytes, file write/overwrite, gradients)
tests/test_api_now_playing.py      ← 4 API integration tests (including artwork URL with mocked download)
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
  - Save as single `now_playing.{ext}` file in `config_dir/cache/images/` (overwriting previous)
  - Validate with PIL (`validate_pil_image`)
  - Extract gradients via `extract_gradient_metadata()` directly
  - Update `ArtworkReference` with path, dimensions, and gradients
- [x] 5.3 Implement `set_artwork_bytes()` path:
  - Compute SHA-256 hash for change detection
  - Save as `now_playing.{ext}` in same location
  - Validate and extract gradients identically to URL path
  - Update `ArtworkReference`
- [x] 5.4 Fire `NOW_PLAYING_ARTWORK_CHANGED` event (with artwork dict payload)
- [x] 5.5 Artwork fields already exposed via `GET /api/now-playing` (ArtworkReference.to_dict())
- [x] 5.6 Tests written:
  - Artwork URL: mocked `_download_image`, verifies ArtworkReference populated with gradients
  - Artwork bytes: real PNG/JPEG via Pillow, verifies file write and gradient extraction
  - File write/overwrite tests: confirms single-file replacement behavior
  - Duplicate detection: same URL/hash returns False
  - Download failure: returns False gracefully
  - Event firing: artwork changed events verified
  - API test: GET /api/now-playing with artwork URL (mocked download)

### Implementation Notes

Instead of routing through `ImageCache.put()`, the service stores artwork directly as a single file and calls `extract_gradient_metadata()` itself. This avoids coupling to the cache's URL-keyed storage model and keeps the now-playing artwork as a simple overwritten file (transient, not accumulating).

The `_update_current_gradient()` helper selects the configured variant (default: `led_punchy`) from extracted gradients and stores it in `state.current_gradient`.

### Dependencies

- Phase 1, Phase 3, Phase 4 complete
- `ledfx/utilities/gradient_extraction.py` provides `extract_gradient_metadata()`
- `ledfx/utilities/security_utils.py` provides URL/image validation

---

## Phase 6 — Current Track Gradient Alias

**Goal**: Expose `system/current_track` as a runtime gradient alias usable by effects.

**Status**: `[ ]` Not started

### Tasks

- [ ] 6.1 Research how effects currently resolve gradient names
  - Check `ledfx/color.py` and effect gradient handling
- [ ] 6.2 Implement gradient alias registry or hook:
  - `system/current_track` resolves to the selected variant gradient string
  - Returns empty/fallback if no artwork loaded
- [ ] 6.3 Update `NowPlayingService` to maintain `current_gradient`:
  - On artwork change: read `selected_gradient_variant` from state
  - Look up that variant in artwork gradients dict
  - Update the alias value
  - Fire `NOW_PLAYING_GRADIENT_CHANGED`
- [ ] 6.4 Add gradient variant config to Now Playing config schema
- [ ] 6.5 Write tests for alias resolution

### Dependencies

- Phase 5 complete

---

## Phase 7 — Effect Gradient Picker Support

**Goal**: Make `system/current_track` selectable in the frontend gradient picker.

**Status**: `[ ]` Not started

### Tasks

- [ ] 7.1 Expose system gradients in gradient list API
- [ ] 7.2 Frontend: show `system/current_track` in gradient picker dropdown
- [ ] 7.3 Verify existing effects render correctly with the alias

### Dependencies

- Phase 6 complete
- Frontend changes required

---

## Phase 8 — Now Playing Configuration + Persistence

**Goal**: Add configurable settings for the Now Playing Service to LedFx config.

**Status**: `[ ]` Not started

### Tasks

- [ ] 8.1 Define config schema (Voluptuous):
  - `enabled: bool`
  - `sources: dict`
  - `gradient.enabled: bool`
  - `gradient.variant: str` (led_safe | led_punchy | led_max)
  - `track_text.mode: str` (off | temporary | continuous)
  - `track_text.duration: int`
  - `track_text.virtual_ids: list`
  - `album_art.mode: str`
  - `album_art.duration: int`
  - `album_art.virtual_ids: list`
- [ ] 8.2 Load/save config via LedFx config system
- [ ] 8.3 Add `PUT /api/now-playing/config` endpoint
- [ ] 8.4 Write config validation tests

### Dependencies

- Phase 2 complete

---

## Phase 9 — Track Text Temporary Display

**Goal**: On track change, temporarily show "Artist - Title" on target matrix virtuals.

**Status**: `[ ]` Not started

### Tasks

- [ ] 9.1 Implement effect save/restore mechanism for virtuals
- [ ] 9.2 On `NOW_PLAYING_TRACK_CHANGED`:
  - Save current effect on configured virtual_ids
  - Apply text fallback effect with formatted track info
  - Schedule restoration after `duration` seconds
- [ ] 9.3 Handle edge cases:
  - Track changes during display (reset timer)
  - Virtual stopped/disabled during display
  - User manually changes effect during display (cancel restore)
- [ ] 9.4 Filter virtual picker to matrix-capable only (rows > 1)
- [ ] 9.5 Write tests

### Dependencies

- Phase 3, Phase 8 complete
- Text effect must support programmatic text setting

---

## Phase 10 — Album Artwork Temporary Display

**Goal**: On artwork change, temporarily show album art on target matrix virtuals.

**Status**: `[ ]` Not started

### Tasks

- [ ] 10.1 On `NOW_PLAYING_ARTWORK_CHANGED`:
  - Save current effect on configured virtual_ids
  - Apply image fallback effect with current artwork
  - Schedule restoration after `duration` seconds
- [ ] 10.2 Handle same edge cases as Phase 9
- [ ] 10.3 Write tests

### Dependencies

- Phase 5, Phase 9 complete (reuses save/restore mechanism)

---

## Phase 11 — Continuous Display Modes

**Goal**: Dedicated virtuals that permanently show track text or album art.

**Status**: `[ ]` Not started

### Tasks

- [ ] 11.1 Continuous text mode: lock virtual to text effect, update on metadata change
- [ ] 11.2 Continuous art mode: lock virtual to image effect, update on artwork change
- [ ] 11.3 Handle virtual unlock (user disables continuous mode)
- [ ] 11.4 Write tests

### Dependencies

- Phase 9, Phase 10 complete

---

## Phase 12 — yzflow Integration

**Goal**: Allow yzflow to orchestrate Now Playing events and routing.

**Status**: `[ ]` Not started

### Tasks

- [ ] 12.1 Expose Now Playing events as yzflow triggers
- [ ] 12.2 Expose gradient routing as yzflow actions
- [ ] 12.3 Expose display triggers as yzflow actions
- [ ] 12.4 Document yzflow integration patterns

### Dependencies

- Phases 1–11 complete
- yzflow system available

---

## Phase 13 — Additional Providers

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
| `ledfx/color.py` | Gradient resolution for `system/current_track` |
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
| 4 | `system/current_track` persistence | No — runtime alias only | Effects reference by name, value resolved dynamically |
| 5 | Fallback effect restore contract | TBD — Phase 9 | Need to handle edge cases (manual override, etc.) |
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
| 6 | Current Track Gradient Alias | `[ ]` Not started |
| 7 | Effect Gradient Picker Support | `[ ]` Not started |
| 8 | Now Playing Configuration | `[ ]` Not started |
| 9 | Track Text Temporary Display | `[ ]` Not started |
| 10 | Album Artwork Temporary Display | `[ ]` Not started |
| 11 | Continuous Display Modes | `[ ]` Not started |
| 12 | yzflow Integration | `[ ]` Not started |
| 13 | Additional Providers | `[ ]` Not started |
