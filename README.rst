===========
   Welcome to LedFx ✨ *-Making music come alive!*
===========
|Build Status| |License| |Build Status Docs| |Discord|

.. image:: https://i.imgur.com/SFWfhFr.png

LedFx website: https://ledfx.app/

***What is LedFx?***

LedFx is a network based LED effect controller with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266/ESP32 nodes allowing for cost effective syncronised effects across your entire house!
real-time LED strip music visualization using Python and the ESP8266 or Raspberry Pi.

What LedFx offers is the ability to  No need to spend hours on end to program a song to your LEDs, as LedFx will convert your audio to ny LedFx is a network controller that aims to enable synchronisation of multiple lights across a network. LedFx doesn’t currently support local control of LED strings, so you need a separate device (e.g., ESP8266/ESP32) to control the LEDs directly. To be able to add your LED strips to LedFx your device needs to be capable of receiving data either via the E1.31 sACN protocol or a generic (simple) UDP protocol. See below for a list of tested ESP8266 firmware that can be used with LedFx.

Demos	(click gif for video)
---------	

We are actively adding and perfecting the effects, but here is a quick demo of LedFx running three different effects synced across three different ESP8266 devices:

.. image:: https://raw.githubusercontent.com/ahodges9/LedFx/gh-pages/demos/ledfx_demo.gif
[![visualiser demo](/gh-pages/demos/ledfx_demo.gif)](https://www.youtube.com/watch?v=HNtM7jH5GXgD)

📑 Quick start guide and documentation📖
---------
LedFx website: https://ledfx.app/download/

**Quick start guide**

***What do I need to make one?***

* Hardware: You will need Windows PC, addressable LED strip, power supply, ESP8266/ESP32 or Raspberry Pi 3/4 

*Hardware: https://github.com/Aircoookie/WLED/wiki/Compatible-hardware*

* Software: `LedFx.exe`_, 

*For Example, @mattallmighty LedFx setup is:*
```
Hardware: ESP8266 NODEMCU v3, sda
Software: WLED, 
```

Option 1: ESP8266/ESP32 module/s
ESP8266/ESP32 modules can be purchased for as little as $2 USD from Aliexpress.
Ahttps://github.com/Aircoookie/WLED/wiki/Compatible-hardware


For installation instructions, see the [documentation](https://ledfx.readthedocs.io/en/docs/).

![How it works](https://github.com/Mattallmighty/audio-reactive-led-strip/blob/master/images/block-diagram.png?raw=true)

🧑‍💻 Join the LedFx Community 
---------	

Join the Discord server to discuss everything about LedFx!

<a href="https://discord.gg/KuqP7NE"><img src="https://discordapp.com/api/guilds/473448917040758787/widget.png?style=banner2" width="25%"></a>

Contributing
---------
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

Credits: _`Contributors-&-About`_

License
---------
`MIT`_


.. _`MIT`: https://choosealicense.com/licenses/mit/
.. _`LedFx.exe`: https://ledfx.app/download/
.. _`Contributors-&-About`: https://ledfx.app/about/
.. _`Contributors-&-About`: https://ledfx.app/about/

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
