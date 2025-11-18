# Scenes API

**Scope:** This document defines the *Scenes* REST API. Scenes allow you to save and restore the active effects and configurations of all virtual devices.

**Base URL:** `http://<host>:<port>/api/scenes`

---

## Overview

A **Scene** is a snapshot of effect configurations across multiple virtual LED devices. When activated, it applies the saved effect type and configuration to each specified virtual device, allowing you to quickly switch between different lighting setups.

**Core capabilities:**
- Create, update, and delete scenes
- Activate scenes to restore saved configurations
- Retrieve all scenes or a single scene by ID
- Query active state of scenes
- Automatic preset detection for effect configurations

---

## Data Model

### Scene Object

```json
{
  "name": "Living Room",
  "scene_image": "Wallpaper",
  "scene_midiactivate": null,
  "scene_payload": null,
  "scene_puturl": null,
  "scene_tags": null,
  "virtuals": {
    "wled-breland-nightstand": {},
    "wled-dining-room": {},
    "wled-lr-behind-couch": {
      "type": "scroll_plus",
      "config": {
        "background_brightness": 1.0,
        "background_color": "#000000",
        "blur": 3.0,
        "brightness": 1.0,
        "color_high": "#0000ff",
        "color_lows": "#ff0000",
        "color_mids": "#00ff00",
        "decay_per_sec": 0.5,
        "flip": false,
        "mirror": true,
        "scroll_per_sec": 0.7,
        "threshold": 0.0
      }
    }
  },
  "active": true
}
```

**Field semantics:**
- `name` *(string, required)*: Human-readable scene name.
- `virtuals` *(object)*: Map of virtual device IDs to their effect configurations.
  - Empty object `{}`: Virtual has no effect (turned off).
  - `type` *(string)*: Effect type identifier.
  - `config` *(object)*: Effect configuration parameters.
- `scene_image` *(string, optional)*: UI image/icon identifier.
- `scene_tags` *(string, optional)*: Comma-separated tags for categorization.
- `scene_puturl` *(string, optional)*: HTTP endpoint to call when scene activates.
- `scene_payload` *(string, optional)*: Payload to send to `scene_puturl`.
- `scene_midiactivate` *(object, optional)*: MIDI activation configuration.
- `active` *(boolean)*: Indicates if the scene's configuration matches the current state of all virtuals.

### Active State Logic

A scene is considered `active` when:
- All virtuals in the scene match their current running state
- Effect types and configurations are identical
- Activating the scene would be a no-op

If any virtual differs from the scene definition, `active` returns `false`.

---

## Endpoints Summary

| Method | Path                    | Purpose                              |
|-------:|-------------------------|--------------------------------------|
|   GET  | `/api/scenes`           | List all scenes with active flags    |
|   GET  | `/api/scenes/{id}`      | Get a specific scene by ID           |
|  POST  | `/api/scenes`           | Create or update a scene             |
|   PUT  | `/api/scenes`           | Activate, deactivate, or rename scene|
| DELETE | `/api/scenes`           | Delete a scene                       |

**Conventions:**
- `Content-Type: application/json` for request bodies.
- Scene IDs are auto-generated from names (lowercase, hyphenated).
- Pass `id` (not `name`) for scene identification in requests.

---

## GET /api/scenes

Get all saved scenes with their configurations and active states.

### Response

```json
{
  "status": "success",
  "scenes": {
    "living-room": {
      "name": "Living Room",
      "scene_image": "Wallpaper",
      "scene_midiactivate": null,
      "scene_payload": null,
      "scene_puturl": null,
      "scene_tags": null,
      "virtuals": {
        "wled-breland-nightstand": {},
        "wled-dining-room": {},
        "wled-lr-behind-couch": {
          "type": "scroll_plus",
          "config": {
            "background_brightness": 1.0,
            "background_color": "#000000",
            "blur": 3.0,
            "brightness": 1.0,
            "color_high": "#0000ff",
            "color_lows": "#ff0000",
            "color_mids": "#00ff00",
            "decay_per_sec": 0.5,
            "flip": false,
            "mirror": true,
            "scroll_per_sec": 0.7,
            "threshold": 0.0
          }
        }
      },
      "active": true
    },
    "off": {
      "name": "Off",
      "virtuals": {
        "wled-breland-nightstand": {},
        "wled-dining-room": {},
        "wled-lr-behind-couch": {}
      },
      "scene_image": "Wallpaper",
      "scene_puturl": null,
      "scene_tags": null,
      "scene_payload": null,
      "scene_midiactivate": null,
      "active": false
    }
  }
}
```

In this example:
- `Living Room` scene is `active` because all virtuals match the scene definition
- `Off` scene is not `active` because virtuals are showing different effects

---

## GET /api/scenes/{scene_id}

Get a specific scene by its ID. Returns the scene configuration with an `active` flag and automatic preset detection.

### URL Parameters

- `scene_id` *(string, required)*: The scene identifier (e.g., `living-room`)

### Response

```json
{
  "status": "success",
  "scene": {
    "id": "living-room",
    "config": {
      "name": "Living Room",
      "active": true,
      "scene_image": "Wallpaper",
      "scene_midiactivate": null,
      "scene_payload": null,
      "scene_puturl": null,
      "scene_tags": null,
      "virtuals": {
        "wled-lr-behind-couch": {
          "type": "scroll_plus",
          "config": {
            "background_brightness": 1.0,
            "blur": 3.0,
            "brightness": 1.0,
            "color_high": "#0000ff",
            "color_lows": "#ff0000",
            "color_mids": "#00ff00"
          },
          "preset": "rainbow-scroll",
          "preset_category": "ledfx_presets"
        },
        "wled-dining-room": {}
      }
    }
  }
}
```

### Preset Detection

For each virtual with an effect configuration, the response includes:
- `preset` *(string)*: Matching preset ID (if found)
- `preset_category` *(string)*: Either `ledfx_presets` (system) or `user_presets` (custom)

Preset matching ignores UI-only keys like `advanced` and `diag` when comparing configurations.

### Error Responses

**200 OK with error payload** - Scene does not exist:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene {scene_id} does not exist"
  }
}
```

Note: Errors return 200 status code for snackbar compatibility in the UI.

---

## POST /api/scenes

Create a new scene or update an existing one with the current state of virtuals.

### Request Body

**Auto-capture all virtuals** (recommended):
```json
{
  "name": "Evening Vibe",
  "scene_image": "",
  "scene_tags": "ambient,relaxing",
  "scene_puturl": "",
  "scene_payload": ""
}
```

When `virtuals` is omitted, the scene automatically captures all currently active virtuals in their current configuration.

**Specify virtuals explicitly**:
```json
{
  "name": "Custom Scene",
  "scene_image": "image: https://example.com/image.jpg",
  "scene_tags": "party,energetic",
  "scene_puturl": "",
  "scene_payload": "",
  "virtuals": {
    "falcon1": {
      "type": "blade_power_plus",
      "config": {
        "background_brightness": 1,
        "background_color": "#000000",
        "blur": 2,
        "brightness": 1,
        "decay": 0.7,
        "flip": false,
        "frequency_range": "Lows (beat+bass)",
        "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%)",
        "mirror": false,
        "multiplier": 0.5
      }
    },
    "strip2": {
      "type": "energy",
      "config": {
        "blur": 4,
        "brightness": 1,
        "color_high": "#0000ff",
        "color_lows": "#ff0000",
        "mirror": true
      }
    }
  }
}
```

### Response

```json
{
  "status": "success",
  "scene": {
    "id": "evening-vibe",
    "config": {
      "name": "Evening Vibe",
      "virtuals": { /* captured configuration */ }
    }
  }
}
```

---

## PUT /api/scenes

Activate, deactivate, or rename a scene.

### Activate a Scene

```json
{
  "id": "living-room",
  "action": "activate"
}
```

**Response:**
```json
{
  "status": "success",
  "type": "info",
  "message": "Activated Living Room"
}
```

### Activate with Delay

```json
{
  "id": "living-room",
  "action": "activate_in",
  "ms": 5000
}
```

Activates the scene after 5000ms (5 seconds).

### Deactivate a Scene

```json
{
  "id": "living-room",
  "action": "deactivate"
}
```

### Rename a Scene

```json
{
  "id": "living-room",
  "action": "rename",
  "name": "Cozy Living Room"
}
```

---

## DELETE /api/scenes

Delete a scene by ID.

### Request Body

```json
{
  "id": "test-scene"
}
```

### Response

```json
{
  "status": "success"
}
```

### Error Responses

**200 OK with error payload** - Scene does not exist:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene {scene_id} does not exist"
  }
}
```

Note: Errors return 200 status code for snackbar compatibility in the UI.

---

## Integration with Playlists

Scenes are referenced by `scene_id` in [Playlists](playlists.md). When a playlist activates a scene, it uses the `PUT /api/scenes` endpoint with `action: "activate"`.
