================================
REST API Documentation
================================

The REST APIs are undergoing active development and many of the below APIs are either not yet implemented or not fully functional. This mainly serves as a reference of what the final APIs will *eventually* look like.


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

GET /api/devices
================================

POST /api/devices
================================
Adds a new device to LedFx



GET /api/devices/<deviceId>
================================
Returns information about the device with the matching device id as JSON

PUT /api/devices/<deviceId>
================================
Modifies the information pertaining to the device with the matching device id and returns the new device as JSON

DELETE /api/devices/<deviceId>
================================
Deletes the device with the matching device id.