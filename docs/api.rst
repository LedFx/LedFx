================================
REST API
================================

The REST APIs are undergoing active development and many of the below APIs are either not yet implemented or not fully functional. This page mainly serves as a reference of what the final APIs will *eventually* look like.

GET /api/info
================================
Returns basic information about the LedFx instance as JSON

.. code:: json

    {
        url: "http://127.0.0.1:8888",
        name: "LedFx",
        version: "0.0.1"
    }

GET /api/config
================================
Returns the current configuration for LedFx as JSON

GET /api/log
================================
Returns the error logs for the currently active LedFx session

GET /api/schema/devices
================================
Returns all the valid schemas for a LedFx device as JSON

GET /api/schema/effects
================================
Returns all the valid schemas for a LedFx effect as JSON

GET /api/devices
================================
Returns all the devices registered with LedFx as JSON

POST /api/devices
================================
Adds a new device to LedFx based on the provided JSON configuration.

GET /api/devices/<deviceId>
================================
Returns information about the device with the matching device id as JSON

PUT /api/devices/<deviceId>
================================
Modifies the information pertaining to the device with the matching device id and returns the new device as JSON

DELETE /api/devices/<deviceId>
================================
Deletes the device with the matching device id.

GET /api/effects
================================
Returns all the effects currently created in LedFx as JSON

POST /api/effects
================================
Create a new Effect based on the provided JSON configuration.

GET /api/effects/<effectId>
================================
Returns information about the effect with the matching effect id as JSON

PUT /api/effects/<effectId>
================================
Modifies the configuration of the effect with a matching effect id and returns the new configuration as JSON

DELETE /api/effects/<effectId>
================================
Deletes the effect with the matching effect id.

GET /api/devices/<device_id>/presets
================================
get presets for active effect of a device

PUT /api/devices/<device_id>/presets
================================
Set active effect of device to a preset

POST /api/devices/<device_id>/presets
================================
Save configuration of device's active effect as a custom preset

DELETE /api/devices/<device_id>/presets
================================
Clear effect of a device

GET /api/effects/<effect_id>/presets
================================
Get all presets for an effect

PUT /api/effects/<effect_id>/presets
================================
Rename a preset

DELETE /api/effects/<effect_id>/presets
================================
Delete a preset

================================
WebSocket API
================================

In addition to the REST APIs LedFx has a WebSocket API for streaming realtime data. The primary use for this is for things like effect visualizations in the frontend.

Will document this further once it is more well defined. The general structure will be event registration based.