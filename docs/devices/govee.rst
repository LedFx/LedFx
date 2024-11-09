Govee Device
============

Ledfx has now added support for Govee LAN enabled devices that are Razer / Dreamview compatible.

Ledfx has only limited access to examples, so if you find a device that should be supported by is not, please raise in discord `Help and Support <https://discord.gg/h3Atx4mkCh>`_

At the time of writing compatible Govee products were listed at this link under the `Supports Razer/Dreamview tab <https://desktop.govee.com/razer/devices>`_

It is not known exhaustively, which of these are truly functional against ledfx current integration.

**Be aware:** An active session from LedFx towards a Govee device may prevent the Govee Desktop app from opening correctly, it may appear within Task manager but no substantiate its UI window. Stop LedFx, close Govee Desktop from within Task Manager, and relaunch Govee Desktop.

----------------------
Known working examples
----------------------

Standard Lights
^^^^^^^^^^^^^^^

Known working with **Stretch To Fit** set to off

* H6061 Glide Hexa Light Panels
* H6167 Govee TV Backlight For 40-50 inch TVs
* H61BA Govee RGBICW LED Strip Light 16.4 ft
* H61D5 Neon Rope Light 2 16.4 FT
* H615C RGB LED Strip Light 50 FT
* TBD: add more here on discovery...

Matrix Lights
^^^^^^^^^^^^^

There is currently no good story around Govee matrix lights such as curtains.

The majority of Govee effects appear to be driven local, not via the LAN interface.

When looking at the Govee LAN interface towards some products, it can be see that a very low segment count is used and the **Stretch To Fit** option is set to on.

All examples from Chroma so far captured are also **Stetch to Fit** and even lower segment count of 4

Currently investigated matrix lights include:

+--------+--------------------+------+-------+--------+----------------------------------+
| Device | Description        | LEDs | Govee | Chroma | Notes                            |
+========+====================+======+=======+========+==================================+
| H70B1  | Curtain Lights     | 520  | 6     | 4      | TBD Best experimental values ABC |
+--------+--------------------+------+-------+--------+----------------------------------+
| H6811  | Net Lights         | 480  | NA    | NA     | Only first 224 pixels @82 seg    |
+--------+--------------------+------+-------+--------+----------------------------------+
| TBD    | Add more here...   | TBD  | TBD   | TBD    | TBD                              |
+--------+--------------------+------+-------+--------+----------------------------------+

H70B1 Curtain Lights 520
------------------------

TBD

H6811 Net Lights 480
--------------------

NOT RECOMMENDED FOR USE WITH LEDFX

No apparent effect from the strech bit, all colors sent are stretched across the first 224 pixels using a correct header. No apparent way to use the last 256 pixels.

82 is the max pixel value to use before pixel stretching to 224 breaks down.

Not supported by Govee app or Razer Chroma for any LAN relevant effects.


--------------------------
Govee Device Configuration
--------------------------

By default compatible Govee devices are not enabled for LAN control.

This must be enabled in the Govee app for both Wifi access and LAN api control.

Find the specific device instance in the Govee app and hit the setting Icon in the top right corner.


.. image:: /_static/devices/govee/settings.jpg
   :alt: Device page


Ensure that the wifi settings are correctly configured for you wifi network name and password. The device must be ON and connected to the app by bluetooth to achieve this the first time.

Then throw the LAN Control swith to on.


.. image:: /_static/devices/govee/LAN_switch.jpg
   :alt: Wifi Settings and LAN switch


While in this page, if you haven't already, take not of the device MAC address and ensure it is reserved in your router DHCP settings to a fixed IP address.


.. image:: /_static/devices/govee/MAC.jpg
   :alt: Note the MAC from here

You also need the device segment count from the Light Panel Layout page, which is under Layout and Calibration. In this example the segment count which you will use in the pixel count field in ledfx is 10.


.. image:: /_static/devices/govee/segments.jpg
   :alt: Adding a device


--------------------------
Ledfx Device Configuration
--------------------------

Ledfx does not currently support auto discovery for Govee.

Devices should be on a fixed IP addess through DHCP reservation against the Govee device MAC address via your router configuration.

Via the Add Device button in the Ledfx UI, select Govee.

Input your desired device name in the Name field.

Input number of segments as seen in the Govee app in the Pixels Count field.

Input the IP address of the device in the IP Address field.

Currently the default refresh rate is set to 40 on govee devices. This is from very limited testing, users are encouraged to test and provide feedback on the optimal refresh rate for their devices.


.. image:: /_static/devices/govee/add_govee.png
   :alt: Adding a device


Hit add and, your Govee device should now be available in the devices view.

Connection refresh
------------------

If Ignore Status is set to the default Off, If Govee device does not respond to a device status enquirey at ledfx startup, it will be marked offline.

If the device is powered on, or otherwise made available after startup, pressing the refresh button on the device will attempt to reconnect to the Govee device.


.. image:: /_static/devices/govee/refresh.png
   :alt: Refesh connection

If you have firewall issues blocking Port 4002 the status check can be disabled by setting Ignore Status to On. Ledfx will assume that the devices is available.
