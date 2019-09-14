LedFx
=================================================================================
|Build Status| |License| |Discord|

WARNING: This project is in early development, so expect to encounter minor issues along the way. If you have issues either join the discord or open an issue.

LedFx is a network based LED effect controller with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266 nodes allowing for cost effectvice syncronized effects across your entire house!

For installation instructions see the `documentation <https://ahodges9.github.io/LedFx/>`__.

Devolopment Plan
---------
What do you think of the below ideas @ahodges9 @not-matt ? Keen to know everyone thoughts 😃 

### Editable Device
_Environment: Device Management_
Ability to edit the device.

### Basic Device Effect Saving (bug)
https://github.com/simon-wh/LedFx/commits?author=simon-wh
Tested and is working. Thanks @simon-wh 👍 
Got this bug though: https://github.com/Mattallmighty/LedFx/issues/2

### Save Presets
_Environment(New): Presets_
Create "Presets" of all LEDs devices current effect settings.

### Front End committed effect
_Environment(New): Device_
Front end: Keep current set effect in place, if navigate to another device.
Example: if you navigate to LED1 with energy -> set effect, then click on LED2 and put in place with beat-> set effect, navigate back to LED1, this should keep energy in place.

### Group Devices
_Environment: Device Management_
Within Manage Devices, ability to group devices, so can set effect and deploys to two devices at the same time.
Example: Manage Devices, can edit: LED1 to link with LED2. When LED1 is updated, so is LED2. LED2 will be greyed out/cannot select device option.

### New effect: WLED
_Environment: Device_
Within Device, effect option will be: WLED.

As soon as selected WLED from dropdown, disables E1.31 multicast of the device, and will then have full flexibility to select Effects, Palettes, Effect Intensity - as the option is selected.

Backend: https://github.com/Aircoookie/WLED/wiki/HTTP-request-API

### Keyboard macro
_Environment(New): Macro_
Assign a keyboard key to a preset.
Then maybe support Launchpad Novation to change lighting effects.

### Audio Channels 
_Environment: Device Management_
Within Manage Devices, can edit the LED1, to assign reactive audio settings for channels from one of the following options:
- mono
- stereo
- left
- right

### Spotify API - song + right time = put in place defined preset
_Environment(New): Web page banner, like Soundcloud_
Spotify API get users current track.
Front end banner displays Spotify User's Currently Playing Track, with buttons for Play/Pause, Next track.

There will also be a dropdown of the current presets saved and a button that creates a trigger for if this song, and this time, then apply this Preset.
https://developer.spotify.com/documentation/web-api/reference/player/get-the-users-currently-playing-track/

Demos
---------

We are actively adding and perfecting the effects, but here is a quick demo of LedFx running three different effects synced across three different ESP8266 devices:

.. image:: https://raw.githubusercontent.com/Mattallmighty/LedFx/master/demos/Example%20UI.PNG
.. image:: https://raw.githubusercontent.com/ahodges9/LedFx/master/demos/ledfx_demo.gif

.. |Build Status| image:: https://travis-ci.org/ahodges9/LedFx.svg?branch=master
   :target: https://travis-ci.org/ahodges9/LedFx
.. |License| image:: https://img.shields.io/badge/license-MIT-blue.svg
.. |Discord| image:: https://img.shields.io/badge/chat-on%20discord-7289da.svg
   :target: https://discord.gg/wJ755dY
