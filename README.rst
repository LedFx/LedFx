===========
   LedFx
===========
|Build Status| |License| |Build Status Docs| |Discord|

LedFx is a network based LED effect controller with support for advanced
real-time audio effects! LedFx can control multiple devices and works great
with cheap ESP8266/ESP32 nodes allowing for cost effectvice syncronized effects
across your entire house!

Installation
------------

Basic Linux Installation (Debian/Ubuntu):

.. code:: console

   $ sudo apt-get install portaudio19-dev
   $ pip install ledfx
   $ ledfx --open-ui

For full installation instructions see :doc:`installing`.

Configuration
-------------

LedFx can be configured in a number of ways. To be able
to add your LED strips to LedFx your device needs to be
capable of receiving data either via the E1.31 sACN
protocol or a generic (simple) UDP protocol.

For more information see the :doc:`Configuration Docs <configuring>`.

.. Demos
.. ---------

.. We are actively adding and perfecting the effects, but here is a quick demo of LedFx running three different effects synced across three different ESP8266 devices:

.. .. image:: https://raw.githubusercontent.com/ahodges9/LedFx/gh-pages/demos/ledfx_demo.gif

.. |Build Status| image:: https://travis-ci.org/ahodges9/LedFx.svg?branch=master
   :target: https://travis-ci.org/ahodges9/LedFx
   :alt: Build Status
.. |Build Status Docs| image:: https://readthedocs.org/projects/ledfx/badge/?version=latest
   :target: https://ledfx.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
.. |License| image:: https://img.shields.io/badge/license-MIT-blue.svg
   :alt: License
.. |Discord| image:: https://img.shields.io/badge/chat-on%20discord-7289da.svg
   :target: https://discord.gg/wJ755dY
   :alt: Discord