# WebSocket Client API

## Overview

This document outlines the enhancement of LedFx's WebSocket connection system to support persistent client metadata tracking and client-to-client messaging capabilities. These features enable richer multi-client experiences, better observability of connected clients, and coordinated interactions between frontend instances, mobile apps, and API clients.

Please also see the dev guides:
- [WebSocket Client Examples](../developer/websocket_client_examples.md)
- [Client Sync Migration Guide](../developer/client_sync_migration_guide.md)

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
If REST broadcasts are added in a future release, they MUST:
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

#### Client Types (Enumeration)

- `controller` - Web UI or primary control interface
- `visualiser` - Display-only client (e.g., fullscreen visualization)
- `mobile` - Mobile app client
- `display` - Dedicated display device (e.g., Raspberry Pi kiosk)
- `api` - Programmatic API client
- `unknown` - Fallback for unspecified clients

#### Client Name Requirements

- **Uniqueness**: Client names must be unique across all connected clients
- **Conflict Resolution (Initial Registration)**: When `set_client_info` is called with a taken name, automatically append a counter: `"MyClient"` → `"MyClient (2)"` → `"MyClient (3)"`
  - Client receives confirmation with `name_conflict: true` flag to indicate modification
  - Ensures smooth initial connection without blocking on name conflicts
- **Conflict Resolution (Explicit Rename)**: When `update_client_info` is called with a taken name, reject with error
  - User-initiated renames require explicit acknowledgment - no silent auto-modification
  - Client must choose alternative name and retry
- **Auto-generation**: If no name provided, generate: `"Client-{first-8-chars-of-uuid}"`
- **Persistence**: Name persists for the duration of the connection only
- **Updates**: Clients can request name changes after connection via `update_client_info` (subject to uniqueness check)

#### API Surface

**WebSocket Messages (Client → Server):**

```javascript
// Initial metadata setup (typically sent immediately after connection)
{
  id: 1,                            // required message correlation ID
  type: "set_client_info",
  data: {
    device_id: "abc123-device-uuid",  // optional, for recognizing returning devices
    name: "Living Room Display",      // optional, will auto-generate if missing
    type: "display"                   // optional, defaults to "unknown"
  }
}

// Update metadata while connected (name and type)
{
  id: 2,                            // required message correlation ID
  type: "update_client_info",
  data: {
    name: "Bedroom Display",          // optional, update name
    type: "display"                   // optional, update type
  }
}
```

**WebSocket Messages (Server → Client):**

```javascript
// Confirmation after metadata set/update
{
  id: 1,                            // echoes request id
  event_type: "client_info_updated",
  client_id: "uuid-of-this-client",
  name: "Living Room Display",      // final name (may differ if conflict)
  type: "display",
  name_conflict: false              // true if name was auto-modified
}

// Error response
{
  id: 1,                            // echoes request id
  success: false,
  error: {
    message: "Name already in use"
  }
}
```

**REST API:**

```
GET /api/clients
```

> **Breaking Change**: As of this version, GET /api/clients always returns full client metadata objects (not just IP strings).

**Response:**
```json
{
  "client-uuid-1": {
    "ip": "192.168.1.100",
    "device_id": "abc123-device-uuid",
    "name": "Living Room Display",
    "type": "display",
    "connected_at": 1708188000.123
  },
  "client-uuid-2": {
    "ip": "192.168.1.101",
    "device_id": null,
    "name": "Client-e7a3f2d1",
    "type": "unknown",
    "connected_at": 1708188050.789
  }
}
```

#### Event Notifications

**New Event: `ClientsUpdatedEvent`**

Fired when:
- A client connects or disconnects
- A client's metadata changes (name update)

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

| Mode | Description | Configuration | Sender Behavior |
|------|-------------|---------------|-----------------|
| `all` | Broadcast to all connected clients | No additional config | Auto-excluded (prevents self-echo) |
| `type` | Target all clients of a specific type | `value: "display"` | Included if sender matches specified type |
| `names` | Target specific clients by name | `names: ["Display 1", "Display 2"]` | Included only if sender's name is in list |
| `uuids` | Target specific clients by UUID | `uuids: ["uuid-1", "uuid-2"]` | Included only if sender's UUID is in list |

#### Request Validation

- **Payload Size Limit**: 2 KB maximum (configurable via constant)
- **Schema Validation**: Voluptuous schema enforcement
- **Target Validation**:
  - **Lenient Filtering**: For `mode="names"` and `mode="uuids"`, non-existent identifiers are silently filtered (broadcasts to whoever exists from the list)
  - **Fail-Closed Security**: If NO targets remain after filtering, request fails with error (prevents accidental broadcasts to zero recipients)
  - **Sender Exclusion**:
    - `mode="all"`: Sender is automatically excluded (prevents self-echo)
    - `mode="type"`: Sender is included if they match the specified type
    - `mode="names"`: Sender is excluded UNLESS their name is explicitly in the names list
    - `mode="uuids"`: Sender is excluded UNLESS their UUID is explicitly in the uuids list
  - Type value must be a valid client type
  - Request fails only if no targets match after filtering

#### Target Specification Validation Rules

**Security Invariant:** Targeting must be explicit. Invalid or ambiguous target specifications fail closed (broadcast rejected, not sent to unintended recipients).

**Common Pitfall:** If `mode="type"` with missing/empty `value`, naive implementations might match clients with `type=None`, causing unintended targeting of all clients without metadata.

**Required Validation:**

1. **Mode: `"all"`**
   - Broadcasts to all connected clients **except sender** (prevents self-echo)
   - No additional fields required
   - Ignore `value`, `names`, or `uuids` if present
   - Always valid (assuming at least one other client is connected)

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
   - **Lenient Filtering**: Non-existent names are silently ignored (broadcasts to whoever exists)
   - **Fail-Closed**: If NO clients match any of the specified names, request fails
   - **Error**: `"Target mode 'names' requires a non-empty 'names' list"` (schema validation)
   - **Error**: `"No clients matched target specification"` (zero matches after filtering)

4. **Mode: `"uuids"`**
   - **MUST** include `uuids` field
   - `uuids` **MUST** be a non-empty list
   - Each UUID **MUST** be a non-empty string
   - Reject if `uuids` is missing, empty list, or contains empty strings
   - **Lenient Filtering**: Non-existent UUIDs are silently ignored (broadcasts to whoever exists)
   - **Fail-Closed**: If NO clients match any of the specified UUIDs, request fails
   - **Error**: `"Target mode 'uuids' requires a non-empty 'uuids' list"` (schema validation)
   - **Error**: `"No clients matched target specification"` (zero matches after filtering)
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

**Lenient Filtering Examples:**

The lenient filtering behavior allows broadcasts to "whoever is available" from a list, which is useful for multi-device scenarios where clients may disconnect/reconnect:

```javascript
// Scenario: Sender wants to broadcast to Display 1, Display 2, Display 3
// Currently connected: Display 1 (uuid-1), Display 2 (uuid-2)
// Display 3 is offline

// Request with mode="names"
{
  target: { mode: "names", names: ["Display 1", "Display 2", "Display 3"] }
}

// Result: ✅ Broadcasts to Display 1 and Display 2
// "Display 3" is silently ignored (not connected)
// targets_matched: 2

// If ALL specified names are offline:
{
  target: { mode: "names", names: ["Display 3", "Display 4"] }
}
// Result: ❌ Error "No clients matched target specification"
```

**Sender Exclusion Examples:**

```javascript
// Scenario 1: mode="all" - Sender always excluded
// 3 clients connected (uuid-sender, uuid-1, uuid-2)

{
  target: { mode: "all" }
}
// Result: ✅ Broadcasts to uuid-1 and uuid-2 only
// uuid-sender (the sender) is automatically excluded to prevent self-echo
// targets_matched: 2

// Scenario 2: mode="type" - Sender included if matching type
// Sender has type="display", 2 other displays connected

{
  target: { mode: "type", value: "display" }
}
// Result: ✅ Broadcasts to all 3 displays (including sender)
// Sender is included because they match type="display"
// targets_matched: 3

// Scenario 3: mode="uuids" - Honors explicit list
// Sender is uuid-sender

{
  target: { mode: "uuids", uuids: ["uuid-1", "uuid-2"] }
}
// Result: ✅ Broadcasts to uuid-1 and uuid-2
// Sender (uuid-sender) NOT in list, so excluded
// targets_matched: 2

{
  target: { mode: "uuids", uuids: ["uuid-sender", "uuid-1"] }
}
// Result: ✅ Broadcasts to uuid-sender and uuid-1
// Sender (uuid-sender) IS in list, so INCLUDED (explicit opt-in)
// targets_matched: 2

// Scenario 4: mode="names" - Honors explicit list
// Sender name is "Controller-1"

{
  target: { mode: "names", names: ["Display-1", "Display-2"] }
}
// Result: ✅ Broadcasts to Display-1 and Display-2
// Sender (Controller-1) NOT in list, so excluded
// targets_matched: 2

{
  target: { mode: "names", names: ["Controller-1", "Display-1"] }
}
// Result: ✅ Broadcasts to Controller-1 and Display-1
// Sender (Controller-1) IS in list, so INCLUDED (explicit opt-in)
// targets_matched: 2
```

---

**Test Cases:**

- ✅ `mode="all"` → broadcasts to all connected clients **except sender**
- ✅ `mode="type", value="visualiser"` → broadcasts to clients with `type="visualiser"` **including sender if sender matches type**
- ✅ `mode="type", value="unknown"` → broadcasts to clients with `type="unknown"` **including sender if sender matches type**
- ❌ `mode="type", value=""` → rejected (400 error)
- ❌ `mode="type", value=null` → rejected (400 error)
- ❌ `mode="type"` (missing value) → rejected (400 error)
- ✅ `mode="type", value="display"` with no matching clients → rejected (no targets matched)
- ✅ `mode="type", value="display"` with client `type=None` → client NOT targeted (explicit type required)
- ✅ `mode="names", names=["Client-1"]` with sender name != "Client-1" → broadcasts to Client-1 only (sender excluded)
- ✅ `mode="names", names=["Client-1", "Sender-Name"]` with sender name = "Sender-Name" → broadcasts to Client-1 and sender (explicit inclusion)
- ✅ `mode="names", names=["Client-1", "Client-999"]` with only Client-1 connected → broadcasts to Client-1 (lenient)
- ✅ `mode="names", names=["Client-999"]` with Client-999 offline → rejected (no targets matched)
- ❌ `mode="names", names=[]` → rejected (400 error)
- ❌ `mode="names"` (missing names) → rejected (400 error)
- ✅ `mode="uuids", uuids=["abc-123"]` with sender uuid != "abc-123" → broadcasts to abc-123 only (sender excluded)
- ✅ `mode="uuids", uuids=["abc-123", "sender-uuid"]` with sender uuid = "sender-uuid" → broadcasts to abc-123 and sender (explicit inclusion)
- ✅ `mode="uuids", uuids=["abc-123", "xyz-999"]` with only abc-123 connected → broadcasts to abc-123 (lenient)
- ✅ `mode="uuids", uuids=["xyz-999"]` with xyz-999 offline → rejected (no targets matched)
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
  "id": 1,
  "type": "broadcast",
  "data": {
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
}
```

#### Event Flow

1. Client sends broadcast request (via WebSocket)
2. Server derives sender identity from authenticated connection (never trusts client-provided sender_id)
3. Server validates schema and payload size
4. Server filters target clients based on targeting mode
5. If no targets match, return error
6. Server fires `ClientBroadcastEvent` with server-derived sender fields
7. Server logs broadcast with audit trail (request_id, sender, targets, type)
8. **Server sends broadcast event to ALL subscribers** of `client_broadcast` event type
9. **Clients MUST filter by checking if their UUID is in `target_uuids` list** (client-side filtering)

**Important:** The broadcast event is sent to all clients subscribed to `client_broadcast`, regardless of the targeting mode. The `target_uuids` field is metadata that clients use for client-side filtering. This means:
- All subscribers receive the event payload (including those not in `target_uuids`)
- Clients are responsible for checking `target_uuids.includes(myClientId)` before processing
- Sensitive data in payloads is visible to all subscribers (consider this in your threat model)

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

### Broadcast Delivery Architecture

**Design Decision:** Broadcast-to-All with Client-Side Filtering

The current implementation uses LedFx's existing event system which broadcasts to all subscribers. This means:

1. **Server-Side:**
   - Server fires `ClientBroadcastEvent` to the event system
   - Event system sends to **ALL** WebSocket connections subscribed to `client_broadcast`
   - The `target_uuids` list is included as metadata in the event payload

2. **Client-Side:**
   - **Every subscriber receives every broadcast event**
   - Clients **MUST** check if their UUID is in `target_uuids` before processing
   - Clients **SHOULD** filter out their own broadcasts (check `sender_uuid`)

**Architectural Implications:**

✅ **Advantages:**
- Simple implementation using existing event infrastructure
- Consistent with LedFx's event-driven architecture
- No need to maintain WebSocket connection registry for targeting

❌ **Limitations:**
- **Privacy:** All subscribers see payload data not intended for them (visible before client-side filtering)
- **Efficiency:** Network bandwidth used sending to clients who will discard the message
- **Security Audit:** Harder to prove data isolation since all clients receive all payloads

**Client Implementation Requirements:**

All clients subscribing to `client_broadcast` events **MUST** implement this filtering pattern:

```javascript
if (data.event_type === 'client_broadcast') {
  // 1. REQUIRED: Check if broadcast is for us
  if (!data.target_uuids.includes(myClientId)) {
    return; // Not for us - discard immediately
  }

  // 2. OPTIONAL: Filter out own broadcasts
  if (data.sender_uuid === myClientId) {
    return; // We sent this - discard
  }

  // 3. Process the broadcast
  handleBroadcast(data);
}
```

### Sender Identity and Security Model

#### Security Invariant

**Sender identity MUST be derived from the authenticated WebSocket connection, NEVER from client-provided data.**

The server is the sole source of truth for client identity:
- For WebSocket broadcasts: `sender_uuid` comes from the WebSocket connection instance (`self.uid`)
- For REST broadcasts (if implemented): Server derives identity from request context or uses "system" sender
- Any `sender_id` field in a client request body MUST be rejected with an error (do not silently ignore)

**Critical:** `sender_uuid` is ALWAYS server-derived from the WebSocket connection. Client-provided sender identity fields are security vulnerabilities and must not be accepted.

#### Implementation Approaches

**Option A: WebSocket-Only Broadcasts** ✅

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
    # Derive sender identity from WebSocket connection (server-side)
    sender_uuid = self.uid  # Canonical client UUID
    sender_name = self.client_name or f"Client-{sender_uuid[:8]}"
    sender_type = self.client_type
    # sender_uuid, sender_name, sender_type are now server-derived and trustworthy
```

#### Event Payload Identity Fields

All `ClientBroadcastEvent` payloads MUST include server-derived sender fields:

```python
{
    "sender_uuid": str,          # Server-derived, never from client
    "sender_name": str | None,   # From metadata, fallback to "Client-{uuid[:8]}"
    "sender_type": str,          # From metadata, default "unknown"
}
```

> **Privacy Note:** `sender_ip` is intentionally excluded from broadcast events to protect client privacy. IP addresses are only available in server-side connection metadata and logs.

**Fallback Behavior:**
- If metadata not set: `sender_name = f"Client-{sender_uuid[:8]}"`
- If type not set: `sender_type = "unknown"`
- If metadata lookup fails: Log error, use UUID-based fallback

#### Audit Logging Requirements

Every broadcast request MUST be logged with:

```python
_LOGGER.info(
    f"Broadcast {broadcast_id}: type={broadcast_type}, "
    f"sender={sender_name} ({sender_uuid[:8]}), "
    f"targets={len(target_uuids)} clients"
)
```

**Log Fields:**
- `broadcast_id`: Unique identifier for correlation
- `broadcast_type`: Envelope type
- `sender_name`: Sender metadata
- `sender_uuid`: Server-derived sender identity (truncated for readability)
- `targets`: Number of matched target clients
- `timestamp`: Implicit in log entry

> **Privacy Note:** The audit log intentionally omits payload contents and sender IP addresses. IP addresses are available in connection metadata (`GET /api/clients`) if needed for debugging.

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

### Backwards Compatibility

- **Existing WebSocket Clients**: Clients that don't send `set_client_info` should continue working
  - Auto-generate name: `"Client-{uuid[:8]}"`
  - Default type: `"unknown"`
  - No device_id
- **Breaking Change - GET Endpoint**: `GET /api/clients` response format changed
  - **Old format**: `{ "uuid": "ip_address", ... }` (simple IP map)
  - **New format**: `{ "uuid": { "name": "...", "type": "...", "ip": "...", ... }, ... }` (metadata objects)
  - **Impact**: Frontend and any external integrations must update in same release

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

- ❌ **REST broadcast endpoint** - v1 uses WebSocket-only broadcasts. REST endpoint (`POST /api/clients` with `action: "broadcast"`) deferred
- ❌ Remote REST broadcasts (non-localhost) - If REST endpoint added later, must be localhost-only by default
- ❌ Unauthenticated REST broadcast support - If REST endpoint added later, use "system" sender for unauthenticated requests

These could be considered for future enhancements if use cases emerge.

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
2. Phone connects, tries to set name "Desktop Control" → auto-renamed to "Desktop Control (2)"
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

## References

- **Related PR**: #1711 (initial implementation, requires revision)
- **WebSocket Handler Pattern**: See `ledfx/api/websocket.py`
- **REST API Patterns**: See `ledfx/api/*.py`, especially helpers in `RestEndpoint`
- **Event System**: See `ledfx/events.py`
- **Project Coding Standards**: See `.github/copilot-instructions.md`
