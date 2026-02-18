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

#### API Surface

**REST API:**

```http
POST /api/clients
Content-Type: application/json

{
  "action": "broadcast",
  "broadcast_type": "visualiser_control",
  "sender_id": "uuid-of-sender",
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

1. Client sends broadcast request to REST API
2. Server validates schema and payload size
3. Server filters target clients based on targeting mode
4. If no targets match, return error
5. Server fires `ClientBroadcastEvent` with enriched payload
6. WebSocket connections subscribed to events receive the broadcast
7. Clients filter by `target_uuids` to determine if message is for them

**Event Payload:**

```javascript
{
  event_type: "client_broadcast",
  broadcast_type: "visualiser_control",
  sender_id: "uuid-of-sender",
  sender_name: "Living Room Controller",
  target_uuids: ["uuid-1", "uuid-2", "uuid-3"],
  payload: {
    command: "set_brightness",
    value: 80,
    // Note: target_uuids is injected by server for client-side filtering
  }
}
```

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
  - Broadcast delivery to correct targetsmaintains backward compatibility
  - Default behavior unchanged: Returns `{ "uuid": "ip_address", ... }` (simple IP map)
  - New optional parameter: `?detailed=true` returns full metadata objects
  - **Non-breaking change** - existing clients continue to work
- **Extended POST Endpoint**: `POST /api/clients` with `action: "sync"` continues to work unchanged
  - New `action: "broadcast"` added alongside existing actions
  - **Non-breaking change** - additive only
### Backwards Compatibility

- **Existing WebSocket Clients**: Clients that don't send `set_client_info` should continue working
  - Auto-generate name: `"Client-{uuid[:8]}"`
  - Default type: `"unknown"`
  - No device_id
- **Modified GET Endpoint**: `GET /api/clients` currently returns `{ "uuid": "ip_address", ... }` (simple IP map)
  - New version returns `{ "uuid": { metadata_object }, ... }` (full metadata)
  - **This is a breaking change** for clients expecting the old format
  - **Decision needed**: Should we maintain backwards compatibility or accept breaking change?
- **Extended POST Endpoint**: `POST /api/clients` with `action: "sync"` must continue to work unchanged
  - New `action: "broadcast"` added alongside existing actions

---

## Open Design Questions

The following questions should be resolved before implementation:

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

**Current**: Returns `{ "uuid": "ip", ... }` (simple IP map)
**Proposed**: Returns `{ "uuid": { metadata }, ... }` (metadata objects)

**Option A - Query Parameter (Non-Breaking):** ✅ **Current Intent**
```http
GET /api/clients              # Default: returns IP map (backward compatible)
GET /api/clients?detailed=true # Returns full metadata objects
```
- **Pros**: Fully backward compatible, single endpoint, clear intent
- **Cons**: Requires parsing query params, two code paths to maintain
- **Frontend change**: Add `?detailed=true` to get new format
- **Best balance**: Compatibility + simplicity, can deprecate old format later

**Option B - New Endpoint (Non-Breaking):**
```http
GET /api/clients              # Keep returning IP map (deprecated)
GET /api/clients/metadata     # New endpoint for full metadata
```
- **Pros**: Clean separation, existing clients unaffected
- **Cons**: Two endpoints doing similar things, requires new route
- **Frontend change**: Switch to `/api/clients/metadata`

**Option C - Breaking Change:**
- `GET /api/clients` now returns metadata objects directly
- **Pros**: Clean API design, single source of truth
- **Cons**: Requires frontend update in same release, may break external integrations

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
- Update WebSocket dispatcher to support async handlers
- Add class-level metadata storage with proper locking
- Implement thread-safe metadata update utilities

### Phase 2: Client Metadata (Core Feature)
- Implement `set_client_info` handler
- Implement `update_client_info` handler
- Implement name uniqueness and conflict resolution
- Update `GET /api/clients` to return metadata
- Fire `ClientsUpdatedEvent` on metadata changes

### Phase 3: Broadcasting (Advanced Feature)
- Implement `POST /api/clients` broadcast action
- Implement target filtering for all modes
- Fire `ClientBroadcastEvent` with proper routing
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
- [ ] Changelog updated with breaking changes (if any)
- [ ] Feature flag added if needed for gradual rollout

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

