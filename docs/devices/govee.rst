Govee Device
============

Ledfx has now added support for Govee LAN enabled devices that are Razer / Dreamview compatible.

Ledfx has only limited access to examples, so if you find a device that should be supported by is not, please raise in discord `Help and Support <https://discord.gg/h3Atx4mkCh>`_

At the time of writing compatible Govee products were listed at this link under the `Supports Razer/Dreamview tab <https://desktop.govee.com/razer/devices>`_

It is not known exhaustively, which of these are truly functional against ledfx current integration.

Known working examples include:

* H6061 Glide Hexa Light Panels
* H6167 Govee TV Backlight For 40-50 inch TVs
* H61BA Govee RGBICW LED Strip Light 16.4 ft
* H61D5 Neon Rope Light 2 16.4 FT
* H615C RGB LED Strip Light 50 FT
* TBD: add more here on discovery...

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


Hit add and ... profit ...



