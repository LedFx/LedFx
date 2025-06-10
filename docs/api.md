# REST API

The REST APIs are undergoing active development, so some of the below
APIs may change in time. APIs marked as (upcoming) are yet to be added.

## /api/info

Information about LedFx

**GET**

Returns basic information about the LedFx instance as JSON

``` json
{
  "url": "http://127.0.0.1:8888",
  "name": "LedFx",
  "version": "0.3.0"
}
```

## /api/config

Endpoint for managing LedFx Configuration

**GET**

Returns the current configuration for LedFx as JSON A GET with no
request body will return LedFx\'s full configuration.

You may instead ask for any number of the config keys:

-   *host*
-   *port*
-   *port_s*
-   *dev_mode*
-   *configuration_version*
-   *scan_on_startup*
-   *visualisation_fps*
-   *visualisation_maxlen*
-   *audio*
-   *melbanks*
-   *wled_preferences*
-   *devices*
-   *virtuals*
-   *integrations*
-   *scenes*
-   *user_presets*
-   *ledfx_presets*
-   *flush_on_deactivate*

example: Get LedFx audio configuration

``` json
"audio"
```

example: Get LedFx audio, devices, and scenes configuration

``` json
["audio", "devices", "scenes"]
```

**PUT**

Updates LedFx configuration with any permitted keys. LedFx will handle
the update and restart if necessary. Generally, updating any core config
key will trigger a restart.

example:

``` json
{
  "audio": {
    "min_volume": 0.3
  },
  "dev_mode": true,
  "visualisation_fps": 50,
  "port": 8080
}
```

**POST**

Set full LedFx config. You must provide a full, valid config. LedFx will
restart to apply the config. To simply update a part of the config, use
PUT

**DELETE**

Resets LedFx\'s config to default values and restarts.

*Warning* This will irreversibly delete all your devices, settings, etc.

## /api/log

LedFx Logging

**GET**

Opens a websocket connection through which realtime LedFx logging info
will be sent.

## /api/schema/

LedFx Schema Api

**GET /api/schema/**

Get JSON schemas specifically defining the kind of data LedFx\'s API
expects. A GET with no request body will return all of LedFx\'s schemas
LedFx uses schemas to validate the following:

-   *devices*
-   *effects*
-   *integrations*
-   *virtuals*
-   *audio*
-   *melbanks*
-   *wled_preferences*
-   *core*

Like with the /api/config endpoint, you may instead ask for spefific
schemas

example: Get LedFx audio schema

``` json
"audio"
```

example: Get LedFx devices and effects schema

``` json
["devices", "effects"]
```

## /api/schema/\<schema_type\>

Query a specific LedFx schema with the matching *schema_type* as JSON

**GET /api/schema/\<schema_type\>**

Returns the LedFx schema with the matching *schema_type* as JSON

-   *devices*: Returns all the devices registered with LedFx
-   *effects*: Returns all the valid schemas for an LedFx effect
-   *integrations*: Returns all the integrations registered with LedFx

## /api/devices

Query and manage devices connected to LedFx

**GET**

Get configuration of all devices

**POST**

Adds a new device to LedFx based on the provided JSON configuration

## /api/devices/\<device_id\>

Query and manage a specific device with the matching *device_id* as JSON

**GET**

Returns information about the device

**PUT**

Modifies the information pertaining to the device and returns the new
device as JSON

**DELETE**

Deletes a device with the matching *device_id*

## /api/find_devices

Find and add all WLED devices on the LAN.

**POST**

For unregisted WLED devices, reads config direct from WLED remote device
Will default the remote protocol to DDP, unless WLED device build is
prior to DDP support, in which case it will default to UDP If device
name has not been over ridden in WLED itself, then name will be
generated from WLED-\<6 digits of MAC Address\> Additionally ledfx
virtuals will be created for all virtuals defined on the WLED device
itself

Returns success as this is only a trigger action, device registration is
handled by the back end

## /api/find_launchpad

**GET**

Returns the name of the first Launchpad device discovered on the system

example:

``` json
{
    "status": "success",
    "device": "Launchpad X"
}
```

if no device is found will return an error

``` json
{
    "status": "error",
    "error": "Failed to find launchpad"
}
```

## /api/find_openrgb

Returns all found openRGB devices registered with the openRGB server

**GET**

The GET call uses default values of 127.0.0.1:6742 for the openRGB
server

**POST**

JSON parameters are supported as follows:

| \'\*\*server\*\*\' (optional): IP address of openRGB server, a default
  value of 127.0.0.1 will be used
| \'\*\*port\*\*\' (optional): Port to be used for openRGB server, a
  default value of 6742 will be used

``` json
{
  "server": "1.2.3.4",
  "port": 1234
}
```

example reponse:

``` json
{
    "status": "success",
    "devices": [
        {
            "name": "ASRock Z370 Gaming K6",
            "type": 0,
            "id": 0,
            "leds": 1
        },
        {
            "name": "ASUS ROG STRIX 3080 O10G V2 WHITE",
            "type": 2,
            "id": 1,
            "leds": 22
        },
        {
            "name": "Razer Deathadder V2",
            "type": 6,
            "id": 2,
            "leds": 2
        }
    ]
}
```

if no devices are found an empty array will be returned

example:

``` json
{
    "status": "success",
    "devices": []
}
```

if the openRGB server is not found an error will be returned

example:

``` json
{
    "status": "error",
    "error": "timed out"
}
```

## /api/get_nanoleaf_token

**POST**

REST end-point for requesting auth token from Nanoleaf. Ensure that the
Nanoleaf controller is in pairing mode. Long press the power button on
the controller for 5-7 seconds. White LEDs will scan back and forth to
indicate pairing mode.

Returns the auth token as a string

``` json
{
    "auth_token":"N7knmECvfRjoBlahBlah1Gsn5K5HcxHy"
}
```

If the Nanoleaf controller is present but not in pairing mode will
return an error message

``` json
{
    "error":"{ip}:{port}: Ensure Nanoleaf controller is in pairing mode"
}
```

## /api/get_gif_frames

### Overview

A RESTful endpoint designed for extracting and returning individual
frames from a GIF image. Clients can request frames by providing either
the URL or the local file path of the GIF resource. The frames are
returned in JPEG format for efficient data transmission.

### Endpoint Details

-   **Endpoint Path**: `/api/get_gif_frames`

### Request

-   **Method**: POST
-   **Request Data**:
    -   `path_url` (String): The URL or local file path of the GIF image
        from which frames are to be extracted.

### Response

-   **Success**:
    -   Status Code: 200
    -   Body:
        -   `frame_count` (Integer): The number of frames extracted from
            the GIF.
        -   `frames` (List): A list of base64 encoded strings, each
            representing a frame in JPEG format.
-   **Failure**:
    -   Status Code: 400 (Bad Request)
        -   When JSON decoding fails or the required attribute
            `path_url` is not provided.
    -   Status Code: 404 (Not Found)
        -   When the GIF image at the specified URL or file path cannot
            be opened or processed.

### Error Handling

In case of an error, the endpoint returns a JSON object with the
following structure:

``` json
{
  "status": "failed",
  "reason": "<error reason>"
}
```

### Usage Example

#### Requesting GIF Frames

To request frames from a GIF image, send a GET request with either the
URL or local file path in the request data:

``` json
{
  "path_url": "http://example.com/image.gif"
}
```

Or, for a local file:

``` json
{
  "path_url": "/path/to/local/image.gif"
}
```

Windows example

``` json
{
  "path_url": "C:\\path\\to\\local\\image.gif"
}
```

#### Sample Response

A successful response with two extracted frames might look like this:

``` json
{
  "frame_count": 2,
  "frames": [
    "<base64-encoded JPEG data>",
    "<base64-encoded JPEG data>"
  ]
}
```

## /api/get_image

### Overview

A RESTful endpoint designed for retrieving an image. Clients can request
a file by providing either the URL or the local file path of the image
resource. The image is returned in JPEG format for efficient data
transmission.

### Endpoint Details

-   **Endpoint Path**: `/api/get_image`

### Request

-   **Method**: POST
-   **Request Data**:
    -   `path_url` (String): The URL or local file path of the image
        from to be opened.

### Response

-   **Success**:
    -   Status Code: 200
    -   Body:
        -   `image` (String): A base64 encoded image in JPEG format.
-   **Failure**:
    -   Status Code: 400 (Bad Request)
        -   When JSON decoding fails or the required attribute
            `path_url` is not provided.
    -   Status Code: 404 (Not Found)
        -   When the image at the specified URL or file path cannot be
            opened or processed.

### Error Handling

In case of an error, the endpoint returns a JSON object with the
following structure:

``` json
{
  "status": "failed",
  "reason": "<error reason>"
}
```

### Usage Example

#### Requesting Image

To request an image, send a GET request with either the URL or local
file path in the request data:

``` json
{
  "path_url": "http://example.com/image.gif"
}
```

Or, for a local file:

``` json
{
  "path_url": "/path/to/local/image.gif"
}
```

Windows example

``` json
{
  "path_url": "C:\\path\\to\\local\\image.gif"
}
```

#### Sample Response

A successful response with image data might look like this:

``` json
{
  "image": "<base64-encoded JPEG data>"
}
```

## /api/effects

Query and manage all effects

**GET**

Returns all the effects currently created in LedFx as JSON

**POST (upcoming)**

Create a new Effect based on the provided JSON configuration

## /api/effects/\<effect_id\>

Query and manage a specific effect with the matching *effect_id* as JSON

**GET**

Returns information about the effect

**PUT (upcoming)**

Modifies the configuration of the effect and returns the new
configuration as JSON

**DELETE (upcoming)**

Deletes the effect with the matching *effect_id*.

## /api/virtuals

Query and manage virtuals connected to LedFx

**GET**

Get configuration of all virtuals

**POST**

Adds a new virtual to LedFx based on the provided JSON configuration

## /api/virtuals/\<virtual_id\>

Query and manage a specific virtual with the matching *virtual_id* as
JSON

**GET**

Returns information about the virtual

**PUT**

Set a virtual to active or inactive. Must evaluate to True or False with
python\'s bool() (eg, true, 1, ..)

example:

``` json
{
  "active": false
}
```

**POST**

Update a virtual\'s segments configuration. Format is a list of lists in
segment order.

\[\[id, start, end, invert\], \...\]

id: valid device id start: first pixel on the device for this segment
end: last pixel on the device for this segment (inclusive) invert:
invert this segment when it is mapped onto the device

example:

``` json
{
  "segments": [
      ["my_device", 0, 49, false],
      ["my_other_device", 0, 99, false],
      ["my_device", 50, 99, false]
  ]
}
```

This would end up with a virtual appearing on the devices as so:

```
[---first 50px of effect---][---last 50px of effect---] [---------------middle 100px of effect----------------]
[-------------------my_device (100px)-----------------] [---------------my_other_device (100px)---------------]
```

another example:

``` json
{
  "segments": [
      ["my_device", 0, 9, false],
      ["my_device", 20, 79, false],
      ["my_device", 90, 99, false]
  ]
}
```

This would end up with a virtual appearing on the devices as so:

```
[ 10px ]    [------ 60px of effect ------]     [ 10px ]
[-------------------my_device (100px)-----------------]
```

**DELETE**

Deletes a virtual with the matching *virtual_id*

## /api/virtuals/{virtual_id}/effects

Endpoint linking virtuals to effects with the matching *virtual_id* as
JSON

**GET**

Returns the active effect config of a virtual

**PUT**

Update the active effect config of a virtual based on the provided JSON
configuration If config given is \"RANDOMIZE\", the active effect config
will be automatically generated to random values

**POST**

Set the virtual to a new effect based on the provided JSON configuration

**DELETE**

Clear the active effect of a virtual

### Fallback effects

/api/virtuals/{virtual_id}/effects has been extended for PUT and POST
with an optional fallback parameter

\"fallback\": (true / false / seconds)

If true ( 300 seconds ) or a value in float seconds, the current running
effect on the virtual will be set as the fallback.

Fallback is auto triggered by the completed scoll of texter2d with side
scroll or the timer expiring

This is intended for use cases such as temporarily displaying a track
name before returning to the prior effect configuration.

Additionally a running temporary effect can be cancelled by triggering
the fallback via a call to /api/virtuals/{virtual_id}/fallback

This can be used for interactive scenarios such as releasing a button
that triggered the temporary effect.

## /api/virtuals/{virtual_id}/fallback

**GET**

Cancel the temporary effect on virtual_id and force the fallback to
trigger, removes any fallback timers

Use for a button release to clear the fallback effect cycle

## /api/virtuals/{virtual_id}/effects/delete

**POST**

Endpoint to remove a specific effect type from the virtual stored
configurations

``` json
{
    "type": "energy2"
}
```

The effect contained in the param provided will be removed from the
configuration for the virtual.

If that effect type is the active effect on the virtual, the active
effect will also be cleared.

If the provide effect type is not present, no change will occur, and a
success message will be returned.

## /api/virtuals/\<virtual_id\>/presets

Endpoint linking virtuals to effect presets (pre-configured effect
configs) with the matching *virtual_id* as JSON

**GET**

Get preset effect configs for active effect of a virtual

**PUT**

Set active effect config of virtual to a preset

``` json
{
  "category": "user_presets",
  "effect_id": "wavelength",
  "preset_id": "my_wavelength_preset"
}
```

**POST**

Save configuration of virtual\'s active effect as a custom preset for
that effect

**DELETE**

Clear effect of a virtual

## /api/virtuals_tools

Extensible support for general tools towards ALL virtuals in one call

**POST**

Supports addition of oneshots to all virtuals.

### oneshot

Fill all active virtuals with a single color in a defined envelope of timing

Intended to allow integration of instantaneous game effects over all active virtual

Repeated oneshot to a virtual will add an extra oneshot if the previous ones have not finished

- color: The color to which we wish to fill the virtual, any format supported, default is white
- ramp: The time in ms over which to ramp the color from zero to full weight over the active  effect
- hold: The time in ms to hold the color to full weight over the active effect
- fade: The time in ms to fade the color from full weight to zero over the active effect
- brightness: The brightness of the oneshot at the beginning. Defaults to 1.0 which is maximum brightness


``` json
{
    "tool":"oneshot",
    "color":"white",
    "ramp":10,
    "hold":200,
    "fade":2000,
    "brightness":1
}
```

returns

``` json
{
    "status": "success",
    "tool": "oneshot"
}
```

**PUT**

Supports tool instances of currently only force_color and oneshot,
others may be added in the future

### force_color

Move all pixels in a virtual to specific color, will be overwritten by
active effect Use during configuration / calibration

``` json
{
  "tool": "force_color",
  "color": "blue"
}
```

``` json
{
  "tool": "force_color",
  "color": "#FFFFFF"
}
```

returns

``` json
{
    "status": "success",
    "tool": "force_color"
}
```

### oneshot

Disables all oneshots on all virtuals. Returns success if at least one oneshot is found.

``` json
{
    "tool":"oneshot"
}
```

returns

``` json
{
    "status": "success",
    "tool": "oneshot"
}
```

## /api/virtuals_tools/\<virtual_id\>

Extensible support for general tools towards a specified virtual

**POST**

Supports addition of oneshots to all virtuals.

### oneshot

Fill the specified virtual with a single color in a defined envelope of timing

Intended to allow integration of instantaneous game effects over any active virtual

Repeated oneshot to a virtual will add an extra oneshot if the previous ones have not finished

- color: The color to which we wish to fill the virtual, any format supported, default is white
- ramp: The time in ms over which to ramp the color from zero to full weight over the active effect
- hold: The time in ms to hold the color to full weight over the active effect
- fade: The time in ms to fade the color from full weight to zero over the active effect
- brightness: The brightness of the oneshot at the beginning. Defaults to 1.0 which is maximum brightness

``` json
{
    "tool":"oneshot",
    "color":"white",
    "ramp":10,
    "hold":200,
    "fade":2000,
    "brightness":1
}
```

returns

``` json
{
    "status": "success",
    "tool": "oneshot"
}
```

The virtual must be active or an error will be returned

``` json
{
    "status": "failed",
    "reason": "virtual falcon1 is not active"
}
```

**PUT**

Supports tool instances of force_color, calibration, highlight, oneshot
and copy, others may be added in the future

### force_color

Move all pixels in a virtual to specific color, will be overwritten by
active effect Use during configuration / calibration

``` json
{
  "tool": "force_color",
  "color": "blue"
}
```

``` json
{
  "tool": "force_color",
  "color": "#FFFFFF"
}
```

returns

``` json
{
    "status": "success",
    "tool": "force_color"
}
```

### calibration

Force virtual into calibration mode

All segments will be switched to solid color rotation of RGBCMY on the final devices
Device backgrounds will be set to black.

Changes to virtual segments in edit virtual will be displayed on browser second tab if open on devices view and physical devices live.

Setting is not persistant. Shutting down ledfx while in calibration mode will leave virtual in normal effect settings in next cycle.

Enter calibration mode with

``` json
{
  "tool": "calibration",
  "mode": "on"
}
```

Exit calibration mode with

``` json
{
  "tool": "calibration",
  "mode": "off"
}
```

returns

``` json
{
    "status": "success",
    "tool": "calibration"
}
```

### highlight

Highlight a segment of a virtual with white, use for editing of virtual segmentations in calibration mode

Intended to highlight the last edited segment, or last reordered segment

- state: defaults to true, explicity send False to turn off highlight
- device: device id of the device which the segment is to be highlighted on, forced to lower case
- start: index of led start on device for highlight
- stop: index of led stop on device for highlight
- flip: render order inversion, default to false

``` json
{
  "tool": "highlight",
  "device": "falcon1",
  "start": 2019,
  "stop": 2451,
  "flip": true
}
```

Disable highlight

``` json
{
  "tool": "highlight",
  "state": false
}
```

returns

``` json
{
    "status": "success",
    "tool": "highlight"
}
```

### oneshot

Disables all oneshots on the specified virtual. Returns success if at least one oneshot is found.

``` json
{
    "tool":"oneshot",
    "color":"white",
    "ramp":10,
    "hold":200,
    "fade":2000,
    "brightness":1
}
```

returns

``` json
{
    "status": "success",
    "tool": "oneshot"
}
```

The virtual must be active or an error will be returned

``` json
{
    "status": "failed",
    "reason": "oneshot was not found"
}
```

### copy

Copy the active effect config of \<virtual_id\> to a list of other virtuals

- target: A list of virtual ids to copy the active effect config to

``` json
{
    "tool":"copy",
    "target":["my_virtual1","my_virtual2","my_virtual3"]
}
```

returns

``` json
{
    "status": "success",
    "tool": "copy"
}
```

| The virtual must have an active or an error will be returned
| target must be a list of virtual ids or an error will be returned
| At least one virtual effect copy must be successful or an error will
  be returned

## /api/effects/\<effect_id\>/presets

Endpoint for querying and managing presets (pre-configured effect
configs) for each effect with the matching *effect_id* as JSON

**GET**

Get all presets for an effect

**GET**

Rename a preset

**DELETE**

Delete a preset

## /api/scenes

Endpoint for managing scenes. Active effects and configs of all devices
can be saved as a \"scene\".

**GET**

Get all saved scenes

**PUT**

Set effects and configs of all devices to those specified in a scene

**POST**

Save effect configuration of devices as a scene

Now support default behaviour when no \"virtuals\" key is provided of
saving all currently active virtuals to the scene in their current
configuration

``` json
{
    "name": "test1",
    "scene_image": "",
    "scene_tags": "",
    "scene_puturl": "",
    "scene_payload": ""
}
```

Where a \"virtuals\" key is provided, only the virtuals specified will
be saved to the scene, using the effect type and config carried in the
json payload

::: collapse
Expand for specified Virtuals Example

``` json
{
    "name": "test2",
    "scene_image": "image: https://i.pinimg.com/736x/05/9c/a7/059ca7cf94a85a3e836693e84c5bf42f--red-frogs.jpg",
    "scene_tags": "",
    "scene_puturl": "",
    "scene_payload": "",
    "virtuals": {
        "falcon1": {
            "type": "blade_power_plus",
            "config": {
                "background_brightness": 1,
                "background_color": "#000000",
                "blur": 2,
                "brightness": 1,
                "decay": 0.7,
                "flip": false,
                "frequency_range": "Lows (beat+bass)",
                "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)",
                "gradient_roll": 0,
                "invert_roll": false,
                "mirror": false,
                "multiplier": 0.5
            }
        },
        "big-copy": {
            "type": "energy",
            "config": {
                "background_brightness": 1,
                "background_color": "#000000",
                "blur": 4,
                "brightness": 1,
                "color_cycler": false,
                "color_high": "#0000ff",
                "color_lows": "#ff0000",
                "color_mids": "#00ff00",
                "flip": false,
                "mirror": true,
                "mixing_mode": "additive",
                "sensitivity": 0.6
            }
        }
    }
}
```
:::

|

**DELETE**

Delete a scene

``` json
{
    "id": "test2"
}
```

## /api/integrations

Endpoint for managing integrations. Integrations are written to allow
ledfx to communicate with other software, and vice versa.

**GET**

Get info of all integrations Optional, send request body to get specific
info of integrations Any of: \[\"id\", \"type\", \"active\", \"status\",
\"data\", \"config\"\]

example:

``` json
{
  "info":"status"
}
```

STATUS REFERENCE 0: disconnected 1: connected 2: disconnecting 3:
connecting

**PUT**

Toggle an integration on or off

example:

``` json
{
  "id": "myqlc"
}
```

**POST**

Create a new integration, or update an existing one

``` json
{
  "type": "qlc",
  "config": {
      "description": "QLC Test",
      "ip_address": "127.0.0.1",
      "name": "myQLC+",
      "port": 9999
      }
}
```

``` json
{
  "type": "spotify",
  "config": {
      "description": "Spotify triggers for party",
      "name": "Party Spotify"
      }
}
```

**DELETE**

Delete an integration, erasing all its configuration and data.

``` json
{
  "id": "myqlc"
}
```

NOTE: This does not turn off the integration, it deletes it entirely!
(though it will first turn off..)

## /api/integrations/qlc/\<integration_id\>

Endpoint for querying and managing a QLC integration.

**GET**

Returns info from the QLC+ integration.

Specify \"info\", one of:
`["event_types", "qlc_widgets", "qlc_listeners"]`

*event_types*: retrieves a list of all the types of events and
associated filters a qlc listener can subscribe to

*qlc_widgets*: retrieves a list of all the widgets that can be modified,
formatted as \[(ID, Type, Name),\...\] for \"type\":

-   \"Buttons\" can be set to either off (0) or on (255)
-   \"Audio Triggers\" are either off (0) or on (255)
-   \"Sliders\" can be anywhere between 0 and 255

*qlc_listeners*: retrieves a list of all of the events that QLC is
listening to, and their associated widget value payloads

``` json
{
  "info": "qlc_listeners"
}
```

**PUT**

Toggle a QLC+ event listener on or off, so that it will or will not send
its payload to set QLC+ widgets

``` json
{
  "event_type": "scene_set",
  "event_filter": {
      "scene_name": "My Scene"
      }
}
```

**POST**

Add a new QLC event listener and QLC+ payload or update an existing one
if it exists with same event_type and event_filter The \"qlc_payload\"
is a dict of {\"widget_id\": value} that will be sent to QLC+

``` json
{
  "event_type": "scene_set",
  "event_filter": {
      "scene_name": "My Scene"
      },
  "qlc_payload": {
      "0":255,
      "1":255,
      "2":169
      }
}
```

**DELETE**

Delete a QLC event listener, and associated payload data.

``` json
{
  "event_type": "scene_set",
  "event_filter": {
      "scene_name": "My Scene"
      }
}
```

NOTE: This does not turn off the integration, it deletes it entirely!
(though it will first turn off..)

## /api/integrations/spotify/\<integration_id\>

Endpoint for querying and managing a Spotify integration.

**GET**

Get all the song triggers

**PUT**

Update a song trigger \[TODO\]

**POST**

Create a new song trigger

``` json
{
  "scene_id": "my_scene",
  "song_id": "347956287364597",
  "song_name": "Really Cool Song",
  "song_position": "43764",
}
```

**DELETE**

Delete a song trigger

``` json
{
  "trigger_id": "Really Cool Song - 43764",
}
```

# WebSocket API

In addition to the REST APIs LedFx has a WebSocket API for streaming
realtime data. The primary use for this is for things like effect
visualizations in the frontend.

Will document this further once it is more well defined. The general
structure will be event registration based.

## Websocket client UIDs

::: mermaid

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

:::

On opening a websocket connection the client will be assigned a UID stored along with the client IP address. noting that mulitple client can exist on one IP address. Multiple browser tabs for example.

The assigned UID will be returned to the client via an event on the websocket of the following structure

``` json
{
  "event_type": "client_id",
  "id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
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
  "id": "e59d112e-3652-41e5-acb1-94538b4cb27c",
  "ip": "1.2.3.4"
}
```

#### client_disconnected

Generated when an existing client disconnects its websocket to the backend.

``` json
{
  "event_type": "client_disconnected",
  "id": "e59d112e-3652-41e5-acb1-94538b4cb27c",
  "ip": "1.2.3.4"
}
```

#### client_sync

Generated when a client makes a POST to the rest api endpoint /api/clients with "action": "sync"

This is intended to allow a client to inform other clients they should sync their configuration due to stimulated changes. The receiving client can filter against its own id to avoid self recursive notifications

``` json
{
  "event_type": "client_sync",
  "id": "e59d112e-3652-41e5-acb1-94538b4cb27c",
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
   "id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```

Will generate a client_sync event sent to all active websockets that are subscribed to the event type

``` json
{
  "event_type": "client_sync",
  "id": "e59d112e-3652-41e5-acb1-94538b4cb27c"
}
```
