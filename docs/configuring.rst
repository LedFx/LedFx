===================
   Configuration
===================

Firmware Specific
-------------------

Once you have LedFx installed, it's time to add some devices! Make sure you have a device with appropriate
firmware for integration with LedFx. Open the LedFx UI and navigate to the 'Device Management' page.
Click the "Add Device" button at the top right of the web page. Add the device using the following
configuration based on your firmware:

    * ESPixelStick_

        - Add the device as an E1.31 device.
        - The default E1.31 settings should work fine.

    * `Scott's Audio Reactive Firmware`_

        - Add the device as a UDP device.
        - Click 'Additional Properties' and check the 'Include Indexes' box.

    * WLED_

    - Add WLED as UDP device
        - Enter the name for your device and IP address
        - Enter 21324 for the port
        - Enter the total number of pixels
        - Click "Show More" and enter 02 for "Data Prefix
        - Click Submit
    - Add WLED as E1.31 device
        - Enable E1.31 support from the 'Sync Settings' page on the WLED web-interface and reboot WLED
        - Enter the name and IP address
        - Enter the total number of pixels
        - Click Submit

.. Links Down Here

.. _`Scott's Audio Reactive Firmware`: https://github.com/scottlawsonbc/audio-reactive-led-strip
.. _ESPixelStick: https://github.com/forkineye/ESPixelStick
.. _WLED: https://github.com/Aircoookie/WLED