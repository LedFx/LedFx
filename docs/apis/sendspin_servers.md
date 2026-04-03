# Sendspin Servers API

## Overview

LedFx provides REST API endpoints for managing Sendspin server connections. [Sendspin](https://sendspin.com) is a synchronized multi-room audio system; LedFx can connect to a Sendspin server as a client to receive audio for real-time visualization effects.

**Base URL:** `http://<host>:<port>/api/sendspin/servers`

**Availability:** Requires Python 3.12+ and the `aiosendspin` package installed. On Python < 3.12 or without the package, all endpoints return a `501 Not Implemented` equivalent response.

---

## Data Model

### Server Object

```json
{
  "id": "living-room",
  "server_url": "ws://192.168.1.12:8927/sendspin",
  "client_name": "LedFx"
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes (URL param for update/delete) | — | Unique server identifier. URL-safe slug; used as the key in `config.json`. |
| `server_url` | string | Yes | `ws://192.168.1.12:8927/sendspin` | WebSocket URL of the Sendspin server. Must start with `ws://` or `wss://`. |
| `client_name` | string | No | `"LedFx"` | Name this client announces to the Sendspin server. |

---

## Endpoints

### List All Servers

Returns all configured Sendspin servers.

**`GET /api/sendspin/servers`**

**Success Response:**
```json
{
  "servers": {
    "living-room": {
      "server_url": "ws://192.168.1.12:8927/sendspin",
      "client_name": "LedFx"
    },
    "office": {
      "server_url": "ws://192.168.1.55:8927/sendspin",
      "client_name": "LedFx-Office"
    }
  }
}
```

**When no servers are configured:**
```json
{
  "servers": {}
}
```

**Sendspin unavailable (Python < 3.12 or missing package):**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
  }
}
```

---

### Add Server

Creates a new Sendspin server configuration and hot-reloads it into the audio system.

**`POST /api/sendspin/servers`**

**Request Body:**
```json
{
  "id": "living-room",
  "server_url": "ws://192.168.1.12:8927/sendspin",
  "client_name": "LedFx"
}
```

> Only `id` and `server_url` are required. All other fields take defaults when omitted.

**Success Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Sendspin server 'living-room' added."
  }
}
```

**Validation Errors:**

Missing required field:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Required key not provided: 'server_url'"
  }
}
```

Duplicate server ID:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Server 'living-room' already exists. Use PUT to update."
  }
}
```

Invalid URL scheme:
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "server_url must start with ws:// or wss://"
  }
}
```

---

### Update Server

Updates an existing Sendspin server configuration and hot-reloads the change.

**`PUT /api/sendspin/servers/{id}`**

**URL Parameter:** `id` — The server identifier to update.

**Request Body:** Any subset of server fields to change. Fields not provided retain their current values.

```json
{
  "server_url": "ws://192.168.1.20:8927/sendspin",
  "client_name": "LedFx-Updated"
}
```

**Success Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Sendspin server 'living-room' updated."
  }
}
```

**Server not found:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Server 'living-room' not found."
  }
}
```

---

### Delete Server

Removes a Sendspin server configuration and removes it from the active audio system.

**`DELETE /api/sendspin/servers/{id}`**

**URL Parameter:** `id` — The server identifier to delete.

**Success Response:**
```json
{
  "status": "success",
  "payload": {
    "type": "success",
    "reason": "Sendspin server 'living-room' removed."
  }
}
```

**Server not found:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "Server 'living-room' not found."
  }
}
```

---

### Discover Servers

Scans the local network for Sendspin servers using mDNS/DNS-SD and returns any found. Does **not** automatically add discovered servers — the frontend should present results and let the user add desired servers via `POST /api/sendspin/servers`.

**`GET /api/sendspin/discover`**

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | float | `3.0` | Discovery scan duration in seconds. Max `30.0`. |

**Example:**
```
GET /api/sendspin/discover?timeout=5.0
```

**Success Response — servers found:**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "Discovery complete. 2 server(s) found."
  },
  "data": {
    "servers": [
      {
        "name": "Sendspin Living Room",
        "server_url": "ws://192.168.1.12:8927/sendspin",
        "host": "192.168.1.12",
        "port": 8927,
        "already_configured": false
      },
      {
        "name": "Sendspin Office",
        "server_url": "ws://192.168.1.55:8927/sendspin",
        "host": "192.168.1.55",
        "port": 8927,
        "already_configured": true
      }
    ]
  }
}
```

**Success Response — no servers found:**
```json
{
  "status": "success",
  "payload": {
    "type": "info",
    "reason": "Discovery complete. No Sendspin servers found on the local network."
  },
  "data": {
    "servers": []
  }
}
```

**Timeout out of range:**
```json
{
  "status": "failed",
  "payload": {
    "type": "error",
    "reason": "timeout must be between 0.1 and 30.0 seconds"
  }
}
```

**Discovery fields:**

| Field | Description |
|-------|-------------|
| `name` | Human-readable server name announced via mDNS |
| `server_url` | Fully formed WebSocket URL ready to use in `POST /api/sendspin/servers` |
| `host` | IP address or hostname of the discovered server |
| `port` | TCP port (default: `8927`) |
| `already_configured` | `true` if a server with this `server_url` is already in `config.json` |

---

## Hot-Reload Behaviour

All mutating operations (`POST`, `PUT`, `DELETE`) immediately update the in-memory `SENDSPIN_SERVERS` dict used by the audio system **without requiring a restart**. Specifically:

1. The `config.json` `sendspin_servers` key is written.
2. `SENDSPIN_SERVERS` (from `ledfx.effects.audio`) is updated in-place.
3. If the currently active audio source is `SENDSPIN {id}`, changing or removing that server causes the audio system to fall back to the default audio device.

> **Note:** A server appearing in `SENDSPIN_SERVERS` does **not** mean LedFx is actively streaming from it. The connection is only established when the user selects that server as the active audio input device (via `PUT /api/config` with `audio_device = "SENDSPIN living-room"`).

---

## Config Storage

Servers are persisted in `config.json` under the `sendspin_servers` key:

```json
{
  "sendspin_servers": {
    "living-room": {
      "server_url": "ws://192.168.1.12:8927/sendspin",
      "client_name": "LedFx"
    },
    "office": {
      "server_url": "ws://192.168.1.55:8927/sendspin",
      "client_name": "LedFx-Office"
    }
  }
}
```

---

## File Layout

Following the one-class-per-file rule for REST endpoints:

| File | Class | Handles |
|------|-------|---------|
| `ledfx/api/sendspin_servers.py` | `SendspinServersEndpoint` | `GET`, `POST` on `/api/sendspin/servers` |
| `ledfx/api/sendspin_server.py` | `SendspinServerEndpoint` | `PUT`, `DELETE` on `/api/sendspin/servers/{id}` |
| `ledfx/api/sendspin_discover.py` | `SendspinDiscoverEndpoint` | `GET` on `/api/sendspin/discover` |

---

## Usage Examples

### Add a server manually

```bash
curl -X POST http://localhost:8888/api/sendspin/servers \
  -H "Content-Type: application/json" \
  -d '{"id": "living-room", "server_url": "ws://192.168.1.12:8927/sendspin"}'
```

### Auto-discover and add the first found server

```bash
# Discover
curl http://localhost:8888/api/sendspin/discover?timeout=5.0

# Add the discovered server
curl -X POST http://localhost:8888/api/sendspin/servers \
  -H "Content-Type: application/json" \
  -d '{"id": "my-server", "server_url": "ws://192.168.1.12:8927/sendspin"}'
```

### Update a server URL

```bash
curl -X PUT http://localhost:8888/api/sendspin/servers/living-room \
  -H "Content-Type: application/json" \
  -d '{"server_url": "ws://192.168.1.20:8927/sendspin"}'
```

### Remove a server

```bash
curl -X DELETE http://localhost:8888/api/sendspin/servers/living-room
```
