=====================
   Troubleshooting
=====================

Install Issues
--------------

Pyaudio:

.. code:: console

    $ conda install -c anaconda pyaudio

Windows
-------

.. _win-alt-install:

Alternative Install Instructions:
+++++++++++++++++++++++++++++++++

.. code:: doscon

    > conda create -n ledfx-git python=3.6
    > conda activate ledfx-git
    > conda config --add channels conda-forge
    > conda install pywin32 portaudio aubio
    > conda install -c anaconda pyaudio
    > cd %HOMEPATH%
    > mkdir ledfx
    > git clone https://github.com/ahodges9/LedFx.git ledfx
    > cd ledfx
    > pip install -r requirements.txt
    > python setup.py install
    > ledfx --open-ui

.. _win-dev-install:

No Conda Installation (good for devs) (requires Visual Studio Build Tools):
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


install python 3.7.9
install visual studio build tools for win10 
  https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2019
  "visual c++ build tools"
  default install options
reboot
open start menu -> x86 native build tools command prompt for VS 2019 

..code:: doscon

    > python -m venv C:/ledfx
    > C:\ledfx\Scripts\activate.bat
    > pip install pipwin
    > pipwin install pyaudio

download ledfx (dev) from github
put this wherever you want
cd to this directory

..code:: doscon

    > python setup.py develop
    > ledfx


Dev Branch Install:
+++++++++++++++++++

.. code:: doscon

    > conda create -n ledfxdevelopement-git
      y
    > conda activate ledfxdevelopement-git
    > conda config --add channels conda-forge
    > conda install pywin32 portaudio aubio
      y
    > cd %HOMEPATH%
    > mkdir ledfx_dev_branch
    > git clone https://github.com/ahodges9/LedFx.git -b dev ledfx_dev_branch
    > cd ledfx_dev_branch
    > pip install -r requirements.txt
    > python setup.py install
    > python setup.py develop
    > yarn install
    > npm run build
    > ledfx --open-ui

Firmware Issues
---------------

WLED
++++

  - Sending data, WLED going into E1.31 mode but lights not working?

    - Try turning off multicast and setting the start universe to 1.

  - As long as the universe size is set to 510 LedFx should output to all pixels. Maybe something in the code is not working past 1 universe as 1 universe is 170 LEDs

  - Make sure "disable wifi sleep" is ticked in WiFi Settings on the WLED web interface.

  - How many devices do you have?

    - Try 1 WLED device to start and work your way up to see where the problem lies, whilst monitoring your computer performance usage.

  - Determine if it’s a networking problem:
    Try pinging the device, LedFx is extremely latency sensitive.
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
LAN IP opens up the port, 8383 in your case, to other devices on your LAN from your host's IP.

Speaker Sound
-------------

My solution to this exact problem is Chromecast audios, I have two in a group and Chromecast to the group.
One of them is connected to my DAC that is then connected to my amplifiers, and another is connected to a line
in on my computer in a separate room that LedFx is running on.

They're perfectly synchronised, but if you need to, you can do a delay on any of the Chromecasts within the group
to adjust sync.

Windows:
++++++++

https://thegeekpage.com/stereo-mix/

Squeezebox Server - Logitech
++++++++++++++++++++++++++++

Multiroom: https://www.picoreplayer.org/

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

1. Disable WiFi Sleep Mode on WLED.
2. Reduce FPS to 30, and set 'Force Refresh' to true.

**Access via LAN**

I added host: 0.0.0.0 to the LedFx config and now it works fine!
https://github.com/ahodges9/LedFx/issues/62

Need more help?
---------------

Reach out to the LedFx team through Discord. Preferably copy and paste with your answers below

  - New build/recent upgrades?

  - python version?

  - LedFx version you are using?

  - restarted your PC and issue continues?

  - any changes/deleted your LedFx config file?

  - Problem: