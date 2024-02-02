=====================
   Troubleshooting
=====================

Firmware Issues
---------------

WLED
++++

  - Sending data, WLED going into E1.31 mode but lights not working?

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

Did you try host: 0.0.0.0 or host: your-ipv4 (i.e.: 192.168.1.10)? The 127 is your localhost internal network and
running anything on that subnet will only be available from that device. Putting it on 0.0.0.0 or your host's
LAN IP opens up the port, 8888 in our case, to other devices on your LAN from your host's IP.

Ledfx Configuration File Corruption Recovery
--------------------------------------------

If you are concerned that your ledfx config.json is corrupted.

Everything was working and you changed an effect setting or similar, and now things no longer work,
even if you restart / reboot / reinstall, it is likely that the config.json has persisted a configuration
that is triggering a bug and causeing a crash from startup.

We will be very interested in a copy of your config.json file, please share in discord with context, but to
recover, and confirm it is a corrupted config.json, you can delete the file and restart ledfx.

Launch ledfx with the --clear-config option to backup the config.json file in the .ledfx directory and create
a fresh default config in its place

   .. code:: console

        ledfx --clear-config

Note the backup json file will be named according to the following format

config_backup_YYYY-MM-DD_HH-MM-SS.json

It will be in the .ledfx directory along with the ledfx.log instances

Please note: This is a dotfile naming convention and may be hidden by default in your file manager.

.ledfx directory will be located in a number of possible locations according to OS.

Examples of being, but not limited to, the following locations

Windows:

   .. code:: console

        C:\Users\username\AppData\Roaming\.ledfx

Linux:

    .. code:: console

        /home/username/.ledfx

MacOS:

   .. code:: console

        /Users/username/.ledfx


Speaker Sound
-------------

My solution to this exact problem is ChromeCast audios, I have two in a group and ChromeCast to the group.
One of them is connected to my DAC that is then connected to my amplifiers, and another is connected to a line
in on my computer in a separate room that LedFx is running on.

They're perfectly synchronized, but if you need to, you can do a delay on any of the ChromeCasts within the group
to adjust sync.

Windows:
++++++++

For setting up "Stereo Mix" recording device , please see https://thegeekpage.com/stereo-mix/

If "Stereo Mix" is not picking up any sound, your "Playback" device is probably digital (e.g.: HDMI) and external tool must be used. See the "Directing Audio" documentation page.

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

**DPC Latency**

LedFx is *extremely* latency sensitive and will expose inherit weaknesses in WiFi.
To minimize this, we reccomend:

1. Disabling WiFi Sleep Mode on WLED.
2. Minimize WiFi activity on your network - using ethernet where possible.
3. Ensure router appropriate for number of devices and amount of traffic.
4. Attempting to ensure your WiFi access point is located in an appropriate area, and is using an appropriate WiFi channel.

**Access via LAN**

All current builds should be able to be accessed from LAN - please ensure that you allow traffic from port 8888 from the host machine.

Need more help?
---------------

Reach out to the LedFx team through Discord. Preferably copy and paste with your answers below

  - New build/recent upgrades?

  - python version?

  - LedFx version you are using?

  - restarted your PC and issue continues?

  - any changes/deleted your LedFx config file?

  - Problem:
