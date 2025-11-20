# Scenes API

**Scope:** This document defines the *Scenes* REST API. Scenes allow you to save and restore the active effects and configurations of all virtual devices.

**Base URL:** `http://<host>:<port>/api/scenes`

---

## Overview

A **Scene** is a snapshot of effect configurations across multiple virtual LED devices. When activated, it applies the saved effect type and configuration to each specified virtual device, allowing you to quickly switch between different lighting setups.

**Core capabilities:**
- Create, replace, delete any number of scenes
- Activate scenes (immediately or with delay) to restore saved configurations
- Deactivate scenes to clear virtual effects
- Retrieve all scenes or a single scene by ID
- Query active state of scenes
- Rename existing scenes
- Automatic preset detection for effect configurations
- Auto-capture all active virtuals or specify explicit virtual configurations

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
    "wled-breland-nightstand": {
      "action": "ignore"
    },
    "wled-dining-room": {
      "action": "stop"
    },
    "wled-lr-behind-couch": {
      "action": "activate",
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
    },
    "wled-accent-light": {
      "action": "forceblack"
    }
  },
  "active": true
}
```

**Field semantics:**
- `name` *(string, required)*: Human-readable scene name.
- `virtuals` *(object)*: Map of virtual device IDs to their effect configurations.
  - **Legacy format** (empty object `{}`): Virtual has no effect (turned off). Equivalent to `{"action": "ignore"}`.
  - **Legacy format** (with `type` and `config`): Apply the specified effect. Equivalent to `{"action": "activate", "type": "...", "config": {...}}`.
  - `action` *(string, optional)*: Controls how the scene affects this virtual. Allowed values:
    - `"ignore"`: Leave virtual unchanged (equivalent to empty object `{}`).
    - `"stop"`: Stop any playing effect on the virtual.
    - `"forceblack"`: Set the virtual to Single Color effect with black (#000000).
    - `"activate"`: Apply the effect configuration (requires `type` and `config`, or `preset`).
    - If omitted: Behaves as legacy mode (empty `{}` means ignore, presence of `type`/`config` means activate).
  - `type` *(string)*: Effect type identifier (required when `action` is `"activate"` and `preset` is not provided).
  - `config` *(object)*: Effect configuration parameters (required when `action` is `"activate"` and `preset` is not provided).
  - `preset` *(string)*: Preset name to apply (alternative to `type`/`config` when `action` is `"activate"`). If preset doesn't exist at activation time, it will be ignored.
- `scene_image` *(string, optional)*: UI image/icon identifier.
- `scene_tags` *(string, optional)*: Comma-separated tags for categorization.
- `scene_puturl` *(string, optional)*: HTTP endpoint to call when scene activates.
- `scene_payload` *(string, optional)*: Payload to send to `scene_puturl`.
- `scene_midiactivate` *(object, optional)*: MIDI activation configuration.
- `active` *(boolean)*: Indicates if the scene's configuration matches the current state of all virtuals.

### Virtual Action Behavior

The `action` field provides fine-grained control over how each virtual is affected when a scene is activated:

| Action | Effect | Use Case |
|--------|--------|----------|
| `ignore` | Virtual remains unchanged | Skip certain virtuals without affecting their current state |
| `stop` | Clear/stop any active effect | Turn off specific virtuals |
| `forceblack` | Apply Single Color effect (#000000) | Create a "blackout" or off appearance |
| `activate` | Apply specified effect config or preset | Standard effect activation |

**Legacy Compatibility:**
- Omitting `action` maintains backward compatibility
- Empty object `{}` behaves as `action: "ignore"`
- Object with `type`/`config` behaves as `action: "activate"`

**Preset Usage with `activate`:**
```json
{
  "virtual-id": {
    "action": "activate",
    "preset": "rainbow-scroll"
  }
}
```
At scene activation time, the preset is resolved from the current preset library. If the preset doesn't exist, the virtual is left unchanged.

### Active State Logic

A scene is considered `active` when:
- All virtuals in the scene match their current running state
- Effect types and configurations are identical
- Activating the scene would be a no-op

If any virtual differs from the scene definition, `active` returns `false`.

---

## Endpoints Summary

| Method | Path                    | Purpose                                    |
|-------:|-------------------------|--------------------------------------------|
|  POST  | `/api/scenes`           | Create or replace (upsert) a scene         |
|   PUT  | `/api/scenes`           | Control/mutate an existing scene           |
| DELETE | `/api/scenes`           | Delete a scene (legacy, requires JSON body)|
| DELETE | `/api/scenes/{id}`      | Delete a scene (RESTful)                   |
|   GET  | `/api/scenes`           | List all scenes with active flags          |
|   GET  | `/api/scenes/{id}`      | Get scene details                          |

**Conventions:**
- `Content-Type: application/json` for request bodies.
- Responses are snackbar-friendly and follow LedFx standard format:
  - Success: `{"status":"success", ...}` or with snackbar: `{"status":"success", "payload":{"type":"success", "reason":"message"}}`
  - Error: `{"status":"failed", "payload":{"type":"error", "reason":"message"}}`
- Status codes: `200 OK` for all responses (to ensure snackbar functionality works).
- Scene IDs are auto-generated from names (lowercase, hyphenated) if not provided.

---

## POST `/api/scenes` — Create/Replace (Upsert)

Creates a new scene or replaces an existing one with the same `id`.

### Request Body

**Auto-capture all virtuals** (recommended):
```json
{
  "name": "Evening Vibe",
  "scene_image": "Wallpaper",
  "scene_tags": "ambient,relaxing",
  "scene_puturl": "",
  "scene_payload": ""
}
```

When `virtuals` is omitted, the scene automatically captures all currently active virtuals in their current configuration.

**Specify virtuals explicitly**:
```json
{
  "id": "custom-scene",
  "name": "Custom Scene",
  "scene_image": "image: https://example.com/image.jpg",
  "scene_tags": "party,energetic",
  "scene_puturl": "",
  "scene_payload": "",
  "virtuals": {
    "falcon1": {
      "action": "activate",
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
      "action": "activate",
      "preset": "rainbow-scroll"
    },
    "strip3": {
      "action": "forceblack"
    },
    "strip4": {
      "action": "stop"
    },
    "strip5": {
      "action": "ignore"
    }
  }
}
```

**Legacy format (backward compatible)**:
```json
{
  "name": "Legacy Scene",
  "virtuals": {
    "falcon1": {
      "type": "blade_power_plus",
      "config": { /* ... */ }
    },
    "strip2": {}
  }
}
```

### Field Semantics

- `id` *(string, optional)*: Stable identifier. If omitted on creation, generated from `name` (lowercase, hyphenated). If provided and exists, the scene will be replaced (upsert).
- `name` *(string, required)*: Human-readable scene name.
- `virtuals` *(object, optional)*: Map of virtual device IDs to their effect configurations.
  - If omitted: Auto-captures all currently active virtuals.
  - Per-virtual `action` field controls behavior:
    - `"ignore"`: Leave virtual unchanged.
    - `"stop"`: Stop any playing effect.
    - `"forceblack"`: Apply Single Color effect with black.
    - `"activate"`: Apply effect (requires `type`/`config` or `preset`).
    - If `action` omitted: Legacy behavior (empty `{}` = ignore, `type`/`config` present = activate).
  - `type` *(string)*: Effect type identifier (required for `action: "activate"` without preset).
  - `config` *(object)*: Effect configuration parameters (required for `action: "activate"` without preset).
  - `preset` *(string)*: Preset name (alternative to `type`/`config` for `action: "activate"`).
- `scene_image` *(string, optional)*: UI image/icon identifier (defaults to "Wallpaper").
- `scene_tags` *(string, optional)*: Comma-separated tags for categorization.
- `scene_puturl` *(string, optional)*: HTTP endpoint to call when scene activates.
- `scene_payload` *(string, optional)*: Payload to send to `scene_puturl`.
- `scene_midiactivate` *(object, optional)*: MIDI activation configuration.

### Validation Rules

- `name`: required, non-empty string
- `virtuals`: if provided, must be a valid object mapping virtual IDs to effect configs

### Responses

**200 OK (success)**
```json
{
  "status": "success",
  "scene": {
    "id": "evening-vibe",
    "config": {
      "name": "Evening Vibe",
      "virtuals": { /* captured configuration */ },
      "scene_image": "Wallpaper",
      "scene_tags": "ambient,relaxing",
      "scene_puturl": "",
      "scene_payload": "",
      "scene_midiactivate": null
    }
  }
}
```

**200 OK (error)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Validation failed: name is required"
  }
}
```

---

## PUT `/api/scenes` — Control / Mutate

Action-based controller for scenes. All actions require an `id` to specify which scene to operate on.

### Scene Control Actions

```json
{ "id": "living-room", "action": "activate" }
```

- `activate` — Activates the specified scene, applying its effect configurations to all virtuals.
- `deactivate` — Deactivates the specified scene, clearing effects from its virtuals.
- `activate_in` — Schedules scene activation after a delay (requires `ms` field).
- `rename` — Renames the scene (requires `name` field).

### Action Details

#### Activate a Scene

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
  "payload": {
    "type": "info",
    "reason": "Activated Living Room"
  }
}
```

#### Activate with Delay

```json
{
  "id": "living-room",
  "action": "activate_in",
  "ms": 5000
}
```

Activates the scene after 5000ms (5 seconds).

**Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "Scene Living Room will activate in 5000ms"
  }
}
```

#### Deactivate a Scene

```json
{
  "id": "living-room",
  "action": "deactivate"
}
```

**Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "Deactivated Living Room"
  }
}
```

#### Rename a Scene

```json
{
  "id": "living-room",
  "action": "rename",
  "name": "Cozy Living Room"
}
```

**Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "Renamed Living Room to Cozy Living Room"
  }
}
```

---

## DELETE `/api/scenes` — Delete (Legacy)

Deletes a scene by ID. Requires JSON body with scene ID. This legacy endpoint is maintained for backward compatibility.

### Request Body

```json
{
  "id": "test-scene"
}
```

### Responses

**200 OK (success)**
```json
{
  "status": "success"
}
```

**200 OK (error)** — Scene does not exist:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene test-scene does not exist"
  }
}
```

---

## DELETE `/api/scenes/{id}` — Delete (RESTful)

Deletes a scene by ID. The scene ID is specified in the URL path.

### Responses

**200 OK (success)**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Scene 'test-scene' deleted."
  }
}
```

**200 OK (error)** — Scene not found:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene not found"
  }
}
```

### Example

```bash
curl -X DELETE http://localhost:8888/api/scenes/test-scene
```

---

## GET `/api/scenes` — List

Get all saved scenes with their configurations and active states. Includes automatic preset detection for all effect configurations.

### Response

**200 OK**

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
          },
          "preset": "rainbow-scroll",
          "preset_category": "ledfx_presets"
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

### Preset Detection

For each virtual with an effect configuration, the response includes:
- `preset` *(string)*: Matching preset ID (if found)
- `preset_category` *(string)*: Either `ledfx_presets` (system) or `user_presets` (custom)

Preset matching ignores UI-only keys like `advanced` and `diag` when comparing configurations.

In this example:
- `Living Room` scene is `active` because all virtuals match the scene definition
- `wled-lr-behind-couch` effect matches the "rainbow-scroll" preset from system presets
- `Off` scene is not `active` because virtuals are showing different effects

---

## GET `/api/scenes/{scene_id}` — Details

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

**200 OK (error)** - Scene does not exist:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene living-room does not exist"
  }
}
```

---

## Examples (cURL)

**Create / replace a scene (auto-capture all virtuals)**
```bash
curl -X POST http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Evening Vibe",
    "scene_image":"Wallpaper",
    "scene_tags":"ambient,relaxing"
  }'
```

**Create / replace a scene with explicit ID and virtuals**
```bash
curl -X POST http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "id":"living-room",
    "name":"Living Room",
    "scene_image":"Wallpaper",
    "virtuals":{
      "wled-lr-behind-couch":{
        "action":"activate",
        "type":"scroll_plus",
        "config":{
          "background_brightness":1.0,
          "blur":3.0,
          "brightness":1.0,
          "color_high":"#0000ff",
          "color_lows":"#ff0000",
          "color_mids":"#00ff00"
        }
      },
      "wled-dining-room":{
        "action":"stop"
      }
    }
  }'
```

**Create scene using presets and mixed actions**
```bash
curl -X POST http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Party Mode",
    "virtuals":{
      "strip1":{
        "action":"activate",
        "preset":"rainbow-scroll"
      },
      "strip2":{
        "action":"activate",
        "preset":"bass-pulse"
      },
      "strip3":{
        "action":"forceblack"
      },
      "strip4":{
        "action":"ignore"
      }
    }
  }'
```

**Activate a scene**
```bash
curl -X PUT http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{ "id":"living-room", "action":"activate" }'
```

**Activate a scene with delay**
```bash
curl -X PUT http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{ "id":"living-room", "action":"activate_in", "ms":5000 }'
```

**Deactivate a scene**
```bash
curl -X PUT http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{ "id":"living-room", "action":"deactivate" }'
```

**Rename a scene**
```bash
curl -X PUT http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{ "id":"living-room", "action":"rename", "name":"Cozy Living Room" }'
```

**Delete a scene (legacy method with JSON body)**
```bash
curl -X DELETE http://localhost:8888/api/scenes \
  -H "Content-Type: application/json" \
  -d '{ "id":"test-scene" }'
```

**Delete a scene (RESTful method)**
```bash
curl -X DELETE http://localhost:8888/api/scenes/test-scene
```

**List all scenes**
```bash
curl -X GET http://localhost:8888/api/scenes
```

**Get a specific scene**
```bash
curl -X GET http://localhost:8888/api/scenes/living-room
```

---

## Validation (Voluptuous sketch)

```python
VirtualActionSchema = vol.Schema({
  vol.Optional("action"): vol.In(["ignore", "stop", "forceblack", "activate"]),
  vol.Optional("type"): str,  # Required if action="activate" and preset not provided
  vol.Optional("config"): dict,  # Required if action="activate" and preset not provided
  vol.Optional("preset"): str,  # Alternative to type/config for action="activate"
})

SceneSchema = vol.Schema({
  vol.Optional("id"): str,
  vol.Required("name"): str,
  vol.Optional("virtuals"): {str: VirtualActionSchema},  # Map of virtual_id -> action config
  vol.Optional("scene_image", default="Wallpaper"): str,
  vol.Optional("scene_tags"): vol.Any(str, None),
  vol.Optional("scene_puturl"): vol.Any(str, None),
  vol.Optional("scene_payload"): vol.Any(str, None),
  vol.Optional("scene_midiactivate"): vol.Any(dict, None),
})
```

**Validation rules:**
- If `action` is `"activate"`, either (`type` and `config`) or `preset` must be provided
- If `action` is `"ignore"`, `"stop"`, or `"forceblack"`, no other fields are required
- If `action` is omitted:
  - Empty object `{}` is valid (legacy ignore behavior)
  - Object with `type` and `config` is valid (legacy activate behavior)
  - Preset field alone is not valid without explicit `action: "activate"`

---

## Integration with Playlists

Scenes are referenced by `scene_id` in [Playlists](playlists.md). When a playlist activates a scene, it uses the `PUT /api/scenes` endpoint with `action: "activate"`.
