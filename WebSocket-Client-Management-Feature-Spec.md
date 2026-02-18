# WebSocket Client Management Enhancement - Feature Specification

**Status:** Draft for Discussion
**Target Release:** TBD
**Author:** LedFx Core Team
**Date:** 2026-02-17

---

## Overview

This document outlines the enhancement of LedFx's WebSocket connection system to support persistent client metadata tracking and client-to-client messaging capabilities. These features enable richer multi-client experiences, better observability of connected clients, and coordinated interactions between frontend instances, mobile apps, and API clients.

---

## Motivation

### Current Limitations

1. **No Client Identification** - We track connections by IP/UUID but have no persistent identity or metadata
2. **Limited Client Visibility** - No way to see what types of clients are connected (web UI, mobile app, API client, etc.)
3. **No Client-to-Client Communication** - Clients cannot coordinate or share state with each other
4. **Poor Observability** - Difficult to debug multi-client scenarios or understand connection history

### Benefits of Enhancement

- **Multi-Device Coordination** - Mobile apps can sync state with web UI, displays can receive commands from controllers
- **Better UX** - Show users what other devices are connected, enable collaborative features
- **Debugging/Monitoring** - See client connection history, identify problem clients, monitor activity
- **Extensibility** - Foundation for features like shared presets, collaborative editing, remote control

---

## WebSocket-Centric Architecture (v1)

**Design Philosophy:** This feature enhancement is built on LedFx's WebSocket-first architecture. All client-to-client broadcasting in v1 originates from WebSocket connections.

**Why WebSocket-Originated Broadcasts:**

1. **Verified Sender Identity** - Sender UUID is derived directly from the authenticated WebSocket connection, eliminating spoofing risks
2. **Architectural Consistency** - Matches LedFx's existing event-driven, real-time communication model
3. **Simplified Authentication** - No additional REST authentication layer needed; WebSocket connections are already authenticated
4. **Bidirectional Communication** - Clients can send broadcasts and receive responses over the same connection

**REST Broadcast Endpoint (Future):**

A REST broadcast endpoint (`POST /api/clients`) is **NOT implemented in v1**. 

**v1 Scope:** WebSocket-only broadcasts. REST endpoint deferred to future release.

**Future REST Implementation Requirements:**
When REST broadcasts are added in a future release, they MUST:
- Be restricted to localhost (127.0.0.1, ::1) by default
- Require explicit `allow_remote_broadcast: true` configuration to enable remote access
- Use a special "system" sender identity for unauthenticated requests

---

## Feature Requirements

### Feature 1: Persistent Client Metadata

#### Description
Each WebSocket connection should maintain a persistent identity with metadata that survives the duration of the connection.

#### Metadata Fields

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `uuid` | String | Unique connection identifier | Auto-generated (existing) |
| `device_id` | String (optional) | Persistent device identifier | Client-provided |
| `name` | String | Human-readable client name | Client-provided or auto-generated |
| `type` | String (enum) | Client category | Client-provided with validation |
| `ip` | String | Client IP address | Auto-detected (existing) |
| `connected_at` | Timestamp | Initial connection time | Auto-generated |
| `last_active` | Timestamp | Last message received | Auto-updated |

#### Client Types (Enumeration)

- `controller` - Web UI or primary control interface
- `visualiser` - Display-only client (e.g., fullscreen visualization)
- `mobile` - Mobile app client
- `display` - Dedicated display device (e.g., Raspberry Pi kiosk)
- `api` - Programmatic API client
- `unknown` - Fallback for unspecified clients

#### Client Name Requirements

- **Uniqueness**: Client names must be unique across all connected clients
- **Conflict Resolution**: If a requested name is already taken, automatically append a counter: `"MyClient"` → `"MyClient (1)"` → `"MyClient (2)"`
- **Auto-generation**: If no name provided, generate: `"Client-{first-8-chars-of-uuid}"`
- **Persistence**: Name persists for the duration of the connection only
- **Updates**: Clients can request name changes after connection (subject to uniqueness check)

#### API Surface

**WebSocket Messages (Client → Server):**

```javascript
// Initial metadata setup (typically sent immediately after connection)
{
  type: "set_client_info",
  device_id: "abc123-device-uuid",  // optional, for recognizing returning devices
  name: "Living Room Display",      // optional, will auto-generate if missing
  client_type: "display"            // optional, defaults to "unknown"
}

// Update metadata while connected
{
  type: "update_client_info",
  name: "Bedroom Display",          // optional, update name only
  client_type: "visualiser"         // optional, update type only
}
```

**WebSocket Messages (Server → Client):**

```javascript
// Confirmation after metadata set/update
{
  event_type: "client_info_updated",
  client_id: "uuid-of-this-client",
  name: "Living Room Display",      // final name (may differ if conflict)
  type: "display",
  name_conflict: false              // true if name was auto-modified
}

// Error response
{
  event_type: "error",
  message: "Name already in use",
  id: "original-message-id"
}
```

**REST API:**

```http
# Backward compatible: Returns simple IP map (existing behavior)
GET /api/clients

# Enhanced: Returns full metadata objects
GET /api/clients?detailed=true
```

**Response (default, backward compatible):**
```json
{
  "client-uuid-1": "192.168.1.100",
  "client-uuid-2": "192.168.1.101"
}
```

**Response (detailed=true):**
```json
{
  "client-uuid-1": {
    "ip": "192.168.1.100",
    "device_id": "abc123-device-uuid",
    "name": "Living Room Display",
    "type": "display",
    "connected_at": 1708188000.123,
    "last_active": 1708188100.456
  },
  "client-uuid-2": {
    "ip": "192.168.1.101",
    "device_id": null,
    "name": "Client-e7a3f2d1",
    "type": "unknown",
    "connected_at": 1708188050.789,
    "last_active": 1708188090.234
  }
}
```

#### Event Notifications

**New Event: `ClientsUpdatedEvent`**

Fired when:
- A client connects or disconnects
- A client's metadata changes (name or type update)

Event payload: (no additional data, listeners should query `/api/clients` for current state)

Use cases:
- Frontend displays live client list
- Monitoring systems track connection changes
- Integrations react to new client types appearing

---

### Feature 2: Client-to-Client Broadcasting

#### Description
Enable clients to broadcast messages to other connected clients through the server, with flexible targeting options.

**Security Note:** All broadcasts must use server-derived sender identity to prevent impersonation. See "Sender Identity and Security Model" section below for details.

#### Use Cases

1. **Visualizer Sync** - Controller broadcasts preset change to all visualizer displays
2. **Scene Coordination** - One controller activates a scene that notifies other controllers to update their UI
3. **Color Palette Sharing** - User creates a color palette and broadcasts it to other connected devices
4. **Custom Automation** - API client broadcasts custom commands to specific client types

#### Broadcast Types (Extensible Enum)

- `visualiser_control` - Commands to control visualization displays
- `scene_sync` - Scene activation/state synchronization
- `color_palette` - Color palette sharing
- `custom` - Open-ended custom broadcasts

#### Targeting Modes

| Mode | Description | Configuration |
|------|-------------|---------------|
| `all` | Broadcast to all connected clients | No additional config |
| `type` | Target all clients of a specific type | `value: "display"` |
| `names` | Target specific clients by name | `names: ["Display 1", "Display 2"]` |
| `uuids` | Target specific clients by UUID | `uuids: ["uuid-1", "uuid-2"]` |

#### Request Validation

- **Payload Size Limit**: 2 KB maximum (configurable via constant)
- **Schema Validation**: Voluptuous schema enforcement
- **Target Validation**:
  - Specified UUIDs must exist in connected clients
  - Specified names must exist in connected clients
  - Type value must be a valid client type
  - If no targets match filters, request fails with error

#### Target Specification Validation Rules

**Security Invariant:** Targeting must be explicit. Invalid or ambiguous target specifications fail closed (broadcast rejected, not sent to unintended recipients).

**Common Pitfall:** If `mode="type"` with missing/empty `value`, naive implementations might match clients with `type=None`, causing unintended targeting of all clients without metadata.

**Required Validation:**

1. **Mode: `"all"`**
   - No additional fields required
   - Ignore `value`, `names`, or `uuids` if present
   - Always valid

2. **Mode: `"type"`**
   - **MUST** include `value` field
   - `value` **MUST** be a non-empty string
   - `value` **MUST** be a valid client type from the enum
   - Reject if `value` is missing, empty string, or null
   - **Error**: `"Target mode 'type' requires a non-empty 'value' field"`

3. **Mode: `"names"`**
   - **MUST** include `names` field
   - `names` **MUST** be a non-empty list
   - Each name **MUST** be a non-empty string
   - Reject if `names` is missing, empty list, or contains empty strings
   - **Error**: `"Target mode 'names' requires a non-empty 'names' list"`

4. **Mode: `"uuids"`**
   - **MUST** include `uuids` field
   - `uuids` **MUST** be a non-empty list
   - Each UUID **MUST** be a non-empty string
   - Reject if `uuids` is missing, empty list, or contains empty strings
   - **Error**: `"Target mode 'uuids' requires a non-empty 'uuids' list"`

---

**Example Requests:**

✅ **Valid Requests:**
```javascript
// Mode: all
{ target: { mode: "all" } }

// Mode: type
{ target: { mode: "type", value: "visualiser" } }

// Mode: names
{ target: { mode: "names", names: ["Display 1", "Display 2"] } }

// Mode: uuids
{ target: { mode: "uuids", uuids: ["abc-123", "def-456"] } }
```

❌ **Invalid Requests (Must Reject with 400):**
```javascript
// Missing value for type mode
{ target: { mode: "type" } }
// Error: "Target mode 'type' requires a non-empty 'value' field"

// Empty value for type mode
{ target: { mode: "type", value: "" } }
// Error: "Target mode 'type' requires a non-empty 'value' field"

// Null value for type mode
{ target: { mode: "type", value: null } }
// Error: "Target mode 'type' requires a non-empty 'value' field"

// Missing names for names mode
{ target: { mode: "names" } }
// Error: "Target mode 'names' requires a non-empty 'names' list"

// Empty names list
{ target: { mode: "names", names: [] } }
// Error: "Target mode 'names' requires a non-empty 'names' list"

// Names list with empty string
{ target: { mode: "names", names: ["Display 1", ""] } }
// Error: "Target mode 'names' requires a non-empty 'names' list"

// Missing uuids for uuids mode
{ target: { mode: "uuids" } }
// Error: "Target mode 'uuids' requires a non-empty 'uuids' list"

// Empty uuids list
{ target: { mode: "uuids", uuids: [] } }
// Error: "Target mode 'uuids' requires a non-empty 'uuids' list"
```

---

**Test Cases:**

- ✅ `mode="all"` → broadcasts to all connected clients
- ✅ `mode="type", value="visualiser"` → broadcasts to clients with `type="visualiser"`
- ✅ `mode="type", value="unknown"` → broadcasts to clients with `type="unknown"`
- ❌ `mode="type", value=""` → rejected (400 error)
- ❌ `mode="type", value=null` → rejected (400 error)
- ❌ `mode="type"` (missing value) → rejected (400 error)
- ✅ `mode="type", value="display"` with no matching clients → rejected (no targets matched)
- ✅ `mode="type", value="display"` with client `type=None` → client NOT targeted (explicit type required)
- ✅ `mode="names", names=["Client-1"]` → broadcasts to client named "Client-1"
- ❌ `mode="names", names=[]` → rejected (400 error)
- ❌ `mode="names"` (missing names) → rejected (400 error)
- ✅ `mode="uuids", uuids=["abc-123"]` → broadcasts to client with uuid "abc-123"
- ❌ `mode="uuids", uuids=[]` → rejected (400 error)
- ❌ `mode="uuids"` (missing uuids) → rejected (400 error)

**Client Matching Behavior:**

When `mode="type"`, only clients with explicitly set `type` metadata are considered:
- Client with `type="visualiser"` → matches filter `value="visualiser"`
- Client with `type="unknown"` → matches filter `value="unknown"`
- Client with `type=None` (no metadata set) → does NOT match any type filter
- Client with `type=""` (empty string, shouldn't happen) → does NOT match any type filter

This prevents accidental broadcasts to clients that haven't registered metadata.

#### API Surface

**WebSocket API (v1 Implementation):**

```javascript
// Client sends via WebSocket (sender identity derived from connection)
{
  type: "broadcast",
  broadcast_type: "visualiser_control",
  target: {
    mode: "type",
    value: "display"
  },
  payload: {
    command: "set_brightness",
    value: 80
  }
}
```

**REST API (Optional / Advanced - Not Required for v1 Core UX):**

_Note: REST broadcasts are optional for v1 and should only be implemented if a documented integration use case exists. Most clients (web UI, mobile apps) maintain WebSocket connections and should use the WebSocket broadcast API above._

```http
POST /api/clients
Content-Type: application/json

{
  "action": "broadcast",
  "broadcast_type": "visualiser_control",
  "target": {
    "mode": "type",
    "value": "display"
  },
  "payload": {
    "command": "set_brightness",
    "value": 80
  }
}
```

**Important Notes:**
- No `sender_id` field - server derives sender identity from the request context
- **Any `sender_id` field in the request body is rejected or ignored**
- **v1 Note**: WebSocket broadcasts don't require `allow_remote_broadcast` (only applies to future REST endpoint)
- See "Access Control for Broadcast Endpoints" section for REST endpoint security (future implementation)

**Response:**
```json
{
  "status": "success",
  "broadcast_id": "b-abc123def456",
  "targets_matched": 3,
  "targets": [
    "uuid-display-1",
    "uuid-display-2",
    "uuid-display-3"
  ]
}
```

**Error Response:**
```json
{
  "status": "failed",
  "message": "No targets matched filters",
  "type": "error"
}
```

#### Event Flow

1. Client sends broadcast request (via WebSocket or REST API)
2. Server derives sender identity from authenticated connection (never trusts client-provided sender_id)
3. Server validates schema and payload size
4. Server filters target clients based on targeting mode
5. If no targets match, return error
6. Server fires `ClientBroadcastEvent` with server-derived sender fields
7. Server logs broadcast with audit trail (request_id, sender, targets, type)
8. WebSocket connections subscribed to events receive the broadcast
9. Clients filter by `target_uuids` to determine if message is for them

**Event Payload:**

```javascript
{
  event_type: "client_broadcast",
  broadcast_type: "visualiser_control",
  broadcast_id: "b-abc123def456",           // Server-generated unique ID
  sender_uuid: "uuid-of-sender",            // Server-derived (trustworthy)
  sender_name: "Living Room Controller",    // From metadata (may be null)
  sender_type: "controller",                // From metadata (may be "unknown")
  target_uuids: ["uuid-1", "uuid-2", "uuid-3"],
  payload: {
    command: "set_brightness",
    value: 80
  }
}
```

**Security Guarantee:** All sender fields (`sender_uuid`, `sender_name`, `sender_type`) are populated by the server based on the authenticated connection, never from client-provided data.

---

### Sender Identity and Security Model

#### The Problem: Client-Provided Sender Identity is Insecure

The current PR implementation accepts `sender_id` from the client request body. **This is a critical security vulnerability** because:

1. **Impersonation Attack**: Any client can claim to be any other client by sending a different UUID
   - Malicious client can send broadcasts appearing to come from a trusted admin client
   - No technical enforcement prevents identity spoofing

2. **Misleading Audit Logs**: Logs record the claimed `sender_id`, not the actual caller
   - Debugging becomes impossible when logs are untrustworthy
   - Security incidents cannot be traced to real actors

3. **Social Engineering**: Users trust broadcasts from known devices
   - Attacker broadcasts malicious commands appearing to come from "Living Room Display"
   - Users may follow instructions thinking they're from a legitimate source

4. **No Accountability**: Without verified sender identity, there's no way to:
   - Rate-limit abusive clients
   - Block misbehaving clients
   - Audit who did what

#### Security Invariant

**Sender identity MUST be derived from the authenticated WebSocket connection, NEVER from client-provided data.**

The server is the sole source of truth for client identity:
- For WebSocket broadcasts: `sender_uuid` comes from the WebSocket connection instance (`self.client_id`)
- For REST broadcasts (if implemented): Server derives identity from request context or uses "system" sender
- Any `sender_id` field in a client request body MUST be rejected with an error (do not silently ignore)

**Critical:** `sender_uuid` is ALWAYS server-derived from the WebSocket connection. Client-provided sender identity fields are security vulnerabilities and must not be accepted.

#### Implementation Approaches

**Option A: WebSocket-Only Broadcasts (Recommended)** ✅

Add new WebSocket message type: `{"type": "broadcast", ...}`

**How it works:**
- Client sends broadcast message via its existing WebSocket connection
- Server uses the connection's UUID (already authenticated) as sender identity
- Server looks up sender metadata (name, type) from class-level storage
- No REST endpoint needed for broadcasts

**Advantages:**
- Inherently secure: sender = authenticated WebSocket connection
- Consistent with WebSocket-first architecture
- Simpler implementation (no REST auth to manage)
- Real-time bidirectional communication already established

**Sender Identity Resolution:**
```python
# In WebSocket handler
async def handle_broadcast(self, data):
    sender_uuid = self.client_id  # From WebSocket connection instance
    sender_metadata = await self.get_all_clients_metadata()
    sender_name = sender_metadata.get(sender_uuid, {}).get("name")
    sender_type = sender_metadata.get(sender_uuid, {}).get("type", "unknown")
    # sender_uuid, sender_name, sender_type are now server-derived and trustworthy
```

---

**Option B: REST API Broadcasts (If Needed)**

If REST broadcasts are required (e.g., for external integrations without WebSocket connections):

**How it works:**
- Client sends `POST /api/clients` with broadcast action (NO `sender_id` field)
- Server uses existing REST authentication to identify the caller
- Server maps authenticated session/token to a sender identity
- If unauthenticated (current state), use special system sender

**Note:** This design works within LedFx's existing authentication model without requiring new authentication mechanisms.

**Sender Identity Resolution:**
```python
# In REST endpoint handler
async def post(self, request):
    # Use existing LedFx authentication
    # (Exact mechanism depends on existing auth implementation)

    # If REST API uses session cookies:
    session = await get_session(request)
    sender_uuid = session.get("client_uuid")  # or create one

    # If REST API uses tokens:
    token = request.headers.get("Authorization")
    sender_uuid = await validate_token_and_get_uuid(token)

    # If no auth available (publicly accessible endpoint):
    sender_uuid = "system"  # Special system sender
    sender_name = "LedFx System"
    sender_type = "api"

    # Never trust request.json().get("sender_id")
```

**Challenges:**
- REST requests may not have an associated WebSocket connection UUID
- Need to define how external API clients get a persistent identity
- More complex than WebSocket-only approach

**Recommendation:** If existing REST API authentication doesn't provide a clear client identity mapping, prefer Option A (WebSocket-only broadcasts).

#### Event Payload Identity Fields

All `ClientBroadcastEvent` payloads MUST include server-derived sender fields:

```python
{
    "sender_uuid": str,          # Server-derived, never from client
    "sender_name": str | None,   # From metadata, fallback to "Client-{uuid[:8]}"
    "sender_type": str,          # From metadata, default "unknown"
    "sender_ip": str | None,     # From connection, useful for debugging
}
```

**Fallback Behavior:**
- If metadata not set: `sender_name = f"Client-{sender_uuid[:8]}"`
- If type not set: `sender_type = "unknown"`
- If metadata lookup fails: Log error, use UUID-based fallback

#### Audit Logging Requirements

Every broadcast request MUST be logged with:

```python
_LOGGER.info(
    f"Broadcast request_id={broadcast_id} "
    f"from sender_uuid={sender_uuid} ({sender_name}, {sender_type}) "
    f"ip={sender_ip} "
    f"to targets={len(target_uuids)} ({target_mode}:{target_value}) "
    f"type={broadcast_type} "
    f"payload_size={len(json.dumps(payload))} bytes"
)
```

**Log Fields:**
- `request_id` / `broadcast_id`: Unique identifier for correlation
- `sender_uuid`: Server-derived sender identity (trustworthy)
- `sender_name`, `sender_type`: Sender metadata (if available)
- `sender_ip`: Connection IP address
- `target_mode`, `target_value`: How targets were selected
- `targets`: Number of matched target clients
- `broadcast_type`: Envelope type
- `payload_size`: Byte size of payload (not full payload, for privacy)
- `timestamp`: Implicit in log entry

**Security Logging:**
- Failed broadcasts: Log with `_LOGGER.warning()` (client error)
- Invalid sender resolution: Log with `_LOGGER.error()` (system error)
- Suspicious patterns: High-frequency broadcasts from single sender

---

## Non-Functional Requirements

### Performance

- **Scalability**: Support up to 100 concurrent clients without significant performance degradation
- **Low Latency**: Metadata operations should complete in <50ms under normal load
- **Broadcast Efficiency**: Broadcasting to 10 clients should complete in <100ms

### Concurrency & Thread Safety

- **Atomic Operations**: Metadata updates must be atomic (no partial states visible)
- **Race Condition Free**: Name uniqueness checks must not have TOCTOU vulnerabilities
- **Consistent Reads**: Clients reading metadata must see consistent snapshots
- **Event Ordering**: Events must fire only after related state changes are persisted

### Security

#### Access Control for Broadcast Endpoints (Future REST Only)

**Note**: This section applies to the **future REST broadcast endpoint** only. WebSocket broadcasts in v1 don't need these restrictions since WebSocket connections are already persistent and authenticated.

**Threat Model:**

If LedFx binds to `0.0.0.0` for LAN usage (common deployment pattern), an unauthenticated REST broadcast endpoint (`POST /api/clients`) becomes a **LAN-wide message injection surface**:

- Any device on the network can send broadcasts
- Malicious actor can spam broadcasts to disrupt service or confuse users
- Social engineering attacks via fake broadcasts from spoofed senders
- Without authentication, no accountability or blocking mechanism

**Design Decision: Localhost-Only by Default**

Restrict `POST /api/clients` (broadcast action) to **localhost connections only** by default:

- **Allowed sources**: `127.0.0.1` (IPv4 loopback), `::1` (IPv6 loopback)
- **Rejected sources**: All non-loopback addresses (LAN, WAN)
- **Opt-in widening**: Explicit configuration required to allow remote broadcasts

**Rationale:**
- WebSocket broadcasts (from authenticated connections) are the primary v1 interface
- REST broadcasts are optional and intended only for local scripts/automation that cannot maintain WebSocket connections
- Remote clients should use WebSocket connections for broadcasts (web UI, mobile apps, API clients)
- Defense in depth: even if sender identity is secure, limit attack surface

**Important:** WebSocket broadcasts are unaffected by this localhost restriction because they are inherently tied to authenticated WebSocket connections. Localhost restriction applies only to the optional REST broadcast endpoint. Clients broadcasting via WebSocket can be on any IP address (LAN, WAN) as long as they have an authenticated WebSocket connection.

---

**Acceptance Criteria:**

1. **Loopback Requests Allowed:**
   ```http
   POST http://127.0.0.1:8888/api/clients  # ✅ Allowed
   POST http://[::1]:8888/api/clients       # ✅ Allowed
   ```

2. **Non-Loopback Requests Rejected:**
   ```http
   POST http://192.168.1.100:8888/api/clients  # ❌ Rejected with 403
   ```

   **Error Response:**
   ```json
   {
     "status": "failed",
     "message": "Remote broadcast requests are not allowed. Broadcasts must originate from localhost (127.0.0.1 or ::1) or use WebSocket connections. To enable remote REST broadcasts, set 'allow_remote_broadcast: true' in configuration.",
     "type": "error"
   }
   ```

   **Logging:**
   ```python
   _LOGGER.warning(
       f"Rejected remote broadcast request from {client_ip} "
       f"(allow_remote_broadcast=false)"
   )
   ```

3. **Reverse Proxy Behavior:**

   When LedFx runs behind a reverse proxy (nginx, Caddy, Apache), all requests appear to come from the proxy's IP (often `127.0.0.1`).

   **Default Behavior (Secure):**
   - Do NOT trust `X-Forwarded-For` or `X-Real-IP` headers by default
   - Use direct connection IP only
   - If proxy is on localhost, all proxied requests appear as localhost (allowed)

   **Proxy Configuration (Opt-In):**
   - If `trusted_proxies` is configured, trust forwarded headers from those IPs only
   - Extract real client IP from `X-Forwarded-For` header
   - Apply localhost restriction to real client IP

   **Example:**
   ```yaml
   # config.yaml
   allow_remote_broadcast: false        # Default: localhost only
   trusted_proxies:                     # Optional: trust these proxies
     - "127.0.0.1"                      # Local nginx
     - "10.0.0.5"                       # Trusted internal proxy
   ```

   **Implementation Pseudocode:**
   ```python
   def get_client_ip(request):
       peer_ip = request.transport.get_extra_info('peername')[0]

       # If trusted_proxies configured and peer is trusted
       if peer_ip in config.get('trusted_proxies', []):
           forwarded_for = request.headers.get('X-Forwarded-For')
           if forwarded_for:
               # Use first IP in chain (real client)
               return forwarded_for.split(',')[0].strip()

       return peer_ip

   def is_localhost(ip):
       return ip in ('127.0.0.1', '::1', 'localhost')

   async def post(self, request):
       action = data.get('action')
       if action == 'broadcast':
           client_ip = get_client_ip(request)

           if not is_localhost(client_ip):
               if not self._ledfx.config.get('allow_remote_broadcast', False):
                   _LOGGER.warning(
                       f"Rejected remote broadcast from {client_ip}"
                   )
                   return await self.invalid_request(
                       "Remote broadcast requests are not allowed. "
                       "Broadcasts must originate from localhost or use WebSocket connections."
                   )
   ```

---

**Configuration Reference:**

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `allow_remote_broadcast` | Boolean | `false` | **[Future]** Allow REST broadcast requests from non-localhost IPs (WebSocket broadcasts unaffected) |
| `trusted_proxies` | List[String] | `[]` | **[Future]** IP addresses of trusted reverse proxies (enables X-Forwarded-For parsing for REST) |

**v1 Note:** These configuration options are NOT used in v1 (WebSocket-only). They will be used when REST broadcasts are added in a future release.

**Security Implications (Future REST Implementation):**
- Setting `allow_remote_broadcast: true` exposes REST broadcast endpoint to LAN without authentication
- Use `trusted_proxies` only in controlled environments where proxy is trusted
- Misconfigured `trusted_proxies` can allow IP spoofing via forged X-Forwarded-For headers

**Recommended Additional Mitigations:**
- **Rate Limiting**: Implement per-IP rate limits for broadcast requests (e.g., 10 requests/minute)
- **Firewall Rules**: Use OS-level firewall to restrict LedFx port to localhost only if remote broadcasts not needed

For this feature, we focus on **localhost restriction** as the primary defense for the optional REST broadcast endpoint, working within existing authentication constraints. Rate limiting should be addressed in separate enhancements.

**Clarification:** The localhost restriction applies only to REST broadcasts (`POST /api/clients`). It does NOT apply to WebSocket broadcasts, which are the primary v1 interface and rely on WebSocket connection authentication. REST broadcasts are not required for core UX and are disabled by default (localhost-only).

---

#### General Security Requirements

- **Rate Limiting**: Consider rate limiting for:
  - Client metadata updates (prevent rapid name change spam)
  - Broadcast requests (prevent DoS via broadcast spam)
- **Payload Validation**: All inputs must be validated against schemas
- **Size Limits**: Enforce maximum payload sizes to prevent memory exhaustion
- **Authorization**: Existing WebSocket authentication/authorization applies (no additional auth needed)

### Reliability

- **Graceful Degradation**: System should handle:
  - Malformed messages (return errors, don't crash)
  - Disconnections during metadata updates
  - Rapid connect/disconnect cycles
- **Error Handling**: All error conditions should be logged and reported to clients appropriately
- **Task Cleanup**: Background tasks must be properly tracked and cleaned up on disconnect

---

## Technical Constraints

### Code Quality

- **Async/Await Consistency**: All async operations must be properly awaited
- **Locking Strategy**: Shared state must be protected with appropriate locks (asyncio.Lock)
- **Import Organization**: All imports at top of file (project standard)
- **Type Hints**: Use type hints where beneficial
- **Error Logging**: Use appropriate log levels:
  - `_LOGGER.warning()` for expected client errors (invalid requests)
  - `_LOGGER.error()` for system errors

### Testing Requirements

- **Unit Tests**:
  - Name conflict resolution (sequential and concurrent)
  - Target filtering logic for all modes
  - Payload validation and size limits
- **Integration Tests**:
  - Concurrent client connections
  - Metadata persistence across handler calls
  - Event ordering guarantees
  - Broadcast delivery to correct targets
- **Breaking Change - GET Endpoint**: `GET /api/clients` returns metadata objects
  - Old format: `{ "uuid": "ip_address", ... }` (simple IP map)
  - New format: `{ "uuid": { metadata_object }, ... }` (full metadata)
  - **Breaking change** - frontend must update to new format
- **Extended POST Endpoint**: `POST /api/clients` with `action: "sync"` continues to work unchanged
  - New `action: "broadcast"` added alongside existing actions
  - **Non-breaking change** - additive only
### Backwards Compatibility

- **Existing WebSocket Clients**: Clients that don't send `set_client_info` should continue working
  - Auto-generate name: `"Client-{uuid[:8]}"`
  - Default type: `"unknown"`
  - No device_id
- **Breaking Change - GET Endpoint**: `GET /api/clients` response format changed
  - **Old format**: `{ "uuid": "ip_address", ... }` (simple IP map)
  - **New format**: `{ "uuid": { "name": "...", "type": "...", "ip": "...", ... }, ... }` (metadata objects)
  - **Impact**: Frontend and any external integrations must update in same release
- **Extended POST Endpoint**: `POST /api/clients` with `action: "sync"` must continue to work unchanged
  - New `action: "broadcast"` added alongside existing actions

---

## Open Design Questions

**Status:** 5 of 6 questions resolved. 1 question remains for discussion before implementation.

### 1. Metadata Persistence Across Reconnections

**Question**: Should we recognize returning clients based on `device_id`?

**Option A - Ephemeral:** ✅ **Current Intent**
- Metadata cleared when client disconnects
- Fresh metadata on reconnect
- Simpler implementation
- Clean, predictable behavior

**Option B - TTL-Based Recognition:**
- Store metadata for 5 minutes after disconnect
- If same `device_id` reconnects, restore previous name/type
- Better UX for rapid reconnects
- More complex cleanup logic
- Can be added later if use cases emerge

---

### 2. REST API Backwards Compatibility

**Question**: Should `GET /api/clients` maintain backwards compatibility?

✅ **RESOLVED - Option C: Breaking Change**

**Decision**: `GET /api/clients` will return metadata objects directly (breaking change)

**Rationale**:
- Clean API design with single source of truth
- No code path duplication or technical debt
- Existing client API is minimally used
- Frontend and backend released together

**Implementation**:
```http
GET /api/clients
# Returns: { "uuid": { "name": "...", "type": "...", "ip": "...", ... }, ... }
```

**Migration Impact**:
- Frontend must be updated in same release
- Old format `{ "uuid": "ip" }` is replaced
- External integrations (if any) need update

---

### 3. Broadcast Message Queuing

**Question**: What happens if target client is connected but doesn't process the broadcast in time?

**Option A - Fire and Forget:** ✅ **Current Intent**
- Server fires event, WebSocket sends to client
- If client's receive buffer is full or processing is slow, message may be dropped
- Simple, no guarantees
- Document as "best effort delivery"
- Sufficient for current use cases

**Option B - Guaranteed Delivery:**
- Queue messages per-client with size limit
- Retry delivery on failure
- Complex, may cause memory issues
- Can be added later if reliable messaging is needed

---

### 4. Client Type Extensibility

**Question**: Should client types be hardcoded or configurable?

**Option A - Hardcoded Enum:** ✅ **Current Intent**
```python
VALID_CLIENT_TYPES = ["controller", "visualiser", "mobile", "display", "api", "unknown"]
```
- Simple validation
- Clear contract
- Type-safe and predictable
- Easy to expand when needed (just update the list)
- Sufficient for foreseeable needs

**Option B - Config-Driven:**
```yaml
# config.yaml
client_types:
  - controller
  - visualiser
  - custom_type_1
```
- Flexible
- Can add types without code change
- Risk of typos, inconsistent naming
- Adds complexity without clear benefit

---

### 5. Broadcast Acknowledgments

**Question**: Should target clients acknowledge receipt of broadcasts?

**Option A - No Acknowledgments:** ✅ **Current Intent**
- Sender receives list of targeted UUIDs
- No confirmation of actual receipt
- Simpler implementation
- Sufficient for most use cases (UI sync, notifications)
- Sender knows who was targeted, even if not who received

**Option B - Optional Acknowledgments:**
- Targets can send ACK messages
- Sender receives ACK events
- More complex, but enables reliable protocols
- Can add later if mission-critical broadcasts emerge

---

### 6. Broadcast Sender Identity Method ✅ **RESOLVED**

**Decision**: WebSocket-Only Broadcasts for v1

**Rationale:**
- Sender identity = WebSocket connection UUID (already authenticated)
- No additional authentication complexity
- Consistent with WebSocket-first architecture
- Simpler, more secure implementation
- Most LedFx clients (web UI, mobile apps) maintain WebSocket connections
- External scripts can connect via WebSocket if they need to broadcast

**Implementation:**
```javascript
// Client sends via WebSocket
{ type: "broadcast", broadcast_type: "...", target: {...}, payload: {...} }
```

**Future Consideration:**
REST broadcast endpoint (`POST /api/clients` with `action: "broadcast"`) can be added in a future release if a documented use case emerges. If implemented, it MUST:
- Be restricted to localhost (127.0.0.1, ::1) by default
- Require explicit `allow_remote_broadcast: true` configuration for remote access
- Use "system" sender identity for unauthenticated requests
- Follow all security guidelines in "Access Control for Broadcast Endpoints" section

---

## Success Criteria

This feature will be considered successfully implemented when:

1. ✅ Multiple clients can connect and each receives a unique name automatically
2. ✅ Clients can set and update their metadata via WebSocket messages
3. ✅ `GET /api/clients` returns complete metadata for all connected clients
4. ✅ Clients can broadcast messages with all targeting modes working correctly
5. ✅ ClientsUpdatedEvent fires appropriately and listeners see consistent state
6. ✅ ClientBroadcastEvent delivers to correct target clients
7. ✅ All unit and integration tests pass
8. ✅ No race conditions exist in concurrent name checks or metadata updates
9. ✅ Code passes linting and follows project conventions
10. ✅ Feature is documented in user-facing API documentation

---

## Implementation Phasing

**Suggested Implementation Order:**

### Phase 1: Infrastructure (Foundation)
- **Update WebSocket dispatcher** to support async handlers:
  - Modify dispatcher (websocket.py line ~272) to detect coroutine functions using `asyncio.iscoroutinefunction()`
  - Await handler if it's a coroutine, otherwise call normally
  - Example: `result = await handler(...) if asyncio.iscoroutinefunction(handler) else handler(...)`
- **Add class-level metadata storage** with proper locking:
  - `WebsocketConnection.client_metadata = {}` (UUID → metadata dict)
  - `WebsocketConnection.metadata_lock = asyncio.Lock()`
- **Add instance attributes** to WebsocketConnection:
  - `self.device_id = None`
  - `self.client_name = None`
  - `self.client_type = "unknown"`
  - `self.connected_at = time.time()` (set in __init__ or handle method)
- Implement thread-safe metadata update utilities

### Phase 2: Client Metadata (Core Feature)
- **Implement `set_client_info` handler** (async):  
  - Use `@websocket_handler("set_client_info")` decorator
  - Extract: device_id, name (default `f"Client-{uuid[:8]}"`), client_type (default "unknown")
  - Validate client_type against VALID_CLIENT_TYPES list
  - Check name uniqueness using async `_name_exists()` method (with lock)
  - If name conflict, append ` (N)` counter
  - Store to instance attributes: `self.device_id`, `self.client_name`, `self.client_type`
  - **Await** `_update_metadata()` to persist
  - Send confirmation: `{"event_type": "client_info_updated", "client_id": self.uid, "name": ..., "type": ..., "name_conflict": bool}`
  - Fire `ClientsUpdatedEvent()` **after** metadata persists
- **Implement `update_client_info` handler** (async):
  - Extract optional: name, client_type
  - If name provided: check uniqueness, reject if taken (send error), otherwise update
  - If client_type provided and valid: update
  - **Await** `_update_metadata()`
  - Send confirmation, fire `ClientsUpdatedEvent()`
- **Implement async `_name_exists(name, exclude_uuid=None)`**:
  - Acquire `metadata_lock` before reading `client_metadata`
  - Return True if name found in any client except exclude_uuid
- **Implement async `_update_metadata()`**:
  - Acquire `metadata_lock`
  - Update `WebsocketConnection.client_metadata[self.uid]` with all fields
  - Update `last_active` timestamp
- **Implement classmethod `get_all_clients_metadata()`**:
  - Acquire `metadata_lock`
  - Return deep copy of `client_metadata`
- **Update `GET /api/clients`**:
  - Parse `?detailed=true` query parameter
  - If detailed: return `await WebsocketConnection.get_all_clients_metadata()`
  - If not detailed (default): return `{uuid: meta["ip"] for uuid, meta in metadata.items()}`
- Fire `ClientsUpdatedEvent` on connect/disconnect (already exists, verify metadata cleanup on disconnect)

### Phase 3: Broadcasting (Core Feature)
- **Define constants in `clients.py`**:
  - `ACTIONS = ["sync", "broadcast"]`
  - `BROADCAST_TYPES = ["visualiser_control", "scene_sync", "color_palette", "custom"]`
  - `TARGET_MODES = ["all", "type", "names", "uuids"]`
  - `MAX_PAYLOAD_SIZE = 2048`
  - `VALID_CLIENT_TYPES = ["controller", "visualiser", "mobile", "display", "api", "unknown"]`
- **Define Voluptuous schema** `BROADCAST_SCHEMA`:
  - Required: action ("broadcast"), broadcast_type (In BROADCAST_TYPES), target (dict), payload (dict)
  - Target schema: Required mode (In TARGET_MODES), Optional value/names/uuids
  - **Do NOT include sender_id field** (security vulnerability)
- **WebSocket broadcast handler** (v1 only interface):
  - Add `@websocket_handler("broadcast")` (async)
  - Validate schema and payload size
  - Derive sender: `sender_uuid = self.uid`, lookup sender_name and sender_type from metadata
  - Call `_filter_targets()` to get target_uuids list
  - Reject if no targets matched
  - Generate `broadcast_id = f"b-{int(time.time() * 1000)}"`
  - Fire `ClientBroadcastEvent(broadcast_type, sender_uuid, sender_name, sender_type, target_uuids, payload)`
  - Log broadcast with audit fields
  - Return success response with broadcast_id, targets_matched, targets list
- **Note**: REST broadcast endpoint (`POST /api/clients` action="broadcast") is NOT implemented in v1. Deferred to future release if use case emerges.
- **Implement `_filter_targets(target_config, clients)` method**:
  - mode="all": return all UUIDs
  - mode="type": filter by `meta.get("type") == value` (reject if value missing/empty)
  - mode="names": filter by `meta.get("name") in names` (reject if names missing/empty)
  - mode="uuids": filter by UUID in known clients (reject if uuids missing/empty)
  - Return empty list if mode invalid or validation fails
- Add payload validation and size limits

### Phase 4: Testing & Documentation
- Write comprehensive unit tests
- Write integration tests for concurrent scenarios
- Document WebSocket message protocol
- Document REST API changes
- Add examples to API documentation

Each phase should be fully tested before moving to the next.

---

## Out of Scope

The following are explicitly **not** included in this feature:

- ❌ Authentication/authorization changes (uses existing WebSocket auth)
- ❌ Persistent storage of client metadata between server restarts
- ❌ Client presence indicators ("online/offline" status display)
- ❌ Direct peer-to-peer messaging (all communication goes through server)
- ❌ Broadcast message history or replay
- ❌ Guaranteed message delivery or acknowledgment protocols
- ❌ Rate limiting (should be added separately if needed)
- ❌ Client permissions/roles system
- ❌ Broadcast encryption or signing

### Out of Scope (v1 Specifically)

The following are **not goals for v1** and should only be considered if specific use cases emerge:

- ❌ **REST broadcast endpoint** - v1 uses WebSocket-only broadcasts. REST endpoint (`POST /api/clients` with `action: "broadcast"`) deferred to future release
- ❌ Remote REST broadcasts (non-localhost) - If REST endpoint added later, must be localhost-only by default
- ❌ Unauthenticated REST broadcast support - If REST endpoint added later, use "system" sender for unauthenticated requests

These could be considered for future enhancements if use cases emerge.

---

## Technical Implementation Reference

### Constants to Define

**In `ledfx/api/clients.py`:**
```python
ACTIONS = ["sync", "broadcast"]
BROADCAST_TYPES = ["visualiser_control", "scene_sync", "color_palette", "custom"]
TARGET_MODES = ["all", "type", "names", "uuids"]
MAX_PAYLOAD_SIZE = 2048  # 2KB
```

**In `ledfx/api/websocket.py`:**
```python
VALID_CLIENT_TYPES = ["controller", "visualiser", "mobile", "display", "api", "unknown"]
```

### Schema Definitions

**Broadcast Schema (Voluptuous):**
```python
import voluptuous as vol

BROADCAST_SCHEMA = vol.Schema(
    {
        vol.Required("action"): "broadcast",
        vol.Required("broadcast_type"): vol.In(BROADCAST_TYPES),
        vol.Required("target"): {
            vol.Required("mode"): vol.In(TARGET_MODES),
            vol.Optional("value"): str,
            vol.Optional("names"): [str],
            vol.Optional("uuids"): [str],
        },
        vol.Required("payload"): dict,
    }
)
# NOTE: No sender_id field - server derives this
```

### Class-Level Shared State Pattern

**In `WebsocketConnection` class:**
```python
class WebsocketConnection:
    # Class-level shared state
    ip_uid_map = {}  # Existing
    map_lock = asyncio.Lock()  # Existing
    client_metadata = {}  # NEW: UUID -> metadata dict
    metadata_lock = asyncio.Lock()  # NEW: Protect metadata access
    
    def __init__(self, ledfx):
        # ... existing init ...
        # Instance attributes for this connection
        self.device_id = None
        self.client_name = None
        self.client_type = "unknown"
        self.connected_at = time.time()
```

### Async Handler Pattern

**WebSocket Dispatcher Update (line ~272):**
```python
# OLD: handler = websocket_handlers.get(message_type)
#      handler(self, message)

# NEW:
handler = websocket_handlers.get(message_type)
if handler:
    if asyncio.iscoroutinefunction(handler):
        await handler(self, message)
    else:
        handler(self, message)
```

**Handler Definition Pattern:**
```python
@websocket_handler("set_client_info")
async def set_client_info_handler(self, message):  # NOTE: async def
    # Extract data
    name = message.get("name", f"Client-{self.uid[:8]}")
    
    # Async operations with proper awaits
    name_conflict = await self._check_and_resolve_name(name)
    
    # Update instance attributes
    self.client_name = name
    
    # Await metadata persistence
    await self._update_metadata()
    
    # THEN fire event (after persistence)
    self._ledfx.events.fire_event(ClientsUpdatedEvent())
```

### Lock-Guarded Read Pattern

**Reading Shared Metadata:**
```python
async def _name_exists(self, name, exclude_uuid=None):
    """Check if name exists with proper locking"""
    async with WebsocketConnection.metadata_lock:
        for uuid, meta in WebsocketConnection.client_metadata.items():
            if uuid != exclude_uuid and meta.get("name") == name:
                return True
    return False

@classmethod
async def get_all_clients_metadata(cls):
    """Get metadata snapshot with proper locking"""
    async with cls.metadata_lock:
        return dict(cls.client_metadata)  # Return copy
```

### Metadata Cleanup on Disconnect

**In `handle()` method cleanup:**
```python
finally:
    # ... existing cleanup ...
    
    # Remove metadata
    async with WebsocketConnection.metadata_lock:
        if self.uid in WebsocketConnection.client_metadata:
            del WebsocketConnection.client_metadata[self.uid]
    
    # Fire event after cleanup
    self._ledfx.events.fire_event(ClientsUpdatedEvent())
```

### Broadcast ID Generation

```python
import time

broadcast_id = f"b-{int(time.time() * 1000)}"  # Millisecond timestamp
```

### Localhost IP Check

```python
def get_client_ip(request):
    """Extract client IP with proxy support"""
    peer_ip = request.transport.get_extra_info('peername')[0]
    
    # Check trusted proxies
    trusted = self._ledfx.config.get('trusted_proxies', [])
    if peer_ip in trusted:
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
    
    return peer_ip

def is_localhost(ip):
    """Check if IP is loopback"""
    return ip in ('127.0.0.1', '::1', 'localhost')
```

### Event Class Constructors

**In `ledfx/events.py`:**
```python
class ClientsUpdatedEvent(Event):
    """Event emitted when client list/metadata changes"""
    def __init__(self):
        super().__init__(Event.CLIENTS_UPDATED)

class ClientBroadcastEvent(Event):
    """Event emitted when a client broadcasts"""
    def __init__(
        self,
        broadcast_type: str,
        sender_uuid: str,
        sender_name: str | None,
        sender_type: str,
        target_uuids: list[str],
        payload: dict,
    ):
        super().__init__(Event.CLIENT_BROADCAST)
        self.broadcast_type = broadcast_type
        self.broadcast_id = f"b-{int(time.time() * 1000)}"  # Server-generated
        self.sender_uuid = sender_uuid
        self.sender_name = sender_name
        self.sender_type = sender_type
        self.target_uuids = target_uuids
        self.payload = payload
```

---

## Example Use Case Scenarios

### Scenario 1: Multi-Room Display Setup

**Setup:**
- Living Room: Web UI controller (laptop)
- Bedroom: Display-only client (Raspberry Pi)
- Kitchen: Display-only client (Tablet)

**Flow:**
1. All three clients connect to LedFx server
2. Living room controller sends `set_client_info` with `name: "Control Center"`, `type: "controller"`
3. Bedroom display sends `set_client_info` with `name: "Bedroom Display"`, `type: "display"`
4. Kitchen display sends `set_client_info` with `name: "Kitchen Display"`, `type: "display"`
5. User queries `GET /api/clients` and sees all three clients listed by name
6. User changes a preset in living room controller
7. Controller broadcasts to all `"display"` type clients: `{ command: "reload_presets" }`
8. Both bedroom and kitchen displays receive broadcast and reload their preset list

### Scenario 2: Mobile App Sync

**Setup:**
- Desktop: Web UI (primary controller)
- Phone: Mobile app (secondary controller)

**Flow:**
1. Desktop connects, sets name "Desktop Control"
2. Phone connects, tries to set name "Desktop Control" → auto-renamed to "Desktop Control (1)"
3. User activates scene "Party Mode" on desktop
4. Desktop broadcasts to `mode: "all"`: `{ broadcast_type: "scene_sync", scene_id: "party_mode" }`
5. Phone receives broadcast, updates its UI to show "Party Mode" is active
6. User's experience is synchronized across devices

### Scenario 3: API Integration

**Setup:**
- Web UI: Primary controller
- Custom Script: Python API client monitoring state

**Flow:**
1. Web UI connects as `type: "controller"`
2. Python script connects via WebSocket, sets `type: "api"`, `name: "State Monitor"`
3. Admin queries `GET /api/clients`, sees both clients and their types
4. Web UI broadcasts color palette change to `mode: "type"`, `value: "api"`
5. Python script receives palette data and logs it to external system
6. Only API clients receive this broadcast, not the UI itself

---

## Acceptance Checklist

Before merging, confirm:

- [ ] All success criteria met
- [ ] Open design questions resolved and documented
- [ ] Code review completed with no unresolved issues
- [ ] Unit tests achieve >80% coverage of new code
- [ ] Integration tests cover concurrent scenarios
- [ ] No race conditions or TOCTOU vulnerabilities
- [ ] All linting checks pass
- [ ] Imports organized per project standards
- [ ] Appropriate logging levels used
- [ ] REST API changes documented
- [ ] WebSocket protocol documented
- [ ] Example code provided for common use cases
- [ ] Changelog updated with breaking change: GET /api/clients response format
- [ ] Frontend updated to handle new GET /api/clients format

---

## References

- **Related PR**: #1711 (initial implementation, requires revision)
- **WebSocket Handler Pattern**: See `ledfx/api/websocket.py`
- **REST API Patterns**: See `ledfx/api/*.py`, especially helpers in `RestEndpoint`
- **Event System**: See `ledfx/events.py`
- **Project Coding Standards**: See `.github/copilot-instructions.md`

---

**Document Status:** Ready for Review
**Next Steps:**
1. Review with PR author and core team
2. Resolve open design questions
3. Approve scope and proceed to implementation

