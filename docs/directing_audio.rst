Directing Audio
===============

Here we explain how to pipe your system audio directly to LedFx without
having to use a microphone or any other peripheral devices.

Linux
-----

Tested on Ubuntu 20.10 64-bit.

Requirements
~~~~~~~~~~~~

-  `PulseAudio <https://www.freedesktop.org/wiki/Software/PulseAudio/?>`__
-  `PulseAudio Volume
   Control <https://freedesktop.org/software/pulseaudio/pavucontrol/>`__

Instructions
~~~~~~~~~~~~

-  In the LedFx UI under "Settings" -> "Audio Input", choose "pulse" as
   the current device |LedFx UI|
-  In PulseAudio Volume Control under "Recording", choose "ALSA plug-in"
   and set "Capture from" to the audio stream you want to capture (e.g.
   "Monitor of Built-in Audio Analog Stereo") |PulseAudio Volume
   Control|

macOS
-----

Tested on macOS Catalina 10.15.7.

Requirements
~~~~~~~~~~~~

-  `BlackHole <https://github.com/ExistentialAudio/BlackHole>`__

Instructions
~~~~~~~~~~~~

-  In Audio MIDI Setup, create a `Multi Output
   Device <https://github.com/ExistentialAudio/BlackHole/wiki/Multi-Output-Device>`__
   |Multi Output Device|
-  In Audio MIDI Setup, choose "BlackHole 2ch" and set it as "Input"
   |Multi Output Device|
-  In the LedFx UI under "Settings" -> "Audio Input", choose "BlackHole
   2ch" as the current device |Multi Output Device|

Alternatives
~~~~~~~~~~~~

-  `Loopback <https://rogueamoeba.com/loopback/>`__: Can direct the
   audio output of individual applications but requires expensive
   license to run more than 20 minutes.

.. |LedFx UI| image:: ./_static/direct_audio_linux_1.png
.. |PulseAudio Volume Control| image:: ./_static/direct_audio_linux_2.png
.. |Multi Output Device| image:: ./_static/directing_audio_macos_1.png
.. |Multi Output Device| image:: ./_static/directing_audio_macos_2.png
.. |Multi Output Device| image:: ./_static/directing_audio_macos_3.png
