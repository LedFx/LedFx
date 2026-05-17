# Now Playing API

## Overview

The Now Playing API provides access to LedFx's centralized media playback state. It exposes the current track metadata, artwork reference, extracted gradient information, and service configuration.

The Now Playing Service is **provider-neutral** — it receives normalized metadata from any configured source (currently Sendspin) and presents a single unified view. Effects and other consumers remain unaware of which provider supplied the data.

**Base URL:** `http://<host>:<port>/api/now-playing`

### Key Concepts

- **Metadata**: Track title, artist, album, duration, and playback position from the active provider.
- **Artwork**: Album art stored as a managed asset at `assets/now_playing/now_playing.{ext}`, with automatic gradient extraction.
- **Gradients**: LED-optimized color gradients extracted from artwork in three variants (`led_safe`, `led_punchy`, `led_max`). These can be automatically applied to target virtuals.
- **Configuration**: Controls gradient application, track text display, and album art display behavior.

---

## Data Model

### Now Playing State

The GET response combines the current playback state with the service configuration.

```json
{
  "active_source_id": "sendspin",
  "metadata": { ... },
  "artwork": { ... },
  "selected_gradient_variant": "led_punchy",
  "current_gradient": "linear-gradient(90deg, rgb(180,40,20) 0%, rgb(220,160,50) 50%, rgb(40,80,160) 100%)",
  "updated_at": 1716000000.123,
  "config": { ... }
}
```

**Top-level Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `active_source_id` | string \| null | Provider currently supplying metadata (e.g. `"sendspin"`). Null when no provider is active. |
| `metadata` | object \| null | Current track metadata. Null when no track is playing. |
| `artwork` | object \| null | Current artwork reference with gradient data. Null when no artwork is available. |
| `selected_gradient_variant` | string | Active gradient variant: `"led_safe"`, `"led_punchy"`, or `"led_max"`. |
| `current_gradient` | string \| null | Resolved CSS gradient string for the selected variant. Null when no artwork/gradients available. |
| `updated_at` | float \| null | Unix timestamp of the last state update. |
| `config` | object | Current service configuration (see Configuration section). |

### Metadata Object

```json
{
  "source_id": "sendspin",
  "title": "Midnight City",
  "artist": "M83",
  "album": "Hurry Up, We're Dreaming",
  "duration": 244.0,
  "position": 42.5,
  "track_id": "spotify:track:6GyFP1nfCDB8lbD2bG0Hq9",
  "artwork_url": "https://i.scdn.co/image/ab67616d0000b273...",
  "artwork_hash": "a1b2c3d4e5f6g7h8",
  "updated_at": 1716000000.123
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | string | Provider that supplied this metadata. |
| `title` | string \| null | Track title. |
| `artist` | string \| null | Track artist. |
| `album` | string \| null | Album name. |
| `duration` | float \| null | Track duration in seconds. |
| `position` | float \| null | Current playback position in seconds. |
| `track_id` | string \| null | Provider-specific track identifier. |
| `artwork_url` | string \| null | Original artwork URL from the provider. |
| `artwork_hash` | string \| null | Hash for artwork change detection. |
| `updated_at` | float \| null | Unix timestamp when this metadata was last updated. |

### Artwork Object

```json
{
  "source_id": "sendspin",
  "url": "https://i.scdn.co/image/ab67616d0000b273...",
  "cache_key": "C:/Users/user/.ledfx/assets/now_playing/now_playing.jpg",
  "content_type": "image/jpeg",
  "hash": "a1b2c3d4e5f6g7h8",
  "width": 640,
  "height": 640,
  "gradients": {
    "led_safe": {
      "gradient": "linear-gradient(90deg, rgb(180,40,20) 0%, ...)"
    },
    "led_punchy": {
      "gradient": "linear-gradient(90deg, rgb(220,50,10) 0%, ...)"
    },
    "led_max": {
      "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, ...)"
    },
    "metadata": {
      "pattern": "interleaved",
      "has_dominant_background": true
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | string | Provider that supplied this artwork. |
| `url` | string \| null | Original artwork URL (null for byte-based artwork). |
| `cache_key` | string \| null | Absolute path to the stored artwork file. |
| `content_type` | string \| null | MIME type of the artwork image. |
| `hash` | string \| null | Content hash for change detection (SHA-256 prefix). |
| `width` | int \| null | Image width in pixels. |
| `height` | int \| null | Image height in pixels. |
| `gradients` | object \| null | Extracted gradient variants and extraction metadata. |

### Gradient Variants

Three LED-optimized gradient variants are extracted from each artwork image:

| Variant | Description |
|---------|-------------|
| `led_safe` | Closest to the source image colors. Conservative but accurate. |
| `led_punchy` | Enhanced saturation and contrast. Best default for physical LEDs. |
| `led_max` | Maximum saturation and vibrancy. High-impact but may be too aggressive. |

Each variant contains a `gradient` field with a CSS `linear-gradient(...)` string that can be used directly by LedFx effects.

### Configuration Object

```json
{
  "gradient": {
    "enabled": true,
    "variant": "led_punchy",
    "virtual_ids": []
  },
  "track_text": {
    "mode": "off",
    "duration": 8,
    "virtual_ids": [],
    "fallback_effect": "text"
  },
  "album_art": {
    "mode": "off",
    "duration": 10,
    "virtual_ids": [],
    "fallback_effect": "image"
  }
}
```

#### Gradient Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Whether to apply extracted gradients to target virtuals on track change. |
| `variant` | string | `"led_punchy"` | Which gradient variant to use. One of: `led_safe`, `led_punchy`, `led_max`. |
| `virtual_ids` | array of strings | `[]` | Virtual IDs to target for gradient application. Empty array means all virtuals. |

#### Track Text Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `"off"` | Display mode. One of: `off`, `temporary`, `continuous`. |
| `duration` | int | `8` | Duration in seconds for temporary text display (1–60). |
| `virtual_ids` | array of strings | `[]` | Target matrix virtual IDs for text display. |
| `fallback_effect` | string | `"text"` | Effect type to use for text display. |

#### Album Art Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `"off"` | Display mode. One of: `off`, `temporary`, `continuous`. |
| `duration` | int | `10` | Duration in seconds for temporary art display (1–60). |
| `virtual_ids` | array of strings | `[]` | Target matrix virtual IDs for art display. |
| `fallback_effect` | string | `"image"` | Effect type to use for artwork display. |

---

## Endpoints

### Get Now Playing State

Returns the current playback state, artwork, gradients, and configuration.

**`GET /api/now-playing`**

**Success Response (bare response — no status wrapper):**

When a track is playing:
```json
{
  "active_source_id": "sendspin",
  "metadata": {
    "source_id": "sendspin",
    "title": "Midnight City",
    "artist": "M83",
    "album": "Hurry Up, We're Dreaming",
    "duration": 244.0,
    "position": 42.5,
    "track_id": null,
    "artwork_url": "https://example.com/art.jpg",
    "artwork_hash": "a1b2c3d4",
    "updated_at": 1716000000.123
  },
  "artwork": {
    "source_id": "sendspin",
    "url": "https://example.com/art.jpg",
    "cache_key": "/home/user/.ledfx/assets/now_playing/now_playing.jpg",
    "content_type": "image/jpeg",
    "hash": "a1b2c3d4",
    "width": 640,
    "height": 640,
    "gradients": {
      "led_safe": {
        "gradient": "linear-gradient(90deg, rgb(180,40,20) 0%, rgb(200,150,40) 50%, rgb(40,80,160) 100%)"
      },
      "led_punchy": {
        "gradient": "linear-gradient(90deg, rgb(220,50,10) 0%, rgb(240,180,20) 50%, rgb(20,60,200) 100%)"
      },
      "led_max": {
        "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(255,200,0) 50%, rgb(0,40,255) 100%)"
      },
      "metadata": {
        "pattern": "interleaved",
        "has_dominant_background": true
      }
    }
  },
  "selected_gradient_variant": "led_punchy",
  "current_gradient": "linear-gradient(90deg, rgb(220,50,10) 0%, rgb(240,180,20) 50%, rgb(20,60,200) 100%)",
  "updated_at": 1716000000.123,
  "config": {
    "gradient": {
      "enabled": true,
      "variant": "led_punchy",
      "virtual_ids": []
    },
    "track_text": {
      "mode": "off",
      "duration": 8,
      "virtual_ids": [],
      "fallback_effect": "text"
    },
    "album_art": {
      "mode": "off",
      "duration": 10,
      "virtual_ids": [],
      "fallback_effect": "image"
    }
  }
}
```

When no track is playing (idle state):
```json
{
  "active_source_id": null,
  "metadata": null,
  "artwork": null,
  "selected_gradient_variant": "led_punchy",
  "current_gradient": null,
  "updated_at": null,
  "config": {
    "gradient": {
      "enabled": true,
      "variant": "led_punchy",
      "virtual_ids": []
    },
    "track_text": {
      "mode": "off",
      "duration": 8,
      "virtual_ids": [],
      "fallback_effect": "text"
    },
    "album_art": {
      "mode": "off",
      "duration": 10,
      "virtual_ids": [],
      "fallback_effect": "image"
    }
  }
}
```

---

### Update Configuration

Updates the Now Playing configuration. Accepts a partial or full configuration object; unspecified sections retain their current values.

**`PUT /api/now-playing`**

**Request Body:**

Partial update (only gradient section):
```json
{
  "gradient": {
    "enabled": false,
    "variant": "led_max"
  }
}
```

Full update (all sections):
```json
{
  "gradient": {
    "enabled": true,
    "variant": "led_punchy",
    "virtual_ids": ["wled-living-room", "wled-bedroom"]
  },
  "track_text": {
    "mode": "temporary",
    "duration": 5,
    "virtual_ids": ["matrix-panel"],
    "fallback_effect": "text"
  },
  "album_art": {
    "mode": "off",
    "duration": 10,
    "virtual_ids": [],
    "fallback_effect": "image"
  }
}
```

**Success Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Now Playing configuration updated.",
    "data": {
      "gradient": {
        "enabled": true,
        "variant": "led_punchy",
        "virtual_ids": ["wled-living-room", "wled-bedroom"]
      },
      "track_text": {
        "mode": "temporary",
        "duration": 5,
        "virtual_ids": ["matrix-panel"],
        "fallback_effect": "text"
      },
      "album_art": {
        "mode": "off",
        "duration": 10,
        "virtual_ids": [],
        "fallback_effect": "image"
      }
    }
  }
}
```

**Validation Error (invalid variant):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "value is not allowed for dictionary value @ data['gradient']['variant']"
  }
}
```

**Validation Error (duration out of range):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "value must be at least 1 for dictionary value @ data['track_text']['duration']"
  }
}
```

**Invalid JSON:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "JSON Decode Error"
  }
}
```

**Non-object body:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Request body must be a JSON object."
  }
}
```

---

## Configuration Behavior

### Gradient Application

When `gradient.enabled` is `true` and a new artwork gradient is extracted, the service automatically applies the selected gradient variant to the target virtuals. This uses the same code path as the global effects API (`PUT /api/effects` with `apply_global` action):

- Resolves the CSS gradient string into color stops
- Samples color groups from the gradient
- Updates each active effect's gradient and color keys
- Persists the updated effect configurations

If `gradient.virtual_ids` is empty, all virtuals with active effects are updated. If specific IDs are provided, only those virtuals are targeted.

### Partial Updates

The PUT endpoint supports section-level partial updates:

```json
{"gradient": {"enabled": false}}
```

This disables gradient application without affecting `track_text` or `album_art` configuration. Within each section, unspecified fields retain their defaults from the schema.

### Variant Switching

When the gradient `variant` is changed (e.g. from `led_punchy` to `led_max`), the service immediately re-resolves the gradient from the cached artwork metadata — no re-download or re-extraction needed. If gradient application is enabled, the new variant is applied to target virtuals.

---

## Events

The Now Playing Service fires the following LedFx events that frontends and other systems can subscribe to:

| Event | Fired When |
|-------|------------|
| `now_playing_track_changed` | Track identity changes (title, artist, album, or track_id). |
| `now_playing_metadata_changed` | Any metadata update (including position-only updates). |
| `now_playing_artwork_changed` | New artwork is downloaded and stored. |
| `now_playing_gradient_changed` | The resolved gradient string changes (new artwork or variant switch). |
| `now_playing_cleared` | The active provider is cleared (e.g. disconnected). |

---

## Provider Integration

The Now Playing Service currently supports **Sendspin** as a metadata provider. When connected to a Sendspin server, track metadata and artwork URLs are automatically forwarded to the Now Playing Service.

Sendspin provides:
- Track title, artist, album
- Artwork URL
- Track duration and playback progress
- Track ID

Provider integration is automatic — no additional configuration is required beyond connecting to a Sendspin server via the [Sendspin Servers API](sendspin_servers.md).

---

## Usage Examples

### Poll Current State

```bash
curl http://localhost:8888/api/now-playing
```

### Enable Gradient Application to Specific Virtuals

```bash
curl -X PUT http://localhost:8888/api/now-playing \
  -H "Content-Type: application/json" \
  -d '{
    "gradient": {
      "enabled": true,
      "variant": "led_punchy",
      "virtual_ids": ["wled-living-room", "wled-bedroom"]
    }
  }'
```

### Disable Gradient Application

```bash
curl -X PUT http://localhost:8888/api/now-playing \
  -H "Content-Type: application/json" \
  -d '{"gradient": {"enabled": false}}'
```

### Switch to Maximum Saturation Variant

```bash
curl -X PUT http://localhost:8888/api/now-playing \
  -H "Content-Type: application/json" \
  -d '{"gradient": {"variant": "led_max"}}'
```

### Configure Temporary Track Text Display

```bash
curl -X PUT http://localhost:8888/api/now-playing \
  -H "Content-Type: application/json" \
  -d '{
    "track_text": {
      "mode": "temporary",
      "duration": 5,
      "virtual_ids": ["matrix-panel"]
    }
  }'
```
