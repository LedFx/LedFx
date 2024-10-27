Govee Device
============

Ledfx has now added support for Govee LAN enabled devices that are Razer / Dreamview compatible.

Ledfx has only limited access to examples, so if you find a device that should be supported by is not, please raise in discord `Help and Support <https://discord.gg/h3Atx4mkCh>`_

At the time of writing compatible Govee products were listed at this link under the `Supports Razer/Dreamview tab <https://desktop.govee.com/razer/devices>`_

Device Configuration
--------------------

Ledfx does not currently support auto discovery for Govee.

Devices should be on a fixed IP addess through DHCP reservation against the Govee device MAC address via your router configuration.

Via the Add Device button in the Ledfx UI, select Govee.

Input your desired device name in the Name field.

Input number of segments as seen in the Govee app in the Pixels Count field.

Input the IP address of the device in the IP Address field.

Currently the default refresh rate is set to 40 on govee devices. This is from very limited testing, users are encouraged to test and provide feedback on the optimal refresh rate for their devices.


.. image:: /_static/devices/add_govee.png
   :alt: Adding a device


Hit add and ... profit ...



