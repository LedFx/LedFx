LedFxController
===============

LedFx is a network based LED effect controller with support for a wide range of effects. Effect range from simple static gradients all the way to audio reactive effects that dance to music!

To get started with LedFx run the following from the project root:

.. code:: bash

    python setup.py install
    ledfx --open-ui

Device Support
==============

LedFx currently only supports E1.31 capable devices, including the `ESPixelStick firmware <https://github.com/forkineye/ESPixelStick/>`__ for any ESP8266 based controller. Upon first launch LedFx will create a default configuration file in the '.ledfx' folder inside the active user profile. The exact path will be printed to the command window. To add a device modify config.yaml as follows:

.. code-block:: yaml

    devices:
    - type: e131
        name: Sample Device
        host: 192.168.1.100
        universe: 1
        channel_offset: 0
        channel_count: 300
        max_brightness: 1.0

Optionally, the config can be simplified down to:

.. code-block:: yaml

    devices:
    - type: e131
        name: Sample Device
        host: 192.168.1.100
        pixel_count: 100

Web-Interface
=============

LedFx is intended to be ran on a small PC such as a Raspberry Pi, thus all configuration is done through a web-interface. The current UI is very simple and enable control of an individaul device's effect, as well as providers a way to visualize the effect.

|screenshot-webinterface|

.. |screenshot-webinterface| image:: https://raw.githubusercontent.com/ahodges9/LedFx/master/web_interface.png