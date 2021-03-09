===================
   Configuration
===================

.. _conf-firmware:

Firmware Specific
-------------------

Once you have LedFx installed, it's time to add some devices! Make sure you have a device with appropriate
firmware for integration with LedFx. Open the LedFx UI and navigate to the 'Device Management' page.
Click the "Add Device" button at the lower right of the web page. Add the device using the following
configuration based on your firmware:

    * ESPixelStick_

        - Add the device as an E1.31 device.
        - The default E1.31 settings should work fine.

    * `Scott's Audio Reactive Firmware`_

        - Add the device as a UDP device.
        - Click 'Additional Properties' and check the 'Include Indexes' box.

    * WLED_

        - Enable E1.31 support from the 'Sync Settings' page on the WLED web-interface.
        - Add the device as an E1.31 device.
        - If you have more than 170 LEDs click 'Additional Properties' and set the 'Universe Size' to 510.

.. Links Down Here

.. _`Scott's Audio Reactive Firmware`: https://github.com/scottlawsonbc/audio-reactive-led-strip
.. _ESPixelStick: https://github.com/forkineye/ESPixelStick
.. _WLED: https://github.com/Aircoookie/WLED