# LedFx Now Playing Service — Implementation Reference

## Purpose

A centralised **Now Playing Service** that receives real-time media metadata from external providers and uses it to drive LedFx visuals automatically.

Provides a single internal source of truth for:

- current track metadata
- current album artwork
- artwork-derived gradients
- temporary or permanent track-text display
- temporary or permanent album-art display
- provider-neutral events

Two providers are currently implemented: **Sendspin** (explicit integration) and **SMTC** (Windows System Media Transport Controls). The architecture is provider-agnostic.

---

## Module Layout

```
ledfx/nowplaying/
    __init__.py                  # exposes NowPlayingService
    models.py                    # TrackMetadata, ArtworkReference, NowPlayingState
    normalise.py                 # YouTube/channel-name metadata normalisation
    service.py                   # NowPlayingService
    album_art/
        __init__.py
        base.py                  # AlbumArtProvider ABC
        resolver.py              # AlbumArtResolver (async, non-blocking)
        musicbrainz.py           # MusicBrainzArtProvider (MusicBrainz + Cover Art Archive)
    providers/
        __init__.py
        sendspin.py              # SendspinNowPlayingProvider
        smtc.py                  # SMTCNowPlayingProvider (Windows only)
```

Supporting changes elsewhere:

| File | Change |
|---|---|
| `ledfx/api/now_playing.py` | REST endpoint `GET/PUT /api/now-playing` |
| `ledfx/events.py` | 5 new Now Playing event types |
| `ledfx/color.py` | `build_gradient_config()` helper |
| `ledfx/virtuals.py` | `apply_config_to_active_effects()` helper |
| `ledfx/core.py` | instantiates `NowPlayingService` as `ledfx.now_playing`; creates and starts `SMTCNowPlayingProvider` |
| `ledfx/sendspin/stream.py` | creates `SendspinNowPlayingProvider` on connect |

---

## Data Models (`ledfx/nowplaying/models.py`)

### TrackMetadata

```python
@dataclass
class TrackMetadata:
    source_id: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    track_id: Optional[str] = None
    artwork_url: Optional[str] = None
    artwork_hash: Optional[str] = None
    updated_at: Optional[float] = None
```

`duration` and `position` fields are not tracked. `track_identity()` returns `(title, artist, album, track_id)` — used for change detection.

### ArtworkReference

```python
@dataclass
class ArtworkReference:
    source_id: str
    url: Optional[str] = None
    cache_key: Optional[str] = None   # absolute path of saved asset
    content_type: Optional[str] = None
    hash: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    gradients: Optional[dict] = None  # keyed by variant name
```

### NowPlayingState

```python
@dataclass
class NowPlayingState:
    active_source_id: Optional[str] = None
    metadata: Optional[TrackMetadata] = None
    artwork: Optional[ArtworkReference] = None
    selected_gradient_variant: str = "led_punchy"
    current_gradient: Optional[str] = None
    updated_at: Optional[float] = None
```

---

## Service Configuration (`NOW_PLAYING_CONFIG_SCHEMA`)

Persisted under `config["now_playing"]`.

```python
{
    "gradient": {
        "enabled": True,                     # apply gradient to virtuals
        "variant": "led_punchy",             # led_safe | led_punchy | led_max
        "virtual_ids": [],                   # [] = all virtuals
    },
    "track_text": {
        "enabled": True,
        "duration": 60,                      # seconds (0–60); 0 = permanent
        "virtual_ids": [],
        "preset": "",                        # texter2d preset name
    },
    "album_art": {
        "enabled": True,
        "duration": 10,                      # seconds (0–60); 0 = permanent
        "virtual_ids": [],
    },
}
```

All sections are optional in `update_config()` — unspecified sections retain their current values.

---

## Source Priority

Multiple providers may send metadata simultaneously. The service uses a static priority table to determine the active source:

| Source | Priority |
|---|---|
| `sendspin` | 10 |
| `smtc` | 1 |

A new source pre-empts the current active source only if its priority is **strictly greater**. When a higher-priority source takes over, any in-flight album-art resolver work is cancelled.

---

## Public API (`NowPlayingService`)

```python
# Called by providers
service.set_metadata(source_id, metadata)        -> bool  # True if track changed
service.set_artwork_url(source_id, url, ...)     -> bool  # True if artwork changed
service.set_artwork_bytes(source_id, data, ...)  -> bool  # True if artwork changed
service.set_artwork_resolved(data, ...)          -> bool  # Called by AlbumArtResolver only
service.clear_artwork(source_id)                 -> None  # Clear artwork, keep track state
service.clear(source_id)                         -> None  # Clear all state for source

# Called by REST endpoint / core
service.get_current()                            -> NowPlayingState
service.update_config(new_config)                -> dict  # raises vol.Invalid
service.apply_gradient_to_virtuals()             -> int   # count updated

# Properties
service.gradient_enabled                         -> bool
service.gradient_virtual_ids                     -> list[str]
service.config                                   -> dict
```

---

## Album Art Resolver

For sources that do not supply their own artwork (currently only `smtc`), the service delegates to `AlbumArtResolver` on each track change. The resolver:

1. Normalises the track key (artist, title, album) to avoid duplicate lookups.
2. Runs an async `MusicBrainzArtProvider` lookup against the MusicBrainz recording search API and Cover Art Archive (no auth required).
3. Delivers resolved bytes via `service.set_artwork_resolved()`.

Sources listed in `_SOURCES_WITH_OWN_ARTWORK` (currently `{"sendspin"}`) never trigger the resolver. When a source directly calls `set_artwork_url()` or `set_artwork_bytes()`, any in-flight resolver task is cancelled.

---

## Metadata Normalisation (`normalise.py`)

Before displaying track text on LEDs or querying MusicBrainz, metadata is cleaned through shared normalisation helpers that strip YouTube/channel noise:

- Artist: removes `- Topic`, `VEVO`, and channel-suffix words (Official, Music, Records…)
- Title: strips bracketed suffixes (`[Official Video]`, `(Lyrics)`, quality tags `[4K]`, remaster/version tags), unbracketed video suffixes, and artist-prefix segments YouTube prepends
- Album: placeholder passthrough (normalise_album returns None for uninformative values)

---

## Artwork Pipeline

```
Provider calls set_artwork_url() or set_artwork_bytes()
    |
    v  (set_artwork_url only)
Security validation (URL safety, size limit, PIL validation)
    |
    v
save_asset(config_dir, "now_playing/now_playing.{ext}", data, allow_overwrite=True)
    |  stored at: {config_dir}/assets/now_playing/now_playing.{ext}
    v
extract_gradient_metadata(absolute_path)  ->  { led_safe: ..., led_punchy: ..., led_max: ... }
    |
    v
ArtworkReference stored in NowPlayingState
    |
    v
_update_current_gradient()  ->  resolves current_gradient from selected variant
    |
    v
apply_gradient_to_virtuals()  (if gradient.enabled)
_apply_album_art_to_virtuals()  (if album_art.enabled and virtual_ids set)
    |
    v
NowPlayingArtworkChangedEvent fired
```

A single file is kept (`now_playing.{ext}`). Each track overwrites the previous artwork in-place. The same pipeline runs for `set_artwork_resolved()` (resolver-delivered bytes), except there is no source_id gate.

---

## Track Change Pipeline

```
Provider calls set_metadata(source_id, metadata)
    |
    v
Source priority check (pre-empt or ignore if lower priority)
    |
    v
_detect_track_change()  -- compares track_identity() tuple
    |
    v
NowPlayingMetadataChangedEvent fired  (suppressed for position-only ticks)
    |  (if track changed)
    v
NowPlayingTrackChangedEvent fired
_apply_track_text_to_virtuals()  (if track_text.enabled and virtual_ids set; audio must be active)
    |  (if source not in _SOURCES_WITH_OWN_ARTWORK)
    v
AlbumArtResolver.on_track_changed(metadata)  ->  async MusicBrainz lookup
```

---

## Visual Application

### Gradient

`apply_gradient_to_virtuals()` uses `build_gradient_config()` (from `ledfx/color.py`) to resolve the gradient string and sample color groups, then calls `apply_config_to_active_effects()` (from `ledfx/virtuals.py`) to update all matching active effects. Changes are persisted to config.

Target scope: `gradient.virtual_ids` if non-empty, otherwise all virtuals.

### Track Text

Creates a `texter2d` effect using the optional `track_text.preset` as base config, then sets `text` to the normalised `"Artist - Album - Title"` string (see Metadata Normalisation above). Applied via `virtual.set_effect(effect, fallback=duration)`. If `duration == 0` the effect is permanent. Track text is only applied when the audio stream is active.

### Album Art

Creates an `imagespin` effect seeded from the built-in `artwork` preset, with `image_source` set to `artwork.cache_key`. Applied via `virtual.set_effect(effect, fallback=duration)`. If `duration == 0` the effect is permanent.

---

## Providers

### Sendspin (`ledfx/nowplaying/providers/sendspin.py`)

`SendspinNowPlayingProvider` is created by `SendspinAudioStream` and wired to the aiosendspin metadata callback.

Sendspin sends **incremental** updates — `UndefinedField` means "not included in this message" (retain previous value); explicit `None` means "cleared". The provider accumulates state across messages before forwarding a full `TrackMetadata` to the service.

Key behaviour:
- State accumulates across incremental updates
- Artwork URL changes trigger `now_playing.set_artwork_url()`; clearing the URL calls `now_playing.clear_artwork()`
- `clear()` resets all accumulated state and calls `now_playing.clear()`

Sendspin is in `_SOURCES_WITH_OWN_ARTWORK` — the album-art resolver is never invoked for it.

### SMTC (`ledfx/nowplaying/providers/smtc.py`) — Windows only

`SMTCNowPlayingProvider` hooks into the Windows System Media Transport Controls via WinRT to receive passive, system-wide media session changes. It is created and started by `core.py` at startup alongside `NowPlayingService`.

Key behaviour:
- Subscribes to WinRT `CurrentSessionChanged` and `MediaPropertiesChanged` events
- Forwards title, artist, album as `TrackMetadata` to the service
- Does **not** fetch artwork — that is delegated to the album-art resolver (MusicBrainz)
- Silently no-ops on non-Windows platforms

---

## Events (`ledfx/events.py`)

| Event type | Fired when |
|---|---|
| `NOW_PLAYING_TRACK_CHANGED` | Track identity changes |
| `NOW_PLAYING_METADATA_CHANGED` | Content-carrying metadata changes (suppressed for position-only ticks) |
| `NOW_PLAYING_ARTWORK_CHANGED` | Artwork stored and gradients extracted (also fired with empty dict on `clear_artwork`) |
| `NOW_PLAYING_GRADIENT_CHANGED` | `current_gradient` changes value |
| `NOW_PLAYING_CLEARED` | Active source clears |

---

## REST API (`ledfx/api/now_playing.py`)

**`GET /api/now-playing`**

Returns the full `NowPlayingState` dict plus `config`.

```json
{
  "active_source_id": "sendspin",
  "metadata": { "..." },
  "artwork": { "..." },
  "current_gradient": "linear-gradient(...)",
  "selected_gradient_variant": "led_punchy",
  "config": { "gradient": {}, "track_text": {}, "album_art": {} }
}
```

**`PUT /api/now-playing`**

Accepts a partial or full config dict. Merges with current config, validates via `NOW_PLAYING_CONFIG_SCHEMA`, persists to disk.

---

## Security

Artwork downloads (`set_artwork_url`) are guarded by:

- `validate_url_safety()` — blocks private/loopback addresses by default
- Extension allow-list via `is_allowed_image_extension()`
- `MAX_IMAGE_SIZE_BYTES` read cap
- `validate_pil_image()` — rejects non-image payloads

Asset writes use `save_asset(..., allow_overwrite=True)` which enforces path containment within the config assets directory.

---

## Adding New Providers

The service is provider-agnostic. Any new provider needs only to:

1. Call `ledfx.now_playing.set_metadata(source_id, TrackMetadata(...))`
2. Call `ledfx.now_playing.set_artwork_url()` or `set_artwork_bytes()` when artwork changes; or rely on the album-art resolver by omitting from `_SOURCES_WITH_OWN_ARTWORK`
3. Call `ledfx.now_playing.clear(source_id)` on disconnect
4. Add a priority entry in `_SOURCE_PRIORITY` in `service.py`

Candidate future providers: Music Assistant, Spotify, Linux MPRIS, browser integrations.
