# Playlists API

**Scope:** This document defines the *Playlists* REST API only. It assumes Scenes already exist and are addressable by `scene_id`.

**Base URL:** `http://<host>:<port>/api/playlists`

---

## Overview

A **Playlist** is an ordered collection of **scene references** (by `scene_id`) with per-item (or default) durations. When started, the backend activates each scene in sequence (or randomized order) and schedules the next activation after its duration. A single playlist may be active at a time.

**Core capabilities:**
- Create, replace, delete any number of playlists
- Start/stop/pause/resume playback
- Shuffle (random) order and sequential playback
- Per-item durations, default duration and jitter multipliers
- Immediate **bump** `next` and `prev` scene (bypassing timeout)
- Randomized order per cycle while ensuring each item plays once per cycle

---

## Data Model

### Playlist Object

```json
{
  "id": "evening-cycle",
  "name": "Evening Cycle",
  "items": [
    { "scene_id": "warm-fade",   "duration_ms": 30000 },
    { "scene_id": "neon-ripple", "duration_ms": 45000 },
    { "scene_id": "calm-amber" }
  ],
  "default_duration_ms": 30000,
  "mode": "sequence",
  "timing": {
    "jitter": {
      "enabled": true,
      "factor_min": 0.5,
      "factor_max": 2.0
    }
  },
  "tags": ["ambient", "night"],
  "image": null
}
```

**Field semantics**
- `id` *(string)*: Stable identifier. If omitted on creation, generated from `name` (lowercase, hyphenated).
- `name` *(string)*: Human-readable title.
- `items[*]` *(array of objects)*:
  - `scene_id` *(string, required)*: Existing scene identifier.
  - `duration_ms` *(int, optional)*: Overrides default duration for this item.
- `default_duration_ms` *(int, optional)*: Used when an item omits `duration_ms`. If both are absent, the server enforces a minimum/default behavior (implementation enforces a minimum of 500ms per item).
- `mode` *(string)*: `"sequence"` (in order) or `"shuffle"` (randomized once per cycle).
- `timing.jitter.enabled` *(bool, optional)*: Toggle per-transition duration randomization.
- `timing.jitter.factor_min` / `factor_max` *(float, optional)*: Multiplicative range applied to the base duration (e.g., `0.5 ... 2.0`).
- `tags`, `image` *(optional)*: UI/use-case metadata.

### Runtime State (Ephemeral)

```json
{
  "active_playlist": "evening-cycle",
  "index": 1,
  "order": [0, 2, 1],
  "scenes": ["warm-fade", "calm-amber", "neon-ripple"],
  "scene_id": "calm-amber",
  "mode": "sequence",
  "paused": false,
  "remaining_ms": 12000,
  "effective_duration_ms": 45000,
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } }
}
```

- `order`: The concrete play order for the current cycle.
- `scenes`: An array of `scene_id` strings in the same order as `order`. This lets clients display the upcoming scenes without remapping indices.
- `remaining_ms`: Time left for the currently active item.
 - `mode`: Effective playback mode for the running session (`"sequence"` or `"shuffle"). If a runtime `mode` override was provided at start, that value is returned here; otherwise the stored playlist `mode` is shown.

---

## Endpoints Summary

| Method | Path                          | Purpose                                |
|-------:|-------------------------------|----------------------------------------|
|  POST  | `/api/playlists`              | Create or replace (upsert) a playlist  |
|   PUT  | `/api/playlists`              | Control/mutate an existing playlist    |
| DELETE | `/api/playlists`              | Delete a playlist                      |
|   GET  | `/api/playlists`              | List all playlists                     |
|   GET  | `/api/playlists/{id}`         | Get playlist details                   |


**Conventions**
- `Content-Type: application/json` for request bodies.
- Responses are snackbar-friendly and follow LedFx standard format:
  - Success: `{"status":"success", ...}` or with snackbar: `{"status":"success", "payload":{"type":"success", "reason":"message"}}`
  - Error: `{"status":"failed", "payload":{"type":"error", "reason":"message"}}`
- Status codes: `200 OK` for all responses (to ensure snackbar functionality works).

---

## POST `/api/playlists` - Create/Replace (Upsert)

Creates a new playlist or replaces an existing one with the same `id`.

### Request Body

```json
{
  "id": "evening-cycle",                   // optional; generated from "name" if omitted
  "name": "Evening Cycle",
  "items": [
    { "scene_id": "warm-fade",   "duration_ms": 30000 },
    { "scene_id": "neon-ripple", "duration_ms": 45000 },
    { "scene_id": "calm-amber" }
  ],
  "default_duration_ms": 30000,
  "mode": "sequence",
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } },
  "tags": ["ambient", "night"],
  "image": null
}
```

### Validation Rules
- `name`: required
- `items`: non-empty array, each with `scene_id` present.
- `duration_ms` and `default_duration_ms`: integers - **500** ms recommended minimum.

### Responses

**200 OK**
```json
{
  "status": "success",
  "playlist": { /* saved playlist */ }
}
```

**200 OK (Error)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Validation failed: items must be non-empty; item[2].scene_id is required"
  }
}
```

---

## PUT `/api/playlists` — Control / Mutate

Action-based controller for playlists. Actions are divided into two categories:

### Playlist Selection Actions (require `id`)

These actions need to specify which playlist to operate on:

```json
{ "id": "evening-cycle", "action": "start" }
```

- `start` — Starts the specified playlist; stops any currently active playlist first.

You may optionally include a `mode` field with the `start` action to temporarily override the playlist's configured playback mode for this run only. The allowed values are `"sequence"` or `"shuffle"`. This override does not persist to the stored playlist — it only affects order generation for the started session.

```json
{ "id": "evening-cycle", "action": "start", "mode": "shuffle" }
```

- `start` — Starts the specified playlist; stops any currently active playlist first. Optionally accepts `mode: "sequence"|"shuffle"` to override the playlist's stored mode for the runtime session.

You may also pass a `timing` object with the `start` action to temporarily override timing settings for the running session. The timing object follows the same shape as the playlist `timing` field (for example, enabling jitter and setting factor_min/factor_max). The runtime timing override is applied only for the active session and is not persisted to the stored playlist.

```json
{ "id": "evening-cycle", "action": "start", "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 1.5 } } }
```

You can also explicitly disable jitter at start (overrides stored playlist timing):

Pass an empty timing object to clear/override timing (no jitter):

```json
{ "id": "evening-cycle", "action": "start", "timing": {} }
```

- `start` — Starts the specified playlist; stops any currently active playlist first. Optionally accepts `mode: "sequence"|"shuffle"` and `timing: { ... }` to override the playlist's stored mode/timing for the runtime session.

### Active Playlist Controls (no `id` required)

These actions operate on the currently active playlist and don't require an `id`:

```json
{ "action": "stop" }
```

- `stop` — Stops the currently active playlist and clears active state.
- `pause` — Pauses the currently active playlist.
- `resume` — Resumes the currently paused playlist.
- `next` — Immediately advances to next item in the active playlist.
- `prev` — Goes to previous item in the active playlist.
- `state` — Returns the runtime state of the active playlist.

---

## DELETE `/api/playlists` — Delete

Stops the playlist if active, then deletes it.

### Body
```json
{ "id": "evening-cycle" }
```

### Responses
**200 OK (success)** — playlist deleted.
**200 OK (failed)** — playlist not found error envelope.

---

## GET `/api/playlists` — List

**200 OK**
```json
{ "playlists": [ { "id": "evening-cycle", "name": "Evening Cycle", "items": [] } ] }
```

---

## GET `/api/playlists/{id}` — Details

**200 OK**
```json
{ "playlist": { "id": "evening-cycle", "name": "Evening Cycle", "items": [] } }
```

**200 OK (failed)** — playlist not found envelope.

---

## Examples (cURL)

**Create / replace**
```bash
curl -X POST http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{
    "id":"evening-cycle",
    "name":"Evening Cycle",
    "items":[
      { "scene_id":"warm-fade",   "duration_ms":30000 },
      { "scene_id":"neon-ripple", "duration_ms":45000 },
      { "scene_id":"calm-amber" }
    ],
    "default_duration_ms":30000,
    "mode":"sequence"
  }'
```

**Start playlist**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"start" }'
```

**Start playlist with runtime-only mode override (shuffle)**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"start", "mode":"shuffle" }'
```

**Bump to next (bypass timeout)**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "action":"next" }'
```

**Pause active playlist**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "action":"pause" }'
```

**Resume active playlist**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "action":"resume" }'
```

**Stop active playlist**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "action":"stop" }'
```

---

## Validation (Voluptuous sketch)

```python
TimingJitter = vol.Schema({
    vol.Required("enabled"): bool,
    vol.Optional("factor_min", default=1.0): vol.All(float, vol.Range(min=0.0)),
    vol.Optional("factor_max", default=1.0): vol.All(float, vol.Range(min=0.0)),
})

PlaylistTiming = vol.Schema({
    vol.Optional("jitter"): TimingJitter
})

PlaylistItem = vol.Schema({
    vol.Required("scene_id"): str,
    vol.Optional("duration_ms"): vol.All(int, vol.Range(min=500)),
})

PlaylistMode = vol.Schema(vol.In(["sequence", "shuffle"]))

PlaylistSchema = vol.Schema({
  vol.Required("id"): str,
  vol.Required("name"): str,
  vol.Required("items"): [PlaylistItem],
  vol.Optional("default_duration_ms"): vol.All(int, vol.Range(min=500)),
  vol.Optional("mode", default="sequence"): PlaylistMode,
  vol.Optional("timing"): PlaylistTiming,
  vol.Optional("tags", default=list): [str],
  vol.Optional("image"): vol.Any(str, None),
})
```

---

## Implementation Notes

- **Single active playlist** at a time simplifies UX and scheduling; starting a new one implicitly stops any active playlist.
- **Timer scheduling:** the implementation uses an asyncio task to activate scenes and sleep the appropriate duration; durations are computed from `item.duration_ms` or `default_duration_ms` and subject to a minimum.
- **Shuffle behavior:** The runtime supports sequence and simple shuffle modes.
- **Error handling:**
  - Empty `items` → `start` is rejected with an error response.
  - Missing `scene_id` in items → the implementation either skips invalid items or fails validation at upsert time depending on validation rules.
  - Scene activation exceptions are logged and the runner will advance to avoid deadlocks when configured to be resilient.
- **Events (names/payloads):**
  - `playlist_started` — payload: `{ "playlist_id": "<id>", "index": <int> }`
  - `playlist_advanced` — payload: `{ "playlist_id": "<id>", "index": <int> }`
  - `playlist_paused` — payload: `{ "playlist_id": "<id>", "index": <int> }`
  - `playlist_resumed` — payload: `{ "playlist_id": "<id>", "index": <int> }`
  - `playlist_stopped` — payload: `{ "playlist_id": "<id>" }`

## Events

The backend fires simple events to notify about playlist lifecycle changes. These are emitted on the server's internal event bus and are also available to any integrations or UI listeners that subscribe to runtime events.

Each event includes a small JSON payload. Here are the supported events, when they are emitted, and their payload shapes:

- **playlist_started**
  - When: emitted immediately after a playlist is started (via API or programmatic start).
  - Payload:
    ```json
    { "playlist_id": "evening-cycle", "index": 0, "scene_id": "warm-fade", "effective_duration_ms": 30000 }
    ```
  - Notes: `index` is the concrete position within the current play order and `scene_id` is the scene activated at that index (if available).

- **playlist_advanced**
  - When: emitted each time the playlist advances to a new item (auto-advance or after a `next`/`prev`).
  - Payload:
    ```json
    { "playlist_id": "evening-cycle", "index": 1, "scene_id": "calm-amber", "effective_duration_ms": 45000 }
    ```

- **playlist_paused**
  - When: emitted when playback is paused.
  - Payload:
    ```json
    { "playlist_id": "evening-cycle", "index": 1, "scene_id": "calm-amber", "effective_duration_ms": 45000, "remaining_ms": 12000 }
    ```
  - Notes: the runtime will also store `remaining_ms` for the current item so callers can resume from the same point. The `playlist_paused` event includes the `remaining_ms` value.

- **playlist_resumed**
  - When: emitted when playback is resumed after a pause.
  - Payload:
    ```json
    { "playlist_id": "evening-cycle", "index": 1, "scene_id": "calm-amber", "effective_duration_ms": 45000, "remaining_ms": 12000 }
    ```

- **playlist_stopped**
  - When: emitted when a playlist is stopped (either explicitly or because another playlist was started).
  - Payload:
    ```json
    { "playlist_id": "evening-cycle", "effective_duration_ms": 45000, "remaining_ms": 12000 }
    ```

- **Timing jitter (if enabled):**
  - On each new item start (start/next/prev/auto-advance), sample a factor uniformly in `[factor_min, factor_max]` and apply it to the base duration; clamp to a sane minimum (e.g., 500ms).
  - Resuming from pause uses stored `remaining_ms` and does not re-sample.