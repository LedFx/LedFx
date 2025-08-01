# WebSocket API

In addition to the REST APIs LedFx has a WebSocket API for streaming
realtime data. The primary use for this is for things like effect
visualizations in the frontend.

Will document this further once it is more well defined. The general
structure will be event registration based.

::: warning
The documentation on websockets need a LOT of legacy implementation.
New sections are added as new events are commited, but all the pre-existing behaviour is currently not documented
:::


## Websocket client UIDs

This functionality is intended to support notification between clients of connect / disconnect and sync actions

```{mermaid}
  sequenceDiagram
      participant Client
      participant ClientEndpoint as ClientEndpoint (/api/clients)
      participant WebSocketMgr as WebsocketConnection
      participant EventSystem as Event System

      Note over Client,EventSystem: WebSocket Connection Flow
      Client->>WebSocketMgr: Establish WebSocket connection
      WebSocketMgr->>WebSocketMgr: Extract client IP from request.remote
      WebSocketMgr->>WebSocketMgr: Generate UUID for client
      WebSocketMgr->>WebSocketMgr: Store UUID→IP mapping (thread-safe with map_lock)
      WebSocketMgr-->>Client: Send JSON {"event_type": "client_id", "client_id": UUID}
      WebSocketMgr->>EventSystem: Fire ClientConnectedEvent(UUID, IP)

      Note over Client,EventSystem: Client List Retrieval
      Client->>ClientEndpoint: GET /api/clients
      ClientEndpoint->>WebSocketMgr: get_all_clients()
      WebSocketMgr->>WebSocketMgr: Return copy of ip_uid_map (thread-safe)
      WebSocketMgr-->>ClientEndpoint: UUID→IP mapping dictionary
      ClientEndpoint-->>Client: HTTP 200 with {"result": client_list}

      Note over Client,EventSystem: Client Sync Action
      Client->>ClientEndpoint: POST /api/clients {"action": "sync", "client_id": UUID}
      ClientEndpoint->>ClientEndpoint: Validate JSON and action field
      ClientEndpoint->>EventSystem: Fire ClientSyncEvent(client_id or "unknown")
      ClientEndpoint-->>Client: HTTP 200 {"result": "success", "action": "sync"}

      Note over Client,EventSystem: WebSocket Disconnection Flow
      Client->>WebSocketMgr: Close WebSocket connection
      WebSocketMgr->>WebSocketMgr: Remove UUID from ip_uid_map (thread-safe with map_lock)
      WebSocketMgr->>EventSystem: Fire ClientDisconnectedEvent(UUID, IP)
```

On opening a websocket connection the client will be assigned a UID stored along with the client IP address. noting that mulitple client can exist on one IP address. Multiple browser tabs for example.

The assigned UID will be returned to the client via an event on the websocket of the following structure

``` json
{
  "event_type": "client_id",
  "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```

A client can store its own id to enable filtering out of events generated by itself.

### Client Events

The following events are available for a client to subscribe to via its websocket

#### client_connected

Generated when a new client is connected to the backend by its own websocket

``` json
{
  "event_type": "client_connected",
  "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c",
  "client_ip": "1.2.3.4"
}
```

#### client_disconnected

Generated when an existing client disconnects its websocket to the backend.

``` json
{
  "event_type": "client_disconnected",
  "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c",
  "client_ip": "1.2.3.4"
}
```

#### client_sync

Generated when a client makes a POST to the rest api endpoint /api/clients with "action": "sync"

This is intended to allow a client to inform other clients they should sync their configuration due to stimulated changes. The receiving client can filter against its own id to avoid self recursive notifications

``` json
{
  "event_type": "client_sync",
  "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```

### client rest api

The following rest api calls support client tracking

#### /api/clients

**GET**

Returns a list of all active websocket clients by UID and IP address

``` json
{
"823f78cd-24fa-4cd4-908f-979249350dea": "127.0.0.1",
"34361601-1416-428d-9b89-37c82281222d": "127.0.0.1",
"8743a845-40ba-4427-8ae6-361b2be6fac6": "1.2.3.4"
}
```

**POST**

Supports an extensible set of actions

##### "action": "sync"

Sync action can be used to inform other clients that they should sync their configurations to pick up changes made by the originating client.

Calling client should provide its own websocket id

``` json
{
   "action": "sync",
   "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```

Will generate a client_sync event sent to all active websockets that are subscribed to the event type

``` json
{
  "event_type": "client_sync",
  "client_id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```

## Diagnostic Events

Diagnostic events are intended to allow improved visibility of performance and development diagnostic via live front end rather than log analysis.

virtual_diag is generated by any virtual running an effect that support advanced / diag and is set to true. At time of writing that is only and all 2d matrix effects. Once established and tested it will be added to all 1d effects as well.

The example given in the following sequence diagram for general_diag is a trivial use case added to noise2d. It will be removed in due course when a better more relevant example is available.

```{mermaid}
  sequenceDiagram
    participant V as Virtual Device
    participant E as Effect (with LogSec)
    participant E2 as Effect (noise2d)
    participant LS as LogSec Monitor
    participant ES as Events System
    participant WS as WebSocket Connection
    participant FE as Frontend Client

    Note over V,FE: Virtual Diag Event Flow

    V->>+E: Execute effect in thread
    E->>+LS: log_sec() - Start frame timing
    LS->>LS: Track FPS, render times

    loop Every Frame
        E->>LS: Render frame
        LS->>LS: Measure render time
        LS->>LS: Update min/max/total times
    end

    LS->>LS: Check if second boundary crossed
    alt Second boundary crossed & diag enabled
        LS->>ES: fire_event(VirtualDiagEvent)
        Note right of LS: Contains: virtual_id, fps, r_avg, <br/>r_min, r_max, cycle, sleep, phy
        ES->>WS: notify_websocket(event)
        WS->>FE: send_event(virtual_diag)
        Note right of FE: Real-time performance metrics
    end

    Note over V,FE: General Diag Event Flow

    V->>+E2: Execute noise2d effect
    alt Test mode enabled
        E2->>E2: draw_test() - Draw diagnostic pattern
        E2->>ES: fire_event(GeneralDiagEvent)
        Note right of E2: Contains: debug message<br/>"Noise2d: {width}x{height}"
        ES->>WS: notify_websocket(event)
        WS->>FE: send_event(general_diag)
        Note right of FE: Diagnostic message for debugging
    end

    Note over V,FE: WebSocket Subscription Setup

    FE->>WS: subscribe_event("virtual_diag")
    WS->>ES: add_listener(notify_websocket, "virtual_diag")

    FE->>WS: subscribe_event("general_diag")
    WS->>ES: add_listener(notify_websocket, "general_diag")

    Note over V,FE: Event Distribution System

    rect rgb(240, 248, 255)
        Note over ES: Events.fire_event() calls all<br/>registered listeners via<br/>loop.call_soon_threadsafe()
    end
```

### `virtual_diag`

The `virtual_diag` WebSocket event is emitted when a virtual's diagnostics are updated. It provides real-time performance and timing metrics in units of seconds for a specific virtual entity on a 1 second period

**Payload Example:**
```json
{
  "event_type": "virtual_diag",
  "virtual_id": "my_virtual_id",
  "fps": 48,
  "r_avg": 0.017432,
  "r_min": 0.008123,
  "r_max": 0.022345,
  "cycle": 16.67,
  "sleep": 0.014232,
  "phy":
  {
    "fps": 55,
    "ver": "0.14.4",
    "n": 1024,
    "name": "32x32",
    "rssi": -45,
    "qual": 100
  }
}
```

**Fields:**
- `event_type`: Always `"virtual_diag"`.
- `virtual_id`: Identifier of the virtual entity.
- `fps`: Frames per second being rendered.
- `r_avg`: Average render time.
- `r_min`: Minimum render time.
- `r_max`: Maximum render time.
- `cycle`: Cycle time for the virtual's update loop.
- `sleep`: Sleep time between cycles.
- `phy`: A dictionary containing physical device information:
  - `fps`: Frames per second reported by the physical device.
  - `ver`: Firmware version of the device.
  - `n`: Number of LEDs or pixels in the device.
  - `name`: Name or identifier of the device.
  - `rssi`: Signal strength (RSSI) of the device's connection.
  - `qual`: Connection quality percentage.


**Usage:**
Subscribe to this event to monitor the performance and timing of virtual devices for diagnostics and optimization.

If a virtual is mapped directly to a device and that device is WLED, then an attempt to read the WLED info and extra key details will be made once per second asynchronously via the /json/info api call and returned on phy, unavailable values will be None.

---

### `general_diag`

The `general_diag` WebSocket event is emitted to provide arbitrary diagnostic messages, typically for debugging or informational purposes.

**Payload Example:**
```json
{
  "event_type": "general_diag",
  "debug": "Diagnostic message here",
  "scroll": false
}
```

**Fields:**
- `event_type`: Always `"general_diag"`.
- `debug`: The diagnostic message string.
- `scroll`: Boolean indicating if the message should be scrolled in the UI oe replaced in each cycle.

**Usage:**
Listen for this event to receive general diagnostic messages from the system, which may be useful for debugging or displaying system status in the frontend.
If a monospaced font is used then back end can attempt table live updates with scroll set to false which is default if not explicitly set.