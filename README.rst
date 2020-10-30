===========
   Welcome to LedFx ✨ *-Making music come alive!*
===========
|Build Status| |License| |Build Status Docs| |Discord|

.. image:: https://i.imgur.com/SFWfhFr.png

LedFx website: https://ledfx.app/

***What is LedFx?*** 

What LedFx offers is the ability to take audio input, and instantanously processes the audio into realtime lightshow to multiple LED strips/matrix.
No need to spend hours on end to program one song to program your LEDs, as LedFx will do this all for you!

LedFx real-time LED strip music visualization effect controller using is a network based devices (ESP8266/ESP32/Raspberry Pi 4) with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266/ESP32 nodes allowing for cost effective syncronised effects across your entire house!

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

* Hardware Requirements: You will need Windows PC, addressable LED strip, power supply, soldering iron/solder, and one of the following devices: ESP8266 or ESP32 (Note: Raspberry Pi 3/4 is avialible, see `LedFx Guide`_ )

Example LedFx setup is:

.. code:: 

   Hardware: 5V 10 amps LED Power Supply, ESP8266 NODEMCU v3, DC5V WS2812B 5 meters 60LED/m IP67
   Software: `LedFx.exe`_(For Windows PC), `WLED`_(For ESP8266) 


Step 1: please follow WLED guide: https://github.com/Aircoookie/WLED/wiki
Ensure all WLED devices are powered on, and connected to your Wi-Fi 5Ghz.
From the WLED web-interface, LedFx will require led setup configured, user interface name (device name), and Sync setup enabled E1.31 support.

Step 2: After you have WLED installed on your ESP device, and configured the  download: `LedFx.exe`_ and install LedFx. 

Step 3: Follow guide, `How to: Enable Stereo Mix in Windows 10`_

Step 4: Start the LedFx program, and go into Device Management -> ``FInd WLED devices`` button.

Step 5: 

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
.. _`LedFx Guide`: https://ledfx.readthedocs.io/en/docs/index.html
.. _`WLED`: https://github.com/Aircoookie/WLED/wiki
.. _`Contributors-&-About`: https://ledfx.app/about/
.. _`How to: Enable Stereo Mix in Windows 10`: https://thegeekpage.com/stereo-mix/

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
