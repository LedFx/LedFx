   Welcome to LedFx ✨ *-Making music come alive!*
=====================================================
[![Build Status](https://github.com/LedFx/LedFx/actions/workflows/ci-build.yml/badge.svg)](https://github.com/LedFx/LedFx/actions/workflows/ci-build.yml) ![License](https://img.shields.io/badge/license-GPL3-blue.svg) [![Build Status Docs](https://readthedocs.org/projects/ledfx/badge/?version=main)](https://ledfx.readthedocs.io/) [![Discord](https://img.shields.io/badge/chat-on%20discord-7289da.svg)](https://discord.gg/xyyHEquZKQ)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg)](CODE_OF_CONDUCT.md)

[![banner](https://raw.githubusercontent.com/LedFx/LedFx/b8e68beaa215d4308c74d0c7d657556ac894b707/icons/banner.png)](https://ledfx.app/)

LedFx website: https://ledfx.app/

What is LedFx?
----------------

What LedFx offers is the ability to take audio input, and instantaneously processes the audio into realtime light show to multiple LED strips/matrix.
No need to spend hours on end to program one song to program your LEDs, as LedFx will do this all for you!

LedFx real-time LED strip music visualization effect controller using is a network based devices (ESP8266/ESP32/Raspberry Pi 4) with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266/ESP32 nodes allowing for cost effective synchronized effects across your entire house!

Demos
-------

We are actively adding and perfecting the effects, but here is a quick demo of LedFx running three different effects synced across three different ESP8266 devices:

[broken link]

📑 Quick start guide and documentation📖
------------------------------------------
Windows users can use the installer from the LedFx website: https://ledfx.app/download/

Mac and Linux are also supported, though currently do not have installers.
For detailed installation instructions, see the [installation documentation](https://ledfx.readthedocs.io/en/latest/installing.html).

😍 Show me how to make one!
-----------------------------

The below image describes a basic setup - LedFx running on PC, communicating with a WLED Device controlling an LED strip.

![diagram](https://i.imgur.com/vzyHNwG.png)


| Component | Example |
| --------- | ------- |
| Computer running LedFx | Windows 10, [LedFx.exe](https://ledfx.app/download/) |
| Networked device controlling LED Strip | ESP8266 NODEMCU v3 running [WLED](https://github.com/Aircoookie/WLED/wiki) |
| Addressable LED strip | DC5V WS2812B 5 meters 60LED/m IP67 |
| Power supply for LED Strip and ESP | 5V 10 amps LED Power Supply |
| Something to connect the wires together! | Soldering iron/solder |


1. **Build your networked LED Strip.**
      - For most, this is the difficult step. Don't worry! There's guides here and online, and plenty of people able to help on WLED and LedFx Discord.
      - Follow the WLED guide to connect the LED strip and ESP together: https://github.com/Aircoookie/WLED/wiki.
      - Flash WLED to the ESP device: https://github.com/Aircoookie/WLED/wiki/Install-WLED-binary
      - Ensure all WLED devices are powered on, and connected to your Wi-Fi.
      - Test you can access the WLED web interface from your PC. If so, then you're good to go!

2. **Install LedFx.**
      - After you have WLED installed on your ESP device, download: [LedFx.exe](https://ledfx.app/download/) and install LedFx.
      - For Mac and Linux, see the [installation documentation](https://ledfx.readthedocs.io/en/latest/installing.html) or [LedFx Guide](https://ledfx.readthedocs.io/en/latest/index.html).

3. **Direct computer audio output to LedFx.**
      - Follow guide, [How to: Enable Stereo Mix in Windows 10](https://thegeekpage.com/stereo-mix/).
      - Alternatively use [Voicemeeter](https://vb-audio.com/Voicemeeter/index.htm). [Voicemeeter tutorial](https://youtu.be/ZXKDzYXS60o?start=27&end=163).
      - More information for [Linux and macOS users here](https://ledfx.readthedocs.io/en/latest/directing_audio.html).
      - Play some music in the background.

4. **Start LedFx.**
      - Your WLED devices should appear in LedFx, automagically configured and ready to go! 🎆🔥
      - If not, on the left hand side, click on Device Management -> `Find WLED devices` button, or `Add Device` to add them manually.
      - If they're still not showing up, make sure they're powered on and properly connected to your WiFi.

5. **Start using effects!**
      - Click on the device, select an effect eg `scroll(Reactive)`, and press `Set effect` button.
      - Your lights should now be reacting realtime to your music! Enjoy the show 🌈


🧑‍💻 Join the LedFx Community
------------------------------

Join the Discord server to discuss everything about LedFx!  |Discord|

To join, click on the Discord button below:

[![](https://discordapp.com/api/guilds/469985374052286474/widget.png?style=banner2)](https://discord.com/invite/xyyHEquZKQ)

Contributing
--------------
Pull requests are welcome. Once tested, contact LedFx developer community on Discord to discuss the next step.
We expect and require all contributors to read, understand and follow our code of conduct.

Credits: [Contributors-&-About](https://ledfx.app/about/)

License
---------
[GPL-3](https://choosealicense.com/licenses/gpl-3.0/)
