=====================
   Troubleshooting
=====================

Firmware Issues
---------------

WLED
++++

  - Sending data, WLED going into E1.31 mode but lights aren't working?

    - Try turning off multicast and setting the start universe to 1.

  - As long as the universe size is set to 510 LedFx should output to all pixels. Maybe something in the code is not working past 1 universe as 1 universe is 170 LEDs

  - Make sure "disable WiFi sleep" is ticked in WiFi Settings on the WLED web interface.

  - How many devices do you have?

    - Try 1 WLED device to start and work your way up to see where the problem lies, whilst monitoring your computer performance usage.

  - Determine if it’s a networking problem:
    Try pinging the device - any large variances in ping will cause issues - LedFx is extremely latency sensitive.
    Command prompt ping the IP address of the WLED device. For example: ping 192.168.1.101

ESPixelStick
++++++++++++

The ESPixelStick firmware is extremely streamlined and by far the lowest latency option.

ESPixelStick will drive all LEDs via the RX pin (like any real pixel pusher FW should do) and will let you have
thousands of LEDs in any pixel order you want. The problem with the code is, it can't handle more than a single
universe, which limits you to 170 pixels. More advanced FW will consume input spanning multiple universes.

LedFx Configuration File
------------------------

By default the configuration file is located in %appdata%/.ledfx on Windows and ~/.ledfx on *nix.
It is called config.json - you can view it manually if required, and if there are any issues you can delete
it - LedFx will start with a fresh configuration. You will of course lose any devices and custom presets/scenes.

Speaker Sound
-------------

My solution to this exact problem is ChromeCast audios, I have two in a group and ChromeCast to the group.
One of them is connected to my DAC that is then connected to my amplifiers, and another is connected to a line
in on my computer in a separate room that LedFx is running on.

They're perfectly synchronized, but if you need to, you can do a delay on any of the ChromeCasts within the group
to adjust sync.

Mac OS X:
+++++++++++
Audio Errors
-------------
In newer version of Mac OS X you will be prompted to allow microphone permissions on first launch - you must allow
this otherwise LedFx won't be allowed access to audio. Please see
`this page <https://stackoverflow.com/questions/57940639/cannot-access-microphone-on-mac-mojave-using-pyaudio>`__ for more information.

Windows:
++++++++

https://thegeekpage.com/stereo-mix/

Squeezebox Server - Logitech
++++++++++++++++++++++++++++

MultiRoom: https://www.picoreplayer.org/

VBAN audio sync
+++++++++++++++

Using Voicemeeter use VBAN, also allows mobile phone app to play your audio. Needs a little tinkering between multi
speaker devices for ms delay. Make sure you have static IP addresses for your device and it does support up to 4
outgoing devices streams.

Alternatively:
https://www.audioanimals.co.uk/news/reviews/v-player-2-review-free-standalone-vst-host

Networking Improvements
-----------------------

**Latency**

LedFx is *extremely* latency sensitive and will expose inherit weaknesses in WiFi.
To minimize this, we recommend:

1. Disabling WiFi Sleep Mode on WLED.
2. Minimize WiFi activity on your network - using ethernet where possible.
3. Ensure router appropriate for number of devices and amount of traffic.
4. Attempting to ensure your WiFi access point is located in an appropriate area, and is using an appropriate WiFi channel.

**Access via LAN**

All current builds should be able to be accessed from LAN - please ensure that you allow traffic from port 8888 from the host machine.

.. _protocol_choice:
Protocol Choice
-----------------------

 Broadly speaking, UDP is the fastest protocol due to a lack of overheads - however it is limited to 480 LEDs. DDP as implemented in WLED is very close in performance with no pixel limits, and following that is E1.31 with similarly unrestricted pixel limits.
 In general, you should only really notice the difference on low power devices such as Raspberry Pi's and the like, however if you are having issues it is worth changing modes.


Need more help?
---------------

Reach out to the LedFx team through Discord. Preferably copy and paste with your answers below

  - New build/recent upgrades?

  - python version?

  - LedFx version you are using?

  - restarted your PC and issue continues?

  - any changes/deleted your LedFx config file?

  - Problem: