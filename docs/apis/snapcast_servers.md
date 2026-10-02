# Snapcast Servers API

## Overview

LedFx provides REST API endpoints for managing Snapcast server connections. [Snapcast](https://github.com/badaix/snapcast) is a synchronous multi-room audio player; LedFx connects to a snapserver as a regular client to receive audio for visualization. See [Snapcast Audio Streaming](/settings/snapcast.md) for the user-facing guide.

**Base URL:** `http://<host>:<port>/api/snapcast/servers`

**Availability:** The Snapcast client is implemented in pure Python and is always available. `GET /api/info` reports `"snapcast": true` in `features`.

Each configured server appears in the audio device list (`GET /api/audio/devices`) as `SNAPCAST: <id>`. Adding, updating or removing a server fires the `audio_device_list_changed` event when the list changes.

---

## Data Model

### Server Object

```json
{
  "host": "192.168.1.20",
  "port": 1704,
  "client_name": "LedFx"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes (create only; URL param for update/delete) | — | Unique server identifier. Converted to a URL-safe slug and used as the key in `config.json`. |
| `host` | string | Yes | — | Hostname or IP address of the snapserver. Not a URL. |
| `port` | integer | No | `1704` | Snapserver stream port (1–65535). |
| `client_name` | string | No | `"LedFx"` | Name LedFx shows up as in the snapserver's client list. |

---

## Endpoints

### List All Servers

**`GET /api/snapcast/servers`**

```json
{
  "servers": {
    "living-room": {
      "host": "192.168.1.20",
      "port": 1704,
      "client_name": "LedFx"
    }
  }
}
```

### Add Server

**`POST /api/snapcast/servers`**

```json
{
  "id": "living-room",
  "host": "192.168.1.20",
  "port": 1704,
  "client_name": "Living Room LEDs"
}
```

**Success Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Snapcast server 'living-room' added."
  }
}
```

**Error Responses** (`"status": "failed"`, reason in `payload.reason`):

- `Required key not provided: 'id'` / `'host'`
- `Server '<id>' already exists. Use PUT to update.`
- An invalid `host`, `port` or `client_name`, with the reason

### Update Server

**`PUT /api/snapcast/servers/{id}`**

Send only the fields to change:

```json
{
  "port": 1705
}
```

If the server is the active audio source and the settings changed, the stream reconnects with the new settings.

### Delete Server

**`DELETE /api/snapcast/servers/{id}`**

If the server is the active audio source, the stream is stopped. The audio device setting is left unchanged, and LedFx reports an `audio_source_error` event instead of falling back to a different audio device.

---

## Global Setting

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `snapcast_always_on` | boolean | `true` | Keep the Snapcast connection open while a Snapcast source is selected, even when no audio-reactive effect is running. Set through `PUT /api/config`. |

## Audio Source Errors

Snapcast problems are reported through the `audio_source_error` websocket event:

| `error_type` | Meaning |
|--------------|---------|
| `snapcast_device_not_found` | The selected Snapcast server is no longer configured |
| `snapcast_device_unavailable` | The selected Snapcast server could not be opened |
| `snapcast_codec_unsupported` | The snapserver stream uses a codec LedFx cannot decode (ogg, opus) |
| `snapcast_codec_unavailable` | The stream uses FLAC but pyFLAC is not installed |
| `snapcast_codec_invalid` | The snapserver sent a stream header LedFx could not read |
