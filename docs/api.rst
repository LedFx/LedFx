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

LedFx Configuration

.. rubric:: GET

Returns the current configuration for LedFx as JSON

/api/log (upcoming)
=========================

LedFx Logging

.. rubric:: GET

Returns the error logs for the currently active LedFx session

/api/schema/<schema_type>
=========================

LedFx Schemas

.. rubric:: GET /api/schema/*devices*

Returns all the valid schemas for a LedFx effect as JSON

.. rubric:: GET /api/schema/*effects*

Returns all the devices registered with LedFx as JSON

/api/devices
=========================

Query and manage devices connected to LedFx

.. rubric:: GET

Get configuration of all devices

.. rubric:: POST

Adds a new device to LedFx based on the provided JSON configuration

/api/devices/<deviceId>
=========================
Query and manage a specific device with the matching device id as JSON

.. rubric:: GET

Returns information about the device

.. rubric:: PUT

Modifies the information pertaining to the device and returns the new device as JSON

.. rubric:: DELETE

Deletes the device

/api/effects
=========================

Query and manage all effects

.. rubric:: GET

Returns all the effects currently created in LedFx as JSON

.. rubric:: POST (upcoming)

Create a new Effect based on the provided JSON configuration

/api/effects/<effectId>
=========================

Query and manage a specific effect with the matching effect id as JSON

.. rubric:: GET

Returns information about the effect

.. rubric:: PUT (upcoming)

Modifies the configuration of the effect and returns the new configuration as JSON

.. rubric:: DELETE (upcoming)

Deletes the effect with the matching effect id.

/api/devices/{device_id}/effects
================================

Endpoint linking devices to effects with the matching device id as JSON

.. rubric:: GET

Returns the active effect config of a device

.. rubric:: PUT

Update the active effect config of a device based on the provided JSON configuration
If config given is "RANDOMIZE", the active effect config will be automatically generated to random values

.. rubric:: POST

Set the device to a new effect based on the provided JSON configuration

.. rubric:: DELETE

Clear the active effect of a device

/api/devices/<device_id>/presets
================================

Endpoint linking devices to effect presets (pre-configured effect configs) with the matching device id as JSON

.. rubric:: GET

Get preset effect configs for active effect of a device

.. rubric:: PUT

Set active effect config of device to a preset

.. rubric:: POST

Save configuration of device's active effect as a custom preset for that effect

.. rubric:: DELETE

Clear effect of a device

/api/effects/<effect_id>/presets
================================

Endpoint for querying and managing presets (pre-configured effect configs) for each effect with the matching effect id as JSON

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

===================
   WebSocket API
===================

In addition to the REST APIs LedFx has a WebSocket API for streaming realtime data. The primary use for this is for things like effect visualizations in the frontend.

Will document this further once it is more well defined. The general structure will be event registration based.