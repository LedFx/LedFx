# WebSocket Client - Usage Examples

This document provides practical examples for implementing the WebSocket client management features in LedFx.

> **Migrating from Legacy System?** If you're updating code that uses the old `POST /api/clients` sync action or `client_sync` events, see the [Client Sync Migration Guide](client_sync_migration_guide.md) for step-by-step migration instructions.
> **📊 Lifecycle Diagrams**: This document includes Mermaid sequence diagrams throughout to visualize key interaction patterns.

## Table of Contents
- [Basic Client Setup](#basic-client-setup)
- [Metadata Management](#metadata-management)
- [Broadcasting Messages](#broadcasting-messages)
- [Event Handling](#event-handling)
- [Complete Example Applications](#complete-example-applications)

## Basic Client Setup

### Lifecycle: Client Connection & Registration

```{mermaid}
sequenceDiagram
    participant Client
    participant WebSocket
    participant Server

    Client->>WebSocket: Connect to ws://localhost:8888/api/websocket
    WebSocket->>Server: WebSocket Connection Established
    Server->>WebSocket: client_id event {client_id: "abc-123"}
    WebSocket->>Client: onmessage: client_id received
    Note over Client: Store client_id
    Client->>WebSocket: set_client_info {name, type, device_id}
    Server->>Server: Validate & store metadata
    Server->>WebSocket: client_info_updated event
    WebSocket->>Client: onmessage: Registration confirmed
    Note over Client: Client is now registered
    Server->>Server: Fire ClientsUpdatedEvent
    Server-->>WebSocket: clients_updated event (to subscribers)
```

```
const websocket = new WebSocket('ws://localhost:8888/api/websocket');
let myClientId = null;

websocket.onopen = () => {
  console.log('WebSocket connected');
};

websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // First message will be our client ID
  if (data.event_type === 'client_id') {
    myClientId = data.client_id;
    console.log('Received client ID:', myClientId);

    // Now set our metadata
    setClientInfo();
  }
};

function setClientInfo() {
  websocket.send(JSON.stringify({
    id: 1,
    type: 'set_client_info',
    data: {
      name: 'My Application',
      type: 'controller',
      device_id: 'my-device-123'
    }
  }));
}
```

## Metadata Management

### Lifecycle: Name Conflict Resolution

```{mermaid}
sequenceDiagram
    participant Client1
    participant Client2
    participant Server

    Note over Client1: Already registered as "Display"
    Client2->>Server: set_client_info {name: "Display"}
    Server->>Server: Check name uniqueness
    Server->>Server: Name exists! Append " (2)"
    Server->>Client2: client_info_updated {name: "Display (2)", name_conflict: true}
    Note over Client2: Notify user of name change

    alt Another client with same name
        Client2->>Server: set_client_info {name: "Display"}
        Server->>Server: "Display" and "Display (2)" exist
        Server->>Server: Append " (3)"
        Server->>Client2: client_info_updated {name: "Display (3)", name_conflict: true}
    end
```

### Setting Client Info with Error Handling

```
// Helper: Generate unique message IDs
let messageIdCounter = 1;
function getNextMessageId() {
  return messageIdCounter++;
}
function setClientInfo(name, type, deviceId = null) {
  const messageId = getNextMessageId();

  websocket.send(JSON.stringify({
    id: messageId,
    type: 'set_client_info',
    data: {
      name: name,
      type: type,
      device_id: deviceId
    }
  }));

  // Handle response
  return new Promise((resolve, reject) => {
    const handler = (event) => {
      const data = JSON.parse(event.data);

      if (data.id === messageId) {
        if (data.event_type === 'client_info_updated') {
          console.log('Metadata set:', data);

          if (data.name_conflict) {
            console.warn(`Name conflict: "${name}" changed to "${data.name}"`);
          }

          cleanup();
          resolve(data);
        } else if (data.success === false) {
          console.error('Failed to set metadata:', data.error);
          cleanup();
          reject(data.error);
        }
      }
    };

    const closeHandler = () => {
      cleanup();
      reject(new Error('WebSocket connection closed'));
    };

    const cleanup = () => {
      websocket.removeEventListener('message', handler);
      websocket.removeEventListener('close', closeHandler);
      clearTimeout(timeoutId);
    };

    // Timeout after 5 seconds
    const timeoutId = setTimeout(() => {
      cleanup();
      reject(new Error('Request timeout'));
    }, 5000);

    websocket.addEventListener('message', handler);
    websocket.addEventListener('close', closeHandler);
  });
}

// Usage
setClientInfo('Living Room Display', 'visualiser', 'esp32-001')
  .then(result => {
    console.log('Successfully registered as:', result.name);
  })
  .catch(error => {
    console.error('Registration failed:', error);
  });
```

### Updating Client Metadata

You can update client name and/or type after initial connection:

```
function updateClientInfo(newName, newType) {
  const messageId = getNextMessageId();
  const data = {};

  if (newName !== undefined) {
    data.name = newName;
  }

  if (newType !== undefined) {
    data.type = newType;
  }

  websocket.send(JSON.stringify({
    id: messageId,
    type: 'update_client_info',
    data: data
  }));
}

// Example: Update name only
updateClientInfo('New Display Name', undefined);

// Example: Update type only
updateClientInfo(undefined, 'visualiser');

// Example: Update both name and type
updateClientInfo('Bedroom Display', 'display');

// Example: Update name when user changes it in UI
document.getElementById('nameInput').addEventListener('change', (e) => {
  updateClientInfo(e.target.value, undefined);
});

// Example: Update type when user selects from dropdown
document.getElementById('typeSelect').addEventListener('change', (e) => {
  updateClientInfo(undefined, e.target.value);
});
```

### Fetching Client List

```
async function getConnectedClients() {
  const response = await fetch('http://localhost:8888/api/clients');
  const data = await response.json();

  // data.result contains the client metadata dictionary
  const clients = data.result;

  Object.entries(clients).forEach(([uuid, metadata]) => {
    console.log(`Client ${uuid}:`, {
      name: metadata.name,
      type: metadata.type,
      ip: metadata.ip,
      connected: new Date(metadata.connected_at * 1000).toLocaleString()
    });
  });

  return clients;
}

// Usage
getConnectedClients().then(clients => {
  console.log(`${Object.keys(clients).length} clients connected`);
});
```

## Broadcasting Messages

### Lifecycle: Broadcasting to All Clients

```{mermaid}
sequenceDiagram
    participant Sender
    participant Server
    participant Client1
    participant Client2
    participant Client3

    Sender->>Server: broadcast {broadcast_type: "scene_sync", target: {mode: "all"}, payload: {...}}
    Server->>Server: Validate broadcast<br/>Derive sender identity from WebSocket
    Server->>Server: Generate broadcast_id
    Server->>Sender: broadcast_sent {targets_matched: 3, target_uuids: [...]}

    par Broadcast to all subscribers
        Server->>Client1: client_broadcast event {sender_uuid, sender_name, payload}
        Server->>Client2: client_broadcast event {sender_uuid, sender_name, payload}
        Server->>Client3: client_broadcast event {sender_uuid, sender_name, payload}
    end

    Note over Client1,Client3: Each client filters:<br/>1. Check target_uuids includes them<br/>2. Skip if sender_uuid == own client_id
```

### Broadcasting to All Clients

```
function broadcastToAll(messageType, payload) {
  const messageId = getNextMessageId();

  websocket.send(JSON.stringify({
    id: messageId,
    type: 'broadcast',
    data: {
      broadcast_type: messageType,
      target: {
        mode: 'all'
      },
      payload: payload
    }
  }));
}

// Example: Broadcast scene change
broadcastToAll('scene_sync', {
  scene_id: 'party-mode',
  action: 'activate'
});
```

### Lifecycle: Targeted Broadcasting (By Type)

```{mermaid}
sequenceDiagram
    participant Controller
    participant Server
    participant Visualiser1
    participant Visualiser2
    participant Mobile

    Note over Visualiser1: type: "visualiser"
    Note over Visualiser2: type: "visualiser"
    Note over Mobile: type: "mobile"

    Controller->>Server: broadcast {broadcast_type: "visualiser_control",<br/>target: {mode: "type", value: "visualiser"}}
    Server->>Server: Filter clients by type="visualiser"
    Server->>Controller: broadcast_sent {targets_matched: 2}

    par Broadcast to matching type only
        Server->>Visualiser1: client_broadcast event
        Server->>Visualiser2: client_broadcast event
    end

    Note over Mobile: No broadcast received<br/>(type doesn't match)
```

### Broadcasting to Specific Client Types

```
function broadcastToVisualisers(payload) {
  websocket.send(JSON.stringify({
    id: getNextMessageId(),
    type: 'broadcast',
    data: {
      broadcast_type: 'visualiser_control',
      target: {
        mode: 'type',
        value: 'visualiser'
      },
      payload: payload
    }
  }));
}

// Example: Send color palette to all visualisers
broadcastToVisualisers({
  colors: ['#FF0000', '#00FF00', '#0000FF'],
  transition: 'fade',
  duration: 2000
});
```

### Broadcasting to Specific Clients by Name

```
function broadcastToNamedClients(names, payload) {
  websocket.send(JSON.stringify({
    id: getNextMessageId(),
    type: 'broadcast',
    data: {
      broadcast_type: 'custom',
      target: {
        mode: 'names',
        names: names
      },
      payload: payload
    }
  }));
}

// Example: Send command to specific displays
broadcastToNamedClients(
  ['Living Room Display', 'Bedroom Display'],
  {
    brightness: 80,
    effect: 'rainbow'
  }
);
```

### Broadcasting with Response Handling

```
function broadcastWithConfirmation(broadcastType, target, payload) {
  const messageId = getNextMessageId();

  websocket.send(JSON.stringify({
    id: messageId,
    type: 'broadcast',
    data: {
      broadcast_type: broadcastType,
      target: target,
      payload: payload
    }
  }));

  return new Promise((resolve, reject) => {
    const handler = (event) => {
      const data = JSON.parse(event.data);

      if (data.id === messageId) {
        if (data.event_type === 'broadcast_sent') {
          console.log(`Broadcast ${data.broadcast_id} sent to ${data.targets_matched} clients`);
          cleanup();
          resolve(data);
        } else if (data.success === false) {
          console.error('Broadcast failed:', data.error);
          cleanup();
          reject(data.error);
        }
      }
    };

    const closeHandler = () => {
      cleanup();
      reject(new Error('WebSocket connection closed'));
    };

    const cleanup = () => {
      websocket.removeEventListener('message', handler);
      websocket.removeEventListener('close', closeHandler);
      clearTimeout(timeoutId);
    };

    // Timeout after 5 seconds
    const timeoutId = setTimeout(() => {
      cleanup();
      reject(new Error('Request timeout'));
    }, 5000);

    websocket.addEventListener('message', handler);
    websocket.addEventListener('close', closeHandler);
  });
}

// Usage
broadcastWithConfirmation('scene_sync', {mode: 'all'}, {scene: 'chill'})
  .then(result => {
    console.log(`Delivered to ${result.target_uuids.length} clients`);
  })
  .catch(error => {
    console.error('Broadcast error:', error.message);
  });
```

## Event Handling

### Lifecycle: Client List Change Notification

```{mermaid}
sequenceDiagram
    participant ClientA
    participant Server
    participant ClientB
    participant NewClient

    Note over ClientA,ClientB: Already connected & subscribed to clients_updated

    NewClient->>Server: WebSocket Connect
    Server->>NewClient: client_id event
    NewClient->>Server: set_client_info
    Server->>Server: Update client metadata
    Server->>Server: Fire ClientsUpdatedEvent

    par Notify all subscribers
        Server->>ClientA: clients_updated event
        Server->>ClientB: clients_updated event
    end

    Note over ClientA: Refresh client list via<br/>GET /api/clients
    Note over ClientB: Update UI with new client

    ClientA->>Server: GET /api/clients
    Server->>ClientA: Full client list with metadata
```

### Lifecycle: Receiving and Filtering Broadcasts

```{mermaid}
sequenceDiagram
    participant Sender
    participant Server
    participant Receiver
    participant OtherClient

    Note over Receiver: client_id: "abc-123"<br/>Subscribed to client_broadcast
    Note over OtherClient: client_id: "xyz-789"<br/>Subscribed to client_broadcast

    Sender->>Server: broadcast {target: {mode: "uuids", uuids: ["abc-123"]}}
    Server->>Server: Determine targets<br/>for audit & response

    par Broadcast to ALL subscribers
        Server->>Receiver: client_broadcast {target_uuids: ["abc-123"]}
        Server->>OtherClient: client_broadcast {target_uuids: ["abc-123"]}
    end

    Receiver->>Receiver: Check: "abc-123" in target_uuids? ✓
    Receiver->>Receiver: Check: sender_uuid != "abc-123"? ✓
    Note over Receiver: Process broadcast payload

    OtherClient->>OtherClient: Check: "xyz-789" in target_uuids? ✗
    Note over OtherClient: Discard (not in target list)

    alt Sender receives their own broadcast
        Sender->>Sender: Check: sender_uuid == own client_id?
        Note over Sender: Skip processing (own broadcast)
    end
```

### Subscribing to Client Events

```
// Subscribe to clients_updated event
websocket.send(JSON.stringify({
  id: getNextMessageId(),
  type: 'subscribe_event',
  event_type: 'clients_updated'
}));

// Subscribe to client_broadcast event
websocket.send(JSON.stringify({
  id: getNextMessageId(),
  type: 'subscribe_event',
  event_type: 'client_broadcast'
}));
```

### Handling Client List Changes

```
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.event_type === 'clients_updated') {
    console.log('Client list changed, refreshing...');
    refreshClientList();
  }
};

async function refreshClientList() {
  const clients = await getConnectedClients();
  updateClientListUI(clients);
}

function updateClientListUI(clients) {
  const listElement = document.getElementById('clientList');
  listElement.innerHTML = '';

  Object.entries(clients).forEach(([uuid, metadata]) => {
    const item = document.createElement('div');
    item.className = 'client-item';

    // Safely create name element
    const nameElement = document.createElement('strong');
    nameElement.textContent = metadata.name;
    item.appendChild(nameElement);

    // Safely create type badge
    const typeElement = document.createElement('span');
    typeElement.className = 'badge';
    typeElement.textContent = metadata.type;
    item.appendChild(typeElement);

    // Safely create IP element
    const ipElement = document.createElement('span');
    ipElement.className = 'ip';
    ipElement.textContent = metadata.ip;
    item.appendChild(ipElement);

    listElement.appendChild(item);
  });
}
```

### Receiving Broadcasts

**Important:** Broadcast events are sent to ALL subscribers of `client_broadcast`. You MUST filter by `target_uuids` to determine if the message is intended for you. This is client-side filtering - the server does not selectively send to specific connections.

```
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.event_type === 'client_broadcast') {
    // REQUIRED: Check if this broadcast is for us
    // All subscribers receive this event - we must filter client-side
    if (!Array.isArray(data.target_uuids) || !data.target_uuids.includes(myClientId)) {
      return; // Not for us - discard
    }

    // OPTIONAL: Filter out our own broadcasts
    if (data.sender_uuid === myClientId) {
      return; // We sent this - discard
    }

    console.log(`Broadcast from ${data.sender_name}:`, data.payload);

    // Handle based on broadcast type
    switch (data.broadcast_type) {
      case 'scene_sync':
        handleSceneSync(data.payload);
        break;
      case 'color_palette':
        handleColorPalette(data.payload);
        break;
      case 'visualiser_control':
        handleVisualiserControl(data.payload);
        break;
      case 'custom':
        handleCustomBroadcast(data.payload);
        break;
    }
  }
};

function handleSceneSync(payload) {
  console.log('Scene sync received:', payload.scene_id);
  // Activate the scene
  activateScene(payload.scene_id);
}

function handleColorPalette(payload) {
  console.log('Color palette received:', payload.colors);
  // Update color scheme
  updateColors(payload.colors);
}
```

## Complete Example Applications

### Lifecycle: End-to-End Scene Sync (Controller → Visualisers)

```{mermaid}
sequenceDiagram
    participant Controller
    participant Server
    participant Visualiser1
    participant Visualiser2

    Note over Controller,Visualiser2: Initial Setup

    Controller->>Server: Connect & set_client_info (type: "controller")
    Visualiser1->>Server: Connect & set_client_info (type: "visualiser")
    Visualiser2->>Server: Connect & set_client_info (type: "visualiser")

    Controller->>Server: subscribe_event: clients_updated
    Visualiser1->>Server: subscribe_event: client_broadcast
    Visualiser2->>Server: subscribe_event: client_broadcast

    Note over Controller,Visualiser2: User Activates Scene in Controller

    Controller->>Server: POST /api/scenes/party-mode/activate
    Server->>Controller: Scene activated successfully

    Controller->>Server: broadcast {<br/>  broadcast_type: "scene_sync",<br/>  target: {mode: "type", value: "visualiser"},<br/>  payload: {scene_id: "party-mode", action: "activate"}<br/>}

    Server->>Server: Filter clients by type="visualiser"
    Server->>Server: Derive sender from WebSocket (Controller)
    Server->>Controller: broadcast_sent {targets_matched: 2}

    par Notify visualisers
        Server->>Visualiser1: client_broadcast {<br/>  sender_name: "Scene Controller",<br/>  sender_type: "controller",<br/>  broadcast_type: "scene_sync",<br/>  payload: {scene_id: "party-mode"}<br/>}
        Server->>Visualiser2: client_broadcast {<br/>  sender_name: "Scene Controller",<br/>  sender_type: "controller",<br/>  broadcast_type: "scene_sync",<br/>  payload: {scene_id: "party-mode"}<br/>}
    end

    Visualiser1->>Visualiser1: Check broadcast_type == "scene_sync"
    Visualiser1->>Visualiser1: activateScene("party-mode")
    Note over Visualiser1: Display updates to party mode

    Visualiser2->>Visualiser2: Check broadcast_type == "scene_sync"
    Visualiser2->>Visualiser2: activateScene("party-mode")
    Note over Visualiser2: Display updates to party mode
```

### Controller Application

A controller app that manages scenes and broadcasts to visualisers:

```
class LedFxController {
  constructor(wsUrl = 'ws://localhost:8888/api/websocket') {
    this.wsUrl = wsUrl;
    this.websocket = null;
    this.clientId = null;
    this.messageId = 1;
    this.registrationMessageId = null;
    this.connectedClients = {};
  }

  connect() {
    this.websocket = new WebSocket(this.wsUrl);

    this.websocket.onopen = () => {
      console.log('Controller connected');
    };

    this.websocket.onmessage = (event) => {
      this.handleMessage(JSON.parse(event.data));
    };

    this.websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  handleMessage(data) {
    switch (data.event_type) {
      case 'client_id':
        this.clientId = data.client_id;
        this.registerAsController();
        this.subscribeToEvents();
        break;

      case 'client_info_updated':
        if (data.id === this.registrationMessageId) {
          console.log('Registered as controller:', data.name);
          this.refreshClientList().catch(err =>
            console.error('Failed to refresh client list:', err)
          );
        }
        break;

      case 'clients_updated':
        this.refreshClientList().catch(err =>
          console.error('Failed to refresh client list:', err)
        );
        break;

      case 'broadcast_sent':
        console.log(`Broadcast delivered to ${data.targets_matched} clients`);
        break;
    }
  }

  registerAsController() {
    this.registrationMessageId = this.messageId;
    this.send({
      id: this.messageId++,
      type: 'set_client_info',
      data: {
        name: 'Scene Controller',
        type: 'controller'
      }
    });
  }

  subscribeToEvents() {
    this.send({
      id: this.messageId++,
      type: 'subscribe_event',
      event_type: 'clients_updated'
    });
  }

  async refreshClientList() {
    const response = await fetch('http://localhost:8888/api/clients');
    const data = await response.json();
    this.connectedClients = data.result;
    console.log('Connected clients:', Object.keys(this.connectedClients).length);
  }

  activateScene(sceneId) {
    console.log(`Activating scene: ${sceneId}`);

    // Broadcast to all visualisers
    this.send({
      id: this.messageId++,
      type: 'broadcast',
      data: {
        broadcast_type: 'scene_sync',
        target: {
          mode: 'type',
          value: 'visualiser'
        },
        payload: {
          scene_id: sceneId,
          action: 'activate',
          timestamp: Date.now()
        }
      }
    });
  }

  updateColorPalette(colors) {
    this.send({
      id: this.messageId++,
      type: 'broadcast',
      data: {
        broadcast_type: 'color_palette',
        target: { mode: 'all' },
        payload: { colors: colors }
      }
    });
  }

  send(message) {
    this.websocket.send(JSON.stringify(message));
  }
}

// Usage
const controller = new LedFxController();
controller.connect();

// Later: activate a scene
setTimeout(() => {
  controller.activateScene('party-mode');
}, 5000);
```

### Visualiser Application

A visualiser app that receives broadcasts and updates display:

```
class LedFxVisualiser {
  constructor(name, wsUrl = 'ws://localhost:8888/api/websocket') {
    this.name = name;
    this.wsUrl = wsUrl;
    this.websocket = null;
    this.clientId = null;
    this.messageId = 1;
  }

  connect() {
    this.websocket = new WebSocket(this.wsUrl);

    this.websocket.onopen = () => {
      console.log('Visualiser connected');
    };

    this.websocket.onmessage = (event) => {
      this.handleMessage(JSON.parse(event.data));
    };
  }

  handleMessage(data) {
    switch (data.event_type) {
      case 'client_id':
        this.clientId = data.client_id;
        this.registerAsVisualiser();
        this.subscribeToBroadcasts();
        break;

      case 'client_info_updated':
        console.log('Registered as:', data.name);
        break;

      case 'client_broadcast':
        this.handleBroadcast(data);
        break;
    }
  }

  registerAsVisualiser() {
    this.send({
      id: this.messageId++,
      type: 'set_client_info',
      data: {
        name: this.name,
        type: 'visualiser'
      }
    });
  }

  subscribeToBroadcasts() {
    this.send({
      id: this.messageId++,
      type: 'subscribe_event',
      event_type: 'client_broadcast'
    });
  }

  handleBroadcast(data) {
    // REQUIRED: Client-side filtering
    // All subscribers receive this event - we must check target_uuids
    if (!Array.isArray(data.target_uuids) || !data.target_uuids.includes(this.clientId)) {
      return; // Not intended for us
    }

    // OPTIONAL: Ignore our own broadcasts
    if (data.sender_uuid === this.clientId) {
      return;
    }

    console.log(`Broadcast from ${data.sender_name}:`, data.broadcast_type);

    switch (data.broadcast_type) {
      case 'scene_sync':
        this.activateScene(data.payload.scene_id);
        break;

      case 'color_palette':
        this.updateColors(data.payload.colors);
        break;

      case 'visualiser_control':
        this.handleControl(data.payload);
        break;
    }
  }

  activateScene(sceneId) {
    console.log(`Activating scene: ${sceneId}`);
    // Implementation: activate the scene on this visualiser
  }

  updateColors(colors) {
    console.log('Updating color palette:', colors);
    // Implementation: update display colors
  }

  handleControl(command) {
    console.log('Control command:', command);
    // Implementation: handle visualiser control
  }

  send(message) {
    this.websocket.send(JSON.stringify(message));
  }
}

// Usage
const visualiser = new LedFxVisualiser('Living Room Display');
visualiser.connect();
```

## Best Practices

### 1. Always Set Client Metadata
Always call `set_client_info` after receiving your client ID to enable proper identification.

### 2. Handle Name Conflicts Gracefully
Check the `name_conflict` flag in responses and inform users if their chosen name was modified.

### 3. REQUIRED: Filter Broadcasts Client-Side
**Critical:** Broadcast events are sent to ALL subscribers. You MUST check if your UUID is in `target_uuids` before processing. This is not optional - the server does not restrict delivery to specific connections. Always filter out your own broadcasts as well.

### 4. Validate Payload Size
Keep broadcast payloads under 2048 bytes. For larger data, use REST API endpoints and broadcast just references.

### 5. Use Appropriate Broadcast Types
Choose the correct `broadcast_type` to help receivers handle messages appropriately:
- `scene_sync` - Scene activation/coordination
- `color_palette` - Color scheme updates
- `visualiser_control` - Display control commands
- `custom` - Application-specific messages

### 6. Subscribe to events
Subscribe to `clients_updated` to keep your client list synchronized.

### 7. Implement Reconnection Logic
```
function connectWithRetry(maxRetries = 5, delay = 1000) {
  let retries = 0;

  function connect() {
    const ws = new WebSocket('ws://localhost:8888/api/websocket');

    ws.onclose = () => {
      if (retries < maxRetries) {
        retries++;
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s...
        const backoffDelay = delay * Math.pow(2, retries - 1);
        console.log(`Reconnecting in ${backoffDelay}ms... (${retries}/${maxRetries})`);
        setTimeout(connect, backoffDelay);
      } else {
        console.error('Max reconnection attempts reached');
      }
    };

    return ws;
  }

  return connect();
}
```

#### Lifecycle: Reconnection with Exponential Backoff

```{mermaid}
sequenceDiagram
    participant Client
    participant WebSocket
    participant Server

    Client->>WebSocket: Initial Connection
    WebSocket->>Server: Connected
    Server->>Client: client_id event
    Note over Client: Store client_id, register metadata

    Note over Client,Server: Connection Active

    Server--xWebSocket: Connection Lost
    WebSocket->>Client: onclose event
    Note over Client: Retry 1: Wait 1s

    Client->>WebSocket: Reconnect Attempt 1
    WebSocket--xClient: Connection Failed
    WebSocket->>Client: onclose event
    Note over Client: Retry 2: Wait 2s

    Client->>WebSocket: Reconnect Attempt 2
    WebSocket--xClient: Connection Failed
    WebSocket->>Client: onclose event
    Note over Client: Retry 3: Wait 4s

    Client->>WebSocket: Reconnect Attempt 3
    WebSocket->>Server: Connected
    Server->>Client: NEW client_id event
    Note over Client: Store new client_id,<br/>re-register metadata,<br/>re-subscribe to events
    Note over Client: Connection Restored
```

## Troubleshooting

### Problem: Not Receiving Broadcasts
**Solution**: Ensure you've subscribed to the `client_broadcast` event:
```
websocket.send(JSON.stringify({
  id: 1,
  type: 'subscribe_event',
  event_type: 'client_broadcast'
}));
```

### Problem: Name Conflict Every Time
**Solution**: Check if another client is using your name. Consider adding a unique suffix:
```
const name = `My App ${Math.random().toString(36).substr(2, 4)}`;
```

### Problem: Broadcast Fails with "No targets matched"
**Solution**: Verify target specification is correct and target clients exist. Fetch client list to confirm:
```
const clients = await getConnectedClients();
console.log('Available clients:', Object.values(clients).map(c => c.name));
```

### Problem: Payload Too Large Error
**Solution**: Reduce payload size or split into multiple broadcasts:
```
// Instead of sending large data
const largePayload = { image: base64ImageData }; // Too large!

// Upload via REST and broadcast reference
const uploadResponse = await uploadImage(imageData);
broadcastToAll('custom', { image_id: uploadResponse.id });
```
