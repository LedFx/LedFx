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
    - `"activate"`: Apply the effect configuration (requires `type` field, plus either `config` or `preset`).
    - If omitted: Behaves as legacy mode (empty `{}` means ignore, presence of `type`/`config` means activate).
  - `type` *(string)*: Effect type identifier (required when `action` is `"activate"`).
  - `config` *(object)*: Effect configuration parameters (required when `action` is `"activate"` unless `preset` is provided).
  - `preset` *(string)*: Preset name to apply instead of explicit `config` (when `action` is `"activate"`). Must be combined with `type` to identify which effect's preset library to search. If preset doesn't exist at activation time, the effect will automatically fall back to the `reset` preset (factory defaults).
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
    "type": "scroll_plus",
    "preset": "rainbow-scroll"
  }
}
```
At scene activation time, the preset is resolved from the specified effect type's preset library (searching both system and user presets). If the preset doesn't exist for that effect type, the effect will automatically fall back to the `reset` preset (factory defaults).

**Special Presets:**
- `"reset"`: Generates the default configuration for the specified effect type. This is always available for any effect and restores factory default settings. This is also used as an automatic fallback when a requested preset is not found.

### Active State Logic

A scene is considered `active` when all virtuals in the scene match their expected state based on their action type:

- **`action: "ignore"`**: Always matches (virtual is skipped in comparison)
- **`action: "stop"`**: Matches when the virtual has no active effect
- **`action: "forceblack"`**: Matches when the virtual has a Single Color effect with black (#000000)
- **`action: "activate"`**: Matches when the virtual has the specified effect type and configuration
  - For explicit `config`: Current effect config must match the specified config
  - For `preset`: Current effect config must match the resolved preset config
- **Legacy format** (no action field):
  - Empty object `{}`: Treated as `"ignore"` (always matches)
  - Object with `type`/`config`: Treated as `"activate"` (must match effect and config)

If any virtual differs from its expected state based on the action, `active` returns `false`.

**Examples:**

- Scene with `action: "ignore"` on a virtual is always active regardless of the virtual's current state
- Scene with `action: "stop"` is active only when the virtual has no effect running
- Scene with `action: "forceblack"` is active only when the virtual shows black (Single Color #000000)
- Scene with `action: "activate"` and preset is active when the virtual's effect matches the resolved preset configuration

If any virtual referenced in the scene no longer exists, the scene is not active.

---

## Endpoints Summary

| Method | Path                        | Purpose                                    |
|-------:|-----------------------------|--------------------------------------------|
|  POST  | `/api/scenes`               | Create a new scene or update existing one  |
|   PUT  | `/api/scenes`               | Control/mutate an existing scene           |
| DELETE | `/api/scenes`               | Delete a scene (legacy, requires JSON body)|
| DELETE | `/api/scenes/{scene_id}`    | Delete a scene (RESTful)                   |
|   GET  | `/api/scenes`               | List all scenes with active flags          |
|   GET  | `/api/scenes/{scene_id}`    | Get scene details                          |

**Conventions:**
- `Content-Type: application/json` for request bodies.
- Responses are snackbar-friendly and follow LedFx standard format:
  - Success: `{"status":"success", ...}` or with snackbar: `{"status":"success", "payload":{"type":"success", "reason":"message"}}`
  - Error: `{"status":"failed", "payload":{"type":"error", "reason":"message"}}`
- Status codes: `200 OK` for all responses (to ensure snackbar functionality works).
- Scene IDs are auto-generated from names (lowercase, hyphenated) if not provided.

---

## POST `/api/scenes` — Create or Update

Creates a new scene or updates an existing one.

**Operation Logic:**
- **Create**: Omit `id` field. A new scene is created with an auto-generated ID from the `name` (lowercase, hyphenated).
- **Update**: Provide `id` field with an existing scene ID. The scene will be updated, preserving any fields not explicitly provided in the request.
- **Error**: Providing a non-existent `id` will return an error. To create a new scene, omit the `id` field entirely.

### Request Body

**Auto-capture all virtuals** (recommended):
```json
{
  "name": "Evening Vibe",
  "snapshot": true,
  "scene_image": "Wallpaper",
  "scene_tags": "ambient,relaxing",
  "scene_puturl": "",
  "scene_payload": ""
}
```

With `snapshot: true`, the scene captures all currently active virtuals in their runtime configuration. The `virtuals` field is omitted and auto-captured.

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
      "type": "scroll_plus",
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

- `id` *(string, optional)*:
  - **For create**: Omit this field. The ID will be auto-generated from `name` (lowercase, hyphenated).
  - **For update**: Provide the existing scene ID. If the ID does not exist, the request will fail.
- `name` *(string)*:
  - **For create**: Required, non-empty string.
  - **For update**: Optional. If omitted, the existing name is preserved.
- `snapshot` *(boolean, optional, default: false)*: Controls how virtuals are captured.
  - **true**: Captures current runtime configuration of all active virtuals, ignoring any provided `virtuals` field.
  - **false**: Uses provided `virtuals` field, or preserves existing configuration if omitted.
  - **Note**: Creates without a `virtuals` field automatically enable snapshot.
- `virtuals` *(object, optional)*: Map of virtual device IDs to their effect configurations.
  - **For create**: If omitted (and `snapshot=false`), snapshot is automatically enabled to capture current state.
  - **For update**: If omitted, existing virtuals configuration is preserved.
  - **With `snapshot=true`**: This field is ignored; current runtime state is captured instead.
  - Per-virtual `action` field controls behavior:
    - `"ignore"`: Leave virtual unchanged.
    - `"stop"`: Stop any playing effect.
    - `"forceblack"`: Apply Single Color effect with black.
    - `"activate"`: Apply effect (requires `type`/`config` or `preset`).
    - If `action` omitted: Legacy behavior (empty `{}` = ignore, `type`/`config` present = activate).
  - `type` *(string)*: Effect type identifier (required for `action: "activate"`).
  - `config` *(object)*: Effect configuration parameters (required for `action: "activate"` when not using `preset`).
  - `preset` *(string)*: Preset name to use instead of explicit `config` (when `action: "activate"`). Must be combined with `type` to identify which effect's preset library to search.
- `scene_image`, `scene_tags`, `scene_puturl`, `scene_payload`, `scene_midiactivate` *(optional)*:
  - **For create**: Optional fields with defaults (scene_image defaults to "Wallpaper").
  - **For update**: Optional. If omitted, existing values are preserved.

### Validation Rules

- **Create**: `name` is required and must be a non-empty string. `id` must not be provided.
- **Update**: `id` must be provided and must exist. `name` and other fields are optional.
- `virtuals`: if provided, must be a valid object mapping virtual IDs to effect configs

### Responses

**200 OK (success - create)**
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

**200 OK (success - update)**
```json
{
  "status": "success",
  "scene": {
    "id": "evening-vibe",
    "config": {
      "name": "Evening Vibe",
      "virtuals": { /* updated configuration */ },
      "scene_image": "Wallpaper",
      "scene_tags": "ambient,relaxing,updated",
      "scene_puturl": "",
      "scene_payload": "",
      "scene_midiactivate": null
    }
  }
}
```

**200 OK (error - validation)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Required attribute 'name' was not provided"
  }
}
```

**200 OK (error - non-existent ID)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Scene with id 'non-existent' does not exist. To create a new scene, omit the 'id' field."
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
        "type":"scroll_plus",
        "preset":"rainbow-scroll"
      },
      "strip2":{
        "action":"activate",
        "type":"singleColor",
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
  vol.Optional("type"): str,  # Required if action="activate"
  vol.Optional("config"): dict,  # Required if action="activate" and preset not provided
  vol.Optional("preset"): str,  # Alternative to config for action="activate", requires type
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
- If `action` is `"activate"`, `type` is required, and either `config` or `preset` must be provided
- If `action` is `"ignore"`, `"stop"`, or `"forceblack"`, no other fields are required
- If `action` is omitted:
  - Empty object `{}` is valid (legacy ignore behavior)
  - Object with `type` and `config` is valid (legacy activate behavior)
  - `preset` field requires both `action: "activate"` and `type` to be valid

---

## Integration with Playlists

Scenes are referenced by `scene_id` in [Playlists](playlists.md). When a playlist activates a scene, it uses the `PUT /api/scenes` endpoint with `action: "activate"`.
