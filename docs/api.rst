==============
   REST API
==============

The REST APIs are undergoing active development, so some of the below APIs may change in time.
APIs marked as (upcoming) are yet to be added.

/api/info
===============

Information about LedFx

.. rubric:: GET

Returns basic information about the LedFx instance as JSON

.. code-block:: json

    {
      "url": "http://127.0.0.1:8888",
      "name": "LedFx",
      "version": "0.3.0"
    }

/api/config
===============

Endpoint for managing LedFx Configuration

.. rubric:: GET

Returns the current configuration for LedFx as JSON
A GET with no request body will return LedFx's full configuration.

You may instead ask for any number of the config keys:

- *host*
- *port*
- *port_s*
- *dev_mode*
- *configuration_version*
- *scan_on_startup*
- *visualisation_fps*
- *visualisation_maxlen*
- *audio*
- *melbanks*
- *wled_preferences*
- *devices*
- *virtuals*
- *integrations*
- *scenes*
- *user_presets*
- *ledfx_presets*

example: Get LedFx audio configuration

.. code-block:: json

    "audio"

example: Get LedFx audio, devices, and scenes configuration

.. code-block:: json

    ["audio", "devices", "scenes"]

.. rubric:: PUT

Updates LedFx configuration with any permitted keys.
LedFx will handle the update and restart if necessary.
Generally, updating any core config key will trigger a restart.

example:

.. code-block:: json

    {
      "audio": {
        "min_volume": 0.3
      },
      "dev_mode": true,
      "visualisation_fps": 50,
      "port": 8080
    }

.. rubric:: POST

Set full LedFx config. You must provide a full, valid config.
LedFx will restart to apply the config.
To simply update a part of the config, use PUT

.. rubric:: DELETE

Resets LedFx's config to default values and restarts.

*Warning* This will irreversibly delete all your devices, settings, etc.

/api/log
=========================

LedFx Logging

.. rubric:: GET

Opens a websocket connection through which realtime LedFx logging info will be sent.

/api/schema/
=========================

LedFx Schema Api

.. rubric:: GET /api/schema/

Get JSON schemas specifically defining the kind of data LedFx's API expects.
A GET with no request body will return all of LedFx's schemas
LedFx uses schemas to validate the following:

- *devices*
- *effects*
- *integrations*
- *virtuals*
- *audio*
- *melbanks*
- *wled_preferences*
- *core*

Like with the /api/config endpoint, you may instead ask for spefific schemas

example: Get LedFx audio schema

.. code-block:: json

    "audio"

example: Get LedFx devices and effects schema

.. code-block:: json

    ["devices", "effects"]

/api/schema/<schema_type>
============================

Query a specific LedFx schema with the matching *schema_type* as JSON

.. rubric:: GET /api/schema/<schema_type>

Returns the LedFx schema with the matching *schema_type* as JSON

- *devices*: Returns all the devices registered with LedFx

- *effects*: Returns all the valid schemas for an LedFx effect

- *integrations*: Returns all the integrations registered with LedFx

/api/devices
=========================

Query and manage devices connected to LedFx

.. rubric:: GET

Get configuration of all devices

.. rubric:: POST

Adds a new device to LedFx based on the provided JSON configuration

/api/devices/<device_id>
=========================

Query and manage a specific device with the matching *device_id* as JSON

.. rubric:: GET

Returns information about the device

.. rubric:: PUT

Modifies the information pertaining to the device and returns the new device as JSON

.. rubric:: DELETE

Deletes a device with the matching *device_id*

/api/find_devices
=========================

Find and add all WLED devices on the LAN.

.. rubric:: POST

For unregisted WLED devices, reads config direct from WLED remote device
Will default the remote protocol to DDP, unless WLED device build is prior to DDP support, in which case it will default to UDP
If device name has not been over ridden in WLED itself, then name will be generated from WLED-<6 digits of MAC Address>
Additionally ledfx virtuals will be created for all virtuals defined on the WLED device itself

Returns success as this is only a trigger action, device registration is handled by the back end

/api/find_launchpad
=========================

.. rubric:: GET

Returns the name of the first Launchpad device discovered on the system

example:

.. code-block:: json

    {
        "status": "success",
        "device": "Launchpad X"
    }

if no device is found will return an error

.. code-block:: json

    {
        "status": "error",
        "error": "Failed to find launchpad"
    }

/api/find_openrgb/?server=1.2.3.4&port=5678
===========================================

.. rubric:: GET

Optional Query parameters are supported as follows:

'**server**' (optional): IP address of openRGB server, a default value of loacl host will be used
'**port**' (optional): Port to be used for openRGB server. a default value of 6742 will be used

In most cases these do not need to be defined as defaults of localhost and 6742 are used

Returns all found openRGB devices registered with the openRGB server

example:

.. code-block:: json

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

if no devices are found an empty array will be returned

example:

.. code-block:: json

    {
        "status": "success",
        "devices": []
    }

if the openRGB server is not found an error will be returned

example:

.. code-block:: json

    {
        "status": "error",
        "error": "timed out"
    }

/api/effects
=========================

Query and manage all effects

.. rubric:: GET

Returns all the effects currently created in LedFx as JSON

.. rubric:: POST (upcoming)

Create a new Effect based on the provided JSON configuration

/api/effects/<effect_id>
=========================

Query and manage a specific effect with the matching *effect_id* as JSON

.. rubric:: GET

Returns information about the effect

.. rubric:: PUT (upcoming)

Modifies the configuration of the effect and returns the new configuration as JSON

.. rubric:: DELETE (upcoming)

Deletes the effect with the matching *effect_id*.

/api/virtuals
=========================

Query and manage virtuals connected to LedFx

.. rubric:: GET

Get configuration of all virtuals

.. rubric:: POST

Adds a new virtual to LedFx based on the provided JSON configuration

/api/virtuals/<virtual_id>
==========================

Query and manage a specific virtual with the matching *virtual_id* as JSON

.. rubric:: GET

Returns information about the virtual

.. rubric:: PUT

Set a virtual to active or inactive. Must evaluate to True or False with python's bool() (eg, true, 1, ..)

example:

.. code-block:: json

    {
      "active": false
    }

.. rubric:: POST

Update a virtual's segments configuration. Format is a list of lists in segment order.

[[id, start, end, invert], ...]

id: valid device id
start: first pixel on the device for this segment
end: last pixel on the device for this segment (inclusive)
invert: invert this segment when it is mapped onto the device

example:

.. code-block:: json

    {
      "segments": [
          ["my_device", 0, 49, false],
          ["my_other_device", 0, 99, false],
          ["my_device", 50, 99, false]
      ]
    }

This would end up with a virtual appearing on the devices as so:

.. code-block::

 [---first 50px of effect---][---last 50px of effect---] [---------------middle 100px of effect----------------]
 [-------------------my_device (100px)-----------------] [---------------my_other_device (100px)---------------]

another example:

.. code-block:: json

    {
      "segments": [
          ["my_device", 0, 9, false],
          ["my_device", 20, 79, false],
          ["my_device", 90, 99, false]
      ]
    }

This would end up with a virtual appearing on the devices as so:

.. code-block::

 [ 10px ]    [------ 60px of effect ------]     [ 10px ]
 [-------------------my_device (100px)-----------------]

.. rubric:: DELETE

Deletes a virtual with the matching *virtual_id*

/api/virtuals/{virtual_id}/effects
==================================

Endpoint linking virtuals to effects with the matching *virtual_id* as JSON

.. rubric:: GET

Returns the active effect config of a virtual

.. rubric:: PUT

Update the active effect config of a virtual based on the provided JSON configuration
If config given is "RANDOMIZE", the active effect config will be automatically generated to random values

.. rubric:: POST

Set the virtual to a new effect based on the provided JSON configuration

.. rubric:: DELETE

Clear the active effect of a virtual

/api/virtuals/<virtual_id>/presets
====================================

Endpoint linking virtuals to effect presets (pre-configured effect configs) with the matching *virtual_id* as JSON

.. rubric:: GET

Get preset effect configs for active effect of a virtual

.. rubric:: PUT

Set active effect config of virtual to a preset

.. code-block:: json

    {
      "category": "user_presets",
      "effect_id": "wavelength",
      "preset_id": "my_wavelength_preset"
    }

.. rubric:: POST

Save configuration of virtual's active effect as a custom preset for that effect

.. rubric:: DELETE

Clear effect of a virtual

/api/virtuals_tools
===================

Extensible support for general tools towards ALL virtuals in one call

.. rubric:: PUT

Supports tool instances of currently only force_color, others may be added in the future

**force_color**

Move all pixels in a virtual to specific color, will be overwritten by active effect
Use during configuration / calibration

.. code-block:: json

    {
      "tool": "force_color",
      "color": "blue"
    }

.. code-block:: json

    {
      "tool": "force_color",
      "color": "#FFFFFF"
    }

returns

.. code-block:: json

    {
        "status": "success",
        "tool": "force_color"
    }

/api/virtuals_tools/<virtual_id>
=================================

Extensible support for general tools towards a specified virtual

.. rubric:: PUT

Supports tool instances of currently only force_color, others may be added in the future

**force_color**

Move all pixels in a virtual to specific color, will be overwritten by active effect
Use during configuration / calibration

.. code-block:: json

    {
      "tool": "force_color",
      "color": "blue"
    }

.. code-block:: json

    {
      "tool": "force_color",
      "color": "#FFFFFF"
    }

returns

.. code-block:: json

    {
        "status": "success",
        "tool": "force_color"
    }

/api/effects/<effect_id>/presets
===================================

Endpoint for querying and managing presets (pre-configured effect configs) for each effect with the matching *effect_id* as JSON

.. rubric:: GET

Get all presets for an effect

.. rubric:: GET

Rename a preset

.. rubric:: DELETE

Delete a preset

/api/scenes
================================

Endpoint for managing scenes. Active effects and configs of all devices can be saved as a "scene".

.. rubric:: GET

Get all saved scenes

.. rubric:: PUT

Set effects and configs of all devices to those specified in a scene

.. rubric:: POST

Save effect configuration of devices as a scene

.. rubric:: DELETE

Delete a scene

/api/integrations
================================

Endpoint for managing integrations. Integrations are written to allow ledfx to communicate with other software, and
vice versa.

.. rubric:: GET

Get info of all integrations
Optional, send request body to get specific info of integrations
Any of: ["id", "type", "active", "status", "data", "config"]

example:

.. code-block:: json

    {
      "info":"status"
    }

STATUS REFERENCE
0: disconnected
1: connected
2: disconnecting
3: connecting

.. rubric:: PUT

Toggle an integration on or off

example:

.. code-block:: json

    {
      "id": "myqlc"
    }

.. rubric:: POST

Create a new integration, or update an existing one

.. code-block:: json

    {
      "type": "qlc",
      "config": {
          "description": "QLC Test",
          "ip_address": "127.0.0.1",
          "name": "myQLC+",
          "port": 9999
          }
    }

.. code-block:: json

    {
      "type": "spotify",
      "config": {
          "description": "Spotify triggers for party",
          "name": "Party Spotify"
          }
    }

.. rubric:: DELETE

Delete an integration, erasing all its configuration and data.

.. code-block:: json

    {
      "id": "myqlc"
    }

NOTE: This does not turn off the integration, it deletes it entirely! (though it will first turn off..)

/api/integrations/qlc/<integration_id>
==============================================

Endpoint for querying and managing a QLC integration.

.. rubric:: GET

Returns info from the QLC+ integration.

Specify "info", one of: ``["event_types", "qlc_widgets", "qlc_listeners"]``

*event_types*: retrieves a list of all the types of events and associated filters a qlc listener can subscribe to

*qlc_widgets*: retrieves a list of all the widgets that can be modified, formatted as [(ID, Type, Name),...] for "type":

- "Buttons" can be set to either off (0) or on (255)

- "Audio Triggers" are either off (0) or on (255)

- "Sliders" can be anywhere between 0 and 255

*qlc_listeners*: retrieves a list of all of the events that QLC is listening to, and their associated widget value payloads

.. code-block:: json

    {
      "info": "qlc_listeners"
    }

.. rubric:: PUT

Toggle a QLC+ event listener on or off, so that it will or will not send its payload to set QLC+ widgets

.. code-block:: json

    {
      "event_type": "scene_set",
      "event_filter": {
          "scene_name": "My Scene"
          }
    }

.. rubric:: POST

Add a new QLC event listener and QLC+ payload or update an existing one if it exists with same event_type and event_filter
The "qlc_payload" is a dict of {"widget_id": value} that will be sent to QLC+

.. code-block:: json

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

.. rubric:: DELETE

Delete a QLC event listener, and associated payload data.

.. code-block:: json

    {
      "event_type": "scene_set",
      "event_filter": {
          "scene_name": "My Scene"
          }
    }

NOTE: This does not turn off the integration, it deletes it entirely! (though it will first turn off..)

/api/integrations/spotify/<integration_id>
=============================================
Endpoint for querying and managing a Spotify integration.

.. rubric:: GET

Get all the song triggers

.. rubric:: PUT

Update a song trigger
[TODO]

.. rubric:: POST

Create a new song trigger

.. code-block:: json

    {
      "scene_id": "my_scene",
      "song_id": "347956287364597",
      "song_name": "Really Cool Song",
      "song_position": "43764",
    }

.. rubric:: DELETE

Delete a song trigger

.. code-block:: json

    {
      "trigger_id": "Really Cool Song - 43764",
    }

===================
   WebSocket API
===================

In addition to the REST APIs LedFx has a WebSocket API for streaming realtime data. The primary use for this is for things like effect visualizations in the frontend.

Will document this further once it is more well defined. The general structure will be event registration based.