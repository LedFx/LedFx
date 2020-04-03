================================
REST API
================================

The REST APIs are undergoing active development, so some of the below APIs may change in time. 
APIs marked as (upcoming) are yet to be added.

/api/info
================================
Information about LedFx

GET
--------------------------------
Returns basic information about the LedFx instance as JSON

.. code:: json

    {
        url: "http://127.0.0.1:8888",
        name: "LedFx",
        version: "0.0.1"
    }

/api/config
================================
LedFx Configuration

GET
--------------------------------
Returns the current configuration for LedFx as JSON

/api/log (upcoming)
================================
LedFx Logging

GET
--------------------------------
Returns the error logs for the currently active LedFx session

/api/schema/<schema_type>
================================
LedFx Schemas

GET /api/schema/*devices*
--------------------------------
Returns all the valid schemas for a LedFx effect as JSON

GET /api/schema/*effects*
--------------------------------
Returns all the devices registered with LedFx as JSON

/api/devices
================================
Query and manage devices connected to LedFx

GET
--------------------------------
Get configuration of all devices

POST
--------------------------------
Adds a new device to LedFx based on the provided JSON configuration

/api/devices/<deviceId>
================================
Query and manage a specific device with the matching device id as JSON

GET
--------------------------------
Returns information about the device 

PUT
--------------------------------
Modifies the information pertaining to the device and returns the new device as JSON

DELETE
--------------------------------
Deletes the device 

/api/effects
================================
Query and manage all effects

GET
--------------------------------
Returns all the effects currently created in LedFx as JSON

POST (upcoming)
--------------------------------
Create a new Effect based on the provided JSON configuration

/api/effects/<effectId>
================================
Query and manage a specific effect with the matching effect id as JSON

GET
--------------------------------
Returns information about the effect

PUT (upcoming)
--------------------------------
Modifies the configuration of the effect and returns the new configuration as JSON

DELETE (upcoming)
--------------------------------
Deletes the effect with the matching effect id.

/api/devices/{device_id}/effects
================================
Endpoint linking devices to effects with the matching device id as JSON

GET
--------------------------------
Returns the active effect config of a device

PUT
--------------------------------
Update the active effect config of a device based on the provided JSON configuration
If config given is "RANDOMIZE", the active effect config will be automatically generated to random values

POST
--------------------------------
Set the device to a new effect based on the provided JSON configuration

DELETE
--------------------------------
Clear the active effect of a device

/api/devices/<device_id>/presets
================================
Endpoint linking devices to effect presets (pre-configured effect configs) with the matching device id as JSON

GET
--------------------------------
Get preset effect configs for active effect of a device

PUT
--------------------------------
Set active effect config of device to a preset

POST
--------------------------------
Save configuration of device's active effect as a custom preset for that effect

DELETE
--------------------------------
Clear effect of a device

/api/effects/<effect_id>/presets
================================
Endpoint for querying and managing presets (pre-configured effect configs) for each effect with the matching effect id as JSON

GET
--------------------------------
Get all presets for an effect

PUT
--------------------------------
Rename a preset

DELETE
--------------------------------
Delete a preset

/api/scenes
================================
Endpoint for managing scenes. Active effects and configs of all devices can be saved as a "scene".

GET
--------------------------------
Get all saved scenes

PUT
--------------------------------
Set effects and configs of all devices to those specified in a scene

POST
--------------------------------
Save effect configuration of devices as a scene

DELETE
--------------------------------
Delete a scene

================================
WebSocket API
================================

In addition to the REST APIs LedFx has a WebSocket API for streaming realtime data. The primary use for this is for things like effect visualizations in the frontend.

Will document this further once it is more well defined. The general structure will be event registration based.