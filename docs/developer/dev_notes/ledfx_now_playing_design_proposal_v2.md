# LedFx Now Playing Service

## Purpose

A centralised **Now Playing Service** that receives real-time media metadata from external providers and uses it to drive LedFx visuals automatically.

Provides a single internal source of truth for:

- current track metadata
- current album artwork
- artwork-derived gradients
- temporary or permanent track-text display
- temporary or permanent album-art display
- provider-neutral events

The first provider is **Sendspin**. The architecture is provider-agnostic.

---

## Module Layout

```
ledfx/nowplaying/
    __init__.py                  # exposes NowPlayingService
    models.py                    # TrackMetadata, ArtworkReference, NowPlayingState
    service.py                   # NowPlayingService
    providers/
        __init__.py
        sendspin.py              # SendspinNowPlayingProvider
```

Supporting changes elsewhere:

| File | Change |
|---|---|
| `ledfx/api/now_playing.py` | REST endpoint `GET/PUT /api/now-playing` |
| `ledfx/events.py` | 5 new Now Playing event types |
| `ledfx/color.py` | `build_gradient_config()` helper |
| `ledfx/virtuals.py` | `apply_config_to_active_effects()` helper |
| `ledfx/presets.py` | `get_ledfx_presets()` helper |
| `ledfx/core.py` | instantiates `NowPlayingService` as `ledfx.now_playing` |
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
    duration: Optional[float] = None
    position: Optional[float] = None
    track_id: Optional[str] = None
    artwork_url: Optional[str] = None
    artwork_hash: Optional[str] = None
    updated_at: Optional[float] = None
```

`track_identity()` returns `(title, artist, album, track_id)` — used for change detection.

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
        "duration": 8,                       # seconds; 0 = permanent
        "virtual_ids": [],
        "preset": "",                        # texter2d preset name
    },
    "album_art": {
        "enabled": True,
        "duration": 10,                      # seconds; 0 = permanent
        "virtual_ids": [],
    },
}
```

All sections are optional in `update_config()` — unspecified sections retain their current values.

---

## Public API (`NowPlayingService`)

```python
# Called by providers
service.set_metadata(source_id, metadata)       -> bool  # True if track changed
service.set_artwork_url(source_id, url, ...)    -> bool  # True if artwork changed
service.set_artwork_bytes(source_id, data, ...) -> bool  # True if artwork changed
service.clear(source_id)                        -> None

# Called by REST endpoint / core
service.get_current()                           -> NowPlayingState
service.update_config(new_config)               -> dict  # raises vol.Invalid
service.apply_gradient_to_virtuals()            -> int   # count updated

# Properties
service.gradient_enabled                        -> bool
service.gradient_virtual_ids                    -> list[str]
service.config                                  -> dict
```

---

## Artwork Pipeline

```
Provider calls set_artwork_url() or set_artwork_bytes()
    |
    v
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

A single file is kept (`now_playing.{ext}`). Each track overwrites the previous artwork in-place.

---

## Track Change Pipeline

```
Provider calls set_metadata(source_id, metadata)
    |
    v
_detect_track_change()  -- compares track_identity() tuple
    |  (if changed)
    v
NowPlayingTrackChangedEvent fired
_apply_track_text_to_virtuals()  (if track_text.enabled and virtual_ids set)
    |
    v
NowPlayingMetadataChangedEvent fired (every call)
```

---

## Visual Application

### Gradient

`apply_gradient_to_virtuals()` uses `build_gradient_config()` (from `ledfx/color.py`) to resolve the gradient string and sample color groups, then calls `apply_config_to_active_effects()` (from `ledfx/virtuals.py`) to update all matching active effects. Changes are persisted to config.

Target scope: `gradient.virtual_ids` if non-empty, otherwise all virtuals.

### Track Text

Creates a `texter2d` effect using the optional `track_text.preset` as base config, then sets `text` to `"Artist - Album - Title"`. Applied via `virtual.set_effect(effect, fallback=duration)`. If `duration == 0` the effect is permanent.

### Album Art

Creates an `imagespin` effect seeded from the built-in `artwork` preset, with `image_source` set to `artwork.cache_key`. Applied via `virtual.set_effect(effect, fallback=duration)`. If `duration == 0` the effect is permanent.

---

## Sendspin Provider (`ledfx/nowplaying/providers/sendspin.py`)

`SendspinNowPlayingProvider` is created by `SendspinAudioStream` and wired to the aiosendspin metadata callback.

Sendspin sends **incremental** updates — `UndefinedField` means "not included in this message" (retain previous value); explicit `None` means "cleared". The provider accumulates state across messages before forwarding a full `TrackMetadata` to the service.

Key behaviour:
- State accumulates across incremental updates
- Artwork URL changes trigger `now_playing.set_artwork_url()`
- `clear()` resets all accumulated state and calls `now_playing.clear()`

---

## Events (`ledfx/events.py`)

| Event type | Fired when |
|---|---|
| `NOW_PLAYING_TRACK_CHANGED` | Track identity changes |
| `NOW_PLAYING_METADATA_CHANGED` | Any metadata update |
| `NOW_PLAYING_ARTWORK_CHANGED` | Artwork stored and gradients extracted |
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

## Future Providers

The service is provider-agnostic. Any new provider needs only to:

1. Call `ledfx.now_playing.set_metadata(source_id, TrackMetadata(...))`
2. Call `ledfx.now_playing.set_artwork_url()` or `set_artwork_bytes()` when artwork changes
3. Call `ledfx.now_playing.clear(source_id)` on disconnect

Candidate future providers: Music Assistant, Spotify, Linux MPRIS, Windows media session, browser integrations.
