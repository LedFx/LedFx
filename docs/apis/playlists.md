# Playlists API

---

> ## ⚠️ **PROPOSAL ONLY - NOT IMPLEMENTED** ⚠️
> 
> **This API has not yet been implemented and is a proposal only.**
> 
> This documentation describes the planned design for a future Playlists feature. The endpoints and functionality described here are not currently available in LedFx.
> 
> **Do not attempt to use these endpoints - they will not work YET**

---

> **Scope:** This document defines the *Playlists* REST API only. It assumes Scenes already exist and are addressable by `scene_id`.
> **Base URL:** `http://<host>:<port>/api/playlists`

---

## Overview

A **Playlist** is an ordered collection of **scene references** (by `scene_id`) with per-item (or default) durations. When started, the backend activates each scene in sequence (or randomized order) and schedules the next activation after its duration. A single playlist may be active at a time.

**Core capabilities:**
- Create, replace, delete any number of playlists
- Start/stop/pause/resume playback
- Shuffle (random) order and sequential playback
- Per-item durations and a default duration
- Immediate **bump** (`next`) to the next scene (bypassing timeout)
- Randomized order per cycle while ensuring each item plays once per cycle
- Seek to arbitrary index and previous/next navigation

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
  "mode": {
    "order": "sequence"   // "sequence" | "shuffle"
  },
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
- `default_duration_ms` *(int, optional)*: Used when an item omits `duration_ms`. If both are absent, use server default (e.g., 30000ms).
- `mode.order` *(string)*: `"sequence"` (in order) or `"shuffle"` (randomized once per cycle).
- `timing.jitter.enabled` *(bool, optional)*: Toggle per-transition duration randomization.
- `timing.jitter.factor_min` / `factor_max` *(float, optional)*: Multiplicative range applied to the base duration (e.g., `0.5 … 2.0`).
- `tags`, `image` *(optional)*: UI/use-case metadata.

### Runtime State (Ephemeral)

```json
{
  "active_id": "evening-cycle",
  "index": 1,
  "order": [0, 2, 1],
  "scene_id": "calm-amber",
  "paused": false,
  "remaining_ms": 12000,
  "effective_duration_ms": 45000,
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } }
}
```

- `order`: The concrete play order for the current cycle.
- `remaining_ms`: Time left for the currently active item.

---

## Endpoints Summary

| Method | Path                          | Purpose                                |
|-------:|-------------------------------|----------------------------------------|
|  POST  | `/api/playlists`              | Create or replace (upsert) a playlist  |
|   PUT  | `/api/playlists`              | Control/mutate an existing playlist    |
| DELETE | `/api/playlists`              | Delete a playlist                      |
|   GET  | `/api/playlists`              | List all playlists                     |
|   GET  | `/api/playlists/{id}`         | Get playlist details                   |
|   GET  | `/api/playlists/active`       | Get active playlist state              |

**Conventions**
- `Content-Type: application/json` for request bodies.
- Responses are snackbar-friendly and follow LedFx standard format:
  - Success: `{"status":"success", ...}` or with snackbar: `{"status":"success", "payload":{"type":"success", "reason":"message"}}`
  - Error: `{"status":"failed", "payload":{"type":"error", "reason":"message"}}`
- Status codes: `200 OK` for all responses (to ensure snackbar functionality works).

---

## POST `/api/playlists` — Create/Replace (Upsert)

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
  "mode": { "order": "sequence" },
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } },
  "tags": ["ambient", "night"],
  "image": null
}
```

### Validation Rules
- `name`: required if `id` is omitted.
- `items`: non-empty array, each with `scene_id` present.
- `duration_ms` and `default_duration_ms`: integers ≥ **500** ms recommended minimum.

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

Action-based controller for playlists. All actions require an `id` and an `action` string.

### Common Envelope

```json
{ "id": "evening-cycle", "action": "<...>" }
```

### Actions

#### 1) `start`
Starts playback. If another playlist is active, it is stopped first.

**Body**
```json
{ "id": "evening-cycle", "action": "start", "index": 0 }
```
- `index` *(optional, int)*: Start at this 0-based index (default 0).

**Behavior**
- Resolve `order` = sequential indices or a single-cycle shuffle.
- Activate `items[index]` scene immediately.
- Schedule automatic advance after resolved duration.

**200 OK**
```json
{
  "status": "success",
  "message": "Playlist 'evening-cycle' started at index 0.",
  "state": {
    "active_id": "evening-cycle",
    "index": 0,
    "order": [0,1,2],
    "scene_id": "warm-fade",
    "paused": false,
    "remaining_ms": 30000
  }
}
```

#### 2) `stop`
Stops playback and clears active state.

**Body**
```json
{ "id": "evening-cycle", "action": "stop" }
```

**200 OK**
```json
{ "status": "success", "message": "Playlist 'evening-cycle' stopped." }
```

#### 3) `pause`
Pauses the current timer; records `remaining_ms`.

```json
{ "id": "evening-cycle", "action": "pause" }
```

**200 OK**
```json
{
  "status": "success",
  "message": "Paused playlist 'evening-cycle'.",
  "state": { "paused": true, "remaining_ms": 12000 }
}
```

#### 4) `resume`
Resumes playback using `remaining_ms`.

```json
{ "id": "evening-cycle", "action": "resume" }
```

**200 OK**
```json
{
  "status": "success",
  "message": "Resumed playlist 'evening-cycle'.",
  "state": { "paused": false, "remaining_ms": 12000 }
}
```

#### 5) `next` (**bump**)
Immediately advance to the next item (wraps if needed), bypassing the timeout.

```json
{ "id": "evening-cycle", "action": "next" }
```

**200 OK**
```json
{
  "status": "success",
  "message": "Advanced to 'neon-ripple' (2/3).",
  "state": { "index": 1, "scene_id": "neon-ripple", "remaining_ms": 45000 }
}
```

#### 6) `prev`
Go to previous item (wraps if needed).

```json
{ "id": "evening-cycle", "action": "prev" }
```

**200 OK**
```json
{
  "status": "success",
  "message": "Moved to previous item 'calm-amber' (3/3).",
  "state": { "index": 2, "scene_id": "calm-amber", "remaining_ms": 30000 }
}
```

#### 7) `seek`
Jump to a specific index (0-based).

```json
{ "id": "evening-cycle", "action": "seek", "index": 2 }
```

**200 OK**
```json
{
  "status": "success",
  "message": "Seeked to index 2 ('calm-amber').",
  "state": { "index": 2, "scene_id": "calm-amber", "remaining_ms": 30000 }
}
```

#### 8) `set_mode`
Update playback mode in-place.

```json
{
  "id":"evening-cycle",
  "action":"set_mode",
  "mode": { "order":"shuffle" }
}
```

**200 OK**
```json
{ "status":"success", "message":"Mode updated to shuffle." }
```

#### 9) `shuffle_on` / `shuffle_off`
Sugar for toggling `mode.order` without specifying the whole object.

```json
{ "id":"evening-cycle", "action":"shuffle_on" }
```
```json
{ "id":"evening-cycle", "action":"shuffle_off" }
```

**200 OK**
```json
{ "status":"success", "message":"Shuffle enabled." }
```
```json
{ "status":"success", "message":"Shuffle disabled (sequence order)." }
```

#### 10) `rename`
Rename the playlist.

```json
{ "id":"evening-cycle", "action":"rename", "name":"Evening Cycle V2" }
```

**200 OK**
```json
{ "status":"success", "message":"Playlist renamed to 'Evening Cycle V2'." }
```

#### 11) `replace_items`
Atomically replace the entire `items` list.

```json
{
  "id":"evening-cycle",
  "action":"replace_items",
  "items":[
    { "scene_id": "blue-waves", "duration_ms": 20000 },
    { "scene_id": "golden-hour", "duration_ms": 40000 }
  ],
  "default_duration_ms": 25000
}
```

**200 OK**
```json
{ "status":"success", "message":"Items replaced (2 total)." }
```

#### 12) `set_timing`
Update the timing configuration, including jitter.

```json
{
  "id":"evening-cycle",
  "action":"set_timing",
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } }
}
```

**200 OK**
```json
{
  "status":"success",
  "message":"Timing updated (jitter enabled, range 0.5–2.0×).",
  "timing": { "jitter": { "enabled": true, "factor_min": 0.5, "factor_max": 2.0 } }
}
```

---

## DELETE `/api/playlists` — Delete

Stops the playlist if active, then deletes it.

### Body
```json
{ "id": "evening-cycle" }
```

### Responses
**200 OK**
```json
{ "status": "success", "message": "Playlist 'evening-cycle' deleted." }
```

**200 OK (Error)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Playlist not found"
  }
}
```

---

## GET `/api/playlists` — List

**200 OK**
```
{ "playlists": [ { /* playlist */ }, ... ] }
```

---

## GET `/api/playlists/{id}` — Details

**200 OK**
```
{ "playlist": { /* playlist object */ } }
```

**200 OK (Error)**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Playlist not found"
  }
}
```

---

## GET `/api/playlists/active` — Active State

**200 OK**
```json
{
  "state": {
    "active_id": "evening-cycle",
    "index": 1,
    "order": [0,2,1],
    "scene_id": "calm-amber",
    "paused": false,
    "remaining_ms": 12000
  }
}
```

**200 OK (no active playlist)**
```json
{ "state": null }
```

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
    "mode":{ "order":"sequence" }
  }'
```

**Start playbook**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"start" }'
```

**Bump to next (bypass timeout)**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"next" }'
```

**Enable shuffle**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"set_mode", "mode": { "order":"shuffle" } }'
```

**Stop**
```bash
curl -X PUT http://localhost:8888/api/playlists \
  -H "Content-Type: application/json" \
  -d '{ "id":"evening-cycle", "action":"stop" }'
```

---

## Validation (Voluptuous Sketch)

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

PlaylistMode = vol.Schema({
    vol.Required("order"): vol.In(["sequence", "shuffle"]),
})

PlaylistSchema = vol.Schema({
    vol.Required("id"): str,
    vol.Required("name"): str,
    vol.Required("items"): [PlaylistItem],
    vol.Optional("default_duration_ms"): vol.All(int, vol.Range(min=500)),
    vol.Optional("mode", default={"order":"sequence"}): PlaylistMode,
    vol.Optional("timing"): PlaylistTiming,
    vol.Optional("tags", default=list): [str],
    vol.Optional("image"): vol.Any(str, None),
})
```

---

## Implementation Notes

- **Single active playlist** at a time simplifies UX and scheduling; starting a new one implicitly stops any active playlist.
- **Timer scheduling:** use event loop (e.g., `loop.call_later`); compute `duration = item.duration_ms ?? playlist.default_duration_ms ?? 30000`.
- **Shuffle behavior:** compute a permutation once per cycle; on loop wrap and shuffle mode, recompute a new permutation.
- **Error handling:**
  - Empty `items` → reject `start` with error response.
  - Missing `scene_id` in scenes → either skip with warning and advance, or return error response (team decision; doc recommends "skip and notify").
  - Scene activation exceptions → log; advance to next to avoid deadlocks if configured to be resilient.
- **Events (recommended):**
  - `PlaylistStartedEvent(playlist_id)`
  - `PlaylistAdvancedEvent(playlist_id, index, scene_id)`
  - `PlaylistPausedEvent(playlist_id)` / `PlaylistResumedEvent(playlist_id)`
  - `PlaylistStoppedEvent(playlist_id)`
  - `PlaylistDeletedEvent(playlist_id)`
- **Timing jitter (if enabled):**
  - On each new item start (start/next/prev/seek/auto-advance), sample a factor uniformly in `[factor_min, factor_max]` and apply it to the base duration; clamp to a sane minimum (e.g., 500ms).
  - Resuming from pause uses stored `remaining_ms` and does not re-sample.

---