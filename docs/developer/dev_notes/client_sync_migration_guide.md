# Websocket Client Migration Guide

**Legacy Client Sync → New Client Management System**

## Overview

This guide documents the migration path from the legacy `client_sync` system to the new secure client management and broadcasting system introduced in LedFx 0.11.0.

## Why Migrate?

The legacy system has a critical security flaw:

**Legacy Issue**: Clients provide their own `client_id` in REST requests, enabling sender spoofing
```javascript
// ⚠️ Any client can claim to be any other client
fetch('/api/clients', {
  body: JSON.stringify({
    action: 'sync',
    client_id: 'someone-elses-id'  // Spoofing possible!
  })
});
```

**New Security**: Server derives sender identity from WebSocket connection
```javascript
// ✅ Server ensures sender_uuid matches the actual WebSocket connection
websocket.send(JSON.stringify({
  type: 'broadcast',
  data: {
    broadcast_type: 'scene_sync',
    target: { mode: 'all' },
    payload: { action: 'sync' }
  }
}));
```

## Migration Timeline

### Phase 1: Backend Implementation ✅ COMPLETE
- [x] New client metadata system (set_client_info, update_client_info)
- [x] New broadcasting system with server-derived sender identity
- [x] New events: `clients_updated`, `client_broadcast`
- [x] Breaking change: GET /api/clients returns full metadata

### Phase 2: Frontend Migration 🔄 IN PROGRESS
- [ ] Update frontend to use new WebSocket broadcasting
- [ ] Replace `client_sync` subscriptions with `client_broadcast`
- [ ] Implement client metadata registration (set_client_info)
- [ ] Update to handle new GET /api/clients format
- [ ] Test migration thoroughly

### Phase 3: Cleanup 🔜 PENDING
- [ ] Remove POST /api/clients "sync" action
- [ ] Remove `ClientSyncEvent` from events.py
- [ ] Remove `CLIENT_SYNC` constant
- [ ] Remove legacy documentation
- [ ] Update changelog to note removal

## Side-by-Side Comparison

### 1. Client Connection & Registration

#### Old System
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8888/api/websocket');
let clientId = null;

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Receive client ID
  if (data.event_type === 'client_id') {
    clientId = data.client_id;
    console.log('Client ID:', clientId);
    // No metadata registration - just store the ID
  }
};
```

#### New System
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8888/api/websocket');
let clientId = null;

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Receive client ID
  if (data.event_type === 'client_id') {
    clientId = data.client_id;
    console.log('Client ID:', clientId);

    // ✨ NEW: Register metadata
    ws.send(JSON.stringify({
      id: 1,
      type: 'set_client_info',
      data: {
        name: 'LedFx Frontend',
        type: 'controller'
      }
    }));
  }
};
```

### 2. Triggering Configuration Sync

#### Old System (Insecure REST)
```javascript
// Send sync notification via REST
async function notifyConfigChange() {
  await fetch('http://localhost:8888/api/clients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action: 'sync',
      client_id: clientId  // ⚠️ Can be spoofed
    })
  });
}

// When scene changes, colors updated, etc.
notifyConfigChange();
```

#### New System (Secure WebSocket)
```javascript
// Send sync notification via WebSocket broadcast
function notifyConfigChange(changeType, details = {}) {
  ws.send(JSON.stringify({
    id: getNextMessageId(),
    type: 'broadcast',
    data: {
      broadcast_type: 'scene_sync',  // Or 'color_palette', 'custom'
      target: { mode: 'all' },
      payload: {
        action: 'sync',
        ...details
      }
    }
  }));
}

// When scene changes
notifyConfigChange('scene', { scene_id: 'party-mode' });

// When colors updated
ws.send(JSON.stringify({
  id: getNextMessageId(),
  type: 'broadcast',
  data: {
    broadcast_type: 'color_palette',
    target: { mode: 'all' },
    payload: { colors: ['#FF0000', '#00FF00', '#0000FF'] }
  }
}));
```

### 3. Subscribing to Sync Events

#### Old System
```javascript
// Subscribe to legacy client_sync event
ws.send(JSON.stringify({
  id: 1,
  type: 'subscribe_event',
  event_type: 'client_sync'
}));

// Handle sync events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.event_type === 'client_sync') {
    console.log('Sync from:', data.client_id);  // ⚠️ Unverified
    refreshConfiguration();
  }
};
```

#### New System
```javascript
// Subscribe to new client_broadcast event
ws.send(JSON.stringify({
  id: 1,
  type: 'subscribe_event',
  event_type: 'client_broadcast'
}));

// Subscribe to clients_updated for client list changes
ws.send(JSON.stringify({
  id: 2,
  type: 'subscribe_event',
  event_type: 'clients_updated'
}));

// Handle broadcast events
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.event_type === 'client_broadcast') {
    // REQUIRED: Check if broadcast is for us
    // All subscribers receive all broadcasts - must filter client-side
    if (!data.target_uuids || !data.target_uuids.includes(clientId)) {
      return; // Not for us
    }

    // OPTIONAL: Filter out our own broadcasts
    if (data.sender_uuid === clientId) {
      return;
    }

    // ✅ Server-verified sender identity
    console.log('Broadcast from:', data.sender_name, data.sender_type);

    // Handle by broadcast type
    switch (data.broadcast_type) {
      case 'scene_sync':
        refreshConfiguration();
        break;
      case 'color_palette':
        updateColorPalette(data.payload.colors);
        break;
      case 'visualiser_control':
        handleVisualiserControl(data.payload);
        break;
    }
  }

  if (data.event_type === 'clients_updated') {
    // Client connected/disconnected
    refreshClientList();
  }
};
```

### 4. Getting Client List

#### Old System
```javascript
async function getClients() {
  const response = await fetch('http://localhost:8888/api/clients');
  const data = await response.json();

  // Old format: { "uuid": "ip_address" }
  const clients = data.result;
  Object.entries(clients).forEach(([uuid, ip]) => {
    console.log(`${uuid}: ${ip}`);
  });
}
```

#### New System (Breaking Change)
```javascript
async function getClients() {
  const response = await fetch('http://localhost:8888/api/clients');
  const data = await response.json();

  // New format: { "uuid": { metadata_object } }
  const clients = data.result;
  Object.entries(clients).forEach(([uuid, metadata]) => {
    console.log(`${metadata.name} (${metadata.type}) - ${metadata.ip}`);
  });

  return clients;
}
```

## Step-by-Step Migration Instructions

### Step 1: Add Client Metadata Registration

**Location**: Where WebSocket connection is established (likely in a WebSocket service/manager)

**Action**: After receiving `client_id` event, send `set_client_info`

```javascript
// Example: In your WebSocket connection handler
handleClientId(data) {
  this.clientId = data.client_id;

  // NEW: Register this client
  this.send({
    id: 1,
    type: 'set_client_info',
    data: {
      name: 'LedFx Frontend',
      type: 'controller'
    }
  });
}
```

### Step 2: Update Event Subscriptions

**Location**: Where event subscriptions are registered

**Action**: Replace `client_sync` with `client_broadcast` and `clients_updated`

```javascript
// OLD - Remove this
this.subscribeToEvent('client_sync');

// NEW - Add these
this.subscribeToEvent('client_broadcast');
this.subscribeToEvent('clients_updated');
```

### Step 3: Replace REST sync calls with WebSocket broadcasts

**Location**: Anywhere calling `POST /api/clients` with action "sync"

**Action**: Replace with WebSocket broadcast messages

```javascript
// OLD - Remove this function
async function notifySync() {
  await fetch('/api/clients', {
    method: 'POST',
    body: JSON.stringify({
      action: 'sync',
      client_id: this.clientId
    })
  });
}

// NEW - Add this function
function broadcastSync(details = {}) {
  this.ws.send(JSON.stringify({
    id: this.getNextMessageId(),
    type: 'broadcast',
    data: {
      broadcast_type: 'scene_sync',
      target: { mode: 'all' },
      payload: {
        action: 'sync',
        ...details
      }
    }
  }));
}
```

**Common trigger points to update:**
- Scene activation/deactivation
- Device configuration changes
- Effect changes
- Color palette updates
- Preset changes
- Any change that other clients should be notified about

### Step 4: Update Event Handlers

**Location**: WebSocket message handler

**Action**: Replace `client_sync` handler with `client_broadcast` handler

```javascript
// OLD - Remove this
handleMessage(data) {
  if (data.event_type === 'client_sync') {
    console.log('Sync from:', data.client_id);
    this.refreshConfiguration();
  }
}

// NEW - Add this
handleMessage(data) {
  if (data.event_type === 'client_broadcast') {
    // Skip our own broadcasts
    if (data.sender_uuid === this.clientId) {
      return;
    }

    // Handle by broadcast type
    switch (data.broadcast_type) {
      case 'scene_sync':
        console.log(`Sync from ${data.sender_name}`);
        this.refreshConfiguration();
        break;

      case 'color_palette':
        this.updateColorPalette(data.payload.colors);
        break;

      case 'visualiser_control':
        this.handleVisualiserControl(data.payload);
        break;
    }
  }

  // NEW: Handle client list changes
  if (data.event_type === 'clients_updated') {
    this.refreshClientList();
  }
}
```

### Step 5: Update GET /api/clients Usage

**Location**: Anywhere fetching the client list

**Action**: Update to handle new metadata object format

```javascript
// OLD
async function loadClients() {
  const response = await fetch('/api/clients');
  const data = await response.json();

  // data.result is { "uuid": "ip" }
  this.clients = data.result;

  Object.entries(this.clients).forEach(([uuid, ip]) => {
    this.renderClient(uuid, ip);
  });
}

// NEW
async function loadClients() {
  const response = await fetch('/api/clients');
  const data = await response.json();

  // data.result is { "uuid": { metadata_object } }
  this.clients = data.result;

  Object.entries(this.clients).forEach(([uuid, metadata]) => {
    this.renderClient(uuid, metadata.name, metadata.type, metadata.ip);
  });
}
```

### Step 6: Add Client List UI (Optional Enhancement)

```javascript
// NEW: Display connected clients with metadata
function renderClientList(clients) {
  const html = Object.entries(clients).map(([uuid, meta]) => `
    <div class="client-item">
      <span class="client-name">${meta.name}</span>
      <span class="client-type badge">${meta.type}</span>
      <span class="client-ip">${meta.ip}</span>
      <span class="client-time">Connected: ${formatTime(meta.connected_at)}</span>
    </div>
  `).join('');

  document.getElementById('client-list').innerHTML = html;
}
```

## Testing Checklist

Use this checklist to verify migration is complete:

### Functional Testing
- [ ] Frontend connects and receives client_id
- [ ] Frontend sends set_client_info successfully
- [ ] Frontend appears in GET /api/clients with correct metadata
- [ ] Making changes in frontend triggers broadcasts
- [ ] Other clients receive broadcasts and update
- [ ] Broadcasts show correct sender_name and sender_type
- [ ] Client list updates when clients connect/disconnect
- [ ] No client_sync events are being subscribed to
- [ ] No POST /api/clients sync calls are being made

### Security Testing
- [ ] Verify sender_uuid cannot be spoofed (matches WebSocket connection)
- [ ] Verify frontend doesn't send sender_id in broadcast requests
- [ ] Verify broadcasts are only received by intended targets

### Browser Console Testing
```javascript
// 1. Check no legacy client_sync subscriptions
// Look for: subscribe_event with event_type: "client_sync"
// Should find: NONE

// 2. Check new subscriptions exist
// Look for: subscribe_event with event_type: "client_broadcast"
// Look for: subscribe_event with event_type: "clients_updated"
// Should find: BOTH

// 3. Check no legacy sync REST calls
// Look for: POST /api/clients with action: "sync"
// Should find: NONE

// 4. Check new broadcast messages
// Look for: type: "broadcast" with broadcast_type and target
// Should find: When making configuration changes
```

### Network Tab Verification
- [ ] No POST requests to /api/clients with action=sync
- [ ] WebSocket messages show type: "broadcast"
- [ ] GET /api/clients returns metadata objects (not IP strings)

## Legacy Code Removal Checklist

**⚠️ Only perform after frontend migration is complete and tested!**

### Backend Cleanup

#### File: `ledfx/api/clients.py`
```python
# REMOVE: The entire POST handler or just the sync action

# Remove from imports:
from ledfx.events import ClientSyncEvent  # DELETE THIS LINE

# Remove from post() method:
if action == "sync":  # DELETE THIS BLOCK
    client_id = data.get("client_id", "unknown")
    self._ledfx.events.fire_event(ClientSyncEvent(client_id))

# If "sync" was the only action, remove entire post() method
# Otherwise, remove "sync" from ACTIONS list:
ACTIONS = ["sync"]  # DELETE THIS if no other actions remain
```

#### File: `ledfx/events.py`
```python
# REMOVE: ClientSyncEvent class
class ClientSyncEvent(Event):  # DELETE ENTIRE CLASS
    """Client requested configuration sync"""

    def __init__(self, client_id):
        super().__init__(Event.CLIENT_SYNC)
        self.client_id = client_id

# REMOVE: CLIENT_SYNC constant
class Event:
    # ... other constants ...
    CLIENT_SYNC = "client_sync"  # DELETE THIS LINE
```

#### Documentation
- [ ] Remove legacy sync documentation from `docs/apis/websocket.md`
- [ ] Update changelog to note removal

### Frontend Cleanup

```javascript
// REMOVE: All client_sync event handling
ws.onmessage = (event) => {
  if (data.event_type === 'client_sync') {  // DELETE THIS BLOCK
    // ... handler code ...
  }
};

// REMOVE: client_sync subscriptions
ws.send(JSON.stringify({
  type: 'subscribe_event',
  event_type: 'client_sync'  // DELETE THIS
}));

// REMOVE: sync REST endpoint calls
fetch('/api/clients', {
  method: 'POST',
  body: JSON.stringify({
    action: 'sync',  // DELETE THIS ENTIRE CALL
    client_id: clientId
  })
});
```

## Migration Example: Real-World Scenario

### Scenario: Scene Activation Notification

**Before Migration:**
```javascript
// scenes.js or similar
async function activateScene(sceneId) {
  // Activate scene on backend
  await fetch(`/api/scenes/${sceneId}/activate`, { method: 'POST' });

  // Notify other clients via legacy sync
  await fetch('/api/clients', {
    method: 'POST',
    body: JSON.stringify({
      action: 'sync',
      client_id: this.clientId  // ⚠️ Insecure
    })
  });
}

// websocket.js or similar
handleMessage(data) {
  if (data.event_type === 'client_sync') {
    // Another client changed something, reload scenes
    this.loadScenes();
  }
}
```

**After Migration:**
```javascript
// scenes.js or similar
async function activateScene(sceneId) {
  // Activate scene on backend
  await fetch(`/api/scenes/${sceneId}/activate`, { method: 'POST' });

  // Notify other clients via secure broadcast
  this.websocket.send(JSON.stringify({
    id: this.getNextMessageId(),
    type: 'broadcast',
    data: {
      broadcast_type: 'scene_sync',
      target: { mode: 'all' },
      payload: {
        action: 'activated',
        scene_id: sceneId
      }
    }
  }));
}

// websocket.js or similar
handleMessage(data) {
  if (data.event_type === 'client_broadcast') {
    // Skip our own broadcasts
    if (data.sender_uuid === this.clientId) {
      return;
    }

    if (data.broadcast_type === 'scene_sync') {
      // Another client changed scenes
      console.log(`${data.sender_name} activated scene: ${data.payload.scene_id}`);
      this.loadScenes();
    }
  }
}
```

## Broadcast Type Guidelines

Choose the appropriate `broadcast_type` for your use case:

| Broadcast Type | Use Case | Example Payload |
|----------------|----------|-----------------|
| `scene_sync` | Scene activation, deactivation | `{ action: 'activated', scene_id: 'party' }` |
| `color_palette` | Color scheme updates | `{ colors: ['#FF0000', '#00FF00'] }` |
| `visualiser_control` | Display control commands | `{ brightness: 80, effect: 'rainbow' }` |
| `custom` | Application-specific messages | `{ custom_data: {...} }` |

## Support & Questions

- **Documentation**: See `docs/apis/websocket.md` for full API reference
- **Examples**: See `docs/developer/websocket_client_examples.md` for code examples
- **Issues**: If migration issues arise, file a GitHub issue with the `migration` label

## Summary

### Key Changes
1. ✅ Client metadata registration via `set_client_info`
2. ✅ WebSocket broadcasts replace REST sync endpoint
3. ✅ Subscribe to `client_broadcast` instead of `client_sync`
4. ✅ GET /api/clients returns metadata objects
5. ✅ Server-verified sender identity (security improvement)

### Migration Path
1. Frontend: Implement new WebSocket-based system
2. Frontend: Test thoroughly with new system
3. Frontend: Remove all legacy client_sync code
4. Backend: Remove POST /api/clients sync action
5. Backend: Remove ClientSyncEvent and CLIENT_SYNC constant
6. Documentation: Update to reflect removal

### Timeline
- **Now**: Backend complete, frontend migration in progress
- **Next**: Complete frontend migration and testing
- **Future**: Remove legacy code once migration verified
