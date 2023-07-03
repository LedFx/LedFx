============================
   Installation and Setup
============================

LedFx is a network controller that aims to enable synchronization of multiple lights across a network.
LedFx doesn't currently support local control of LED strings, so you need a separate device
(e.g., ESP8266/ESP32) to control the LEDs directly. To be able to add your LED strips to LedFx your device
needs to be capable of receiving data either via the E1.31 sACN protocol or a generic (simple)
UDP protocol. See below for a list of tested ESP8266 firmware that can be used with LedFx.

Here is everything you need to get started with LedFx:

    #. A Computer (or Raspberry Pi) with Python >= 3.8
    #. An E1.31 capable device with addressable LEDs connected

        - Commercial grade DMX controllers
        - ESP8266 modules can be purchased for as little as $2 USD from AliExpress

.. warning:: Anaconda is no longer recommended for installing LedFx. We have removed all references to Anaconda. If you are coming from an old install, we recommend removing Anaconda completely.

Here is a list of tested ESP8266 firmware that works with LedFx:

    - WLED_ is preferred and has lots of great firmware effects (ESP32/ESP8266)
    - ESPixelStick_ is a great E1.31 based firmware
    - `Scott's Audio Reactive Firmware`_ which inspired this project!

Windows Installation
----------------------

To get started on Windows please use our `LedFx Windows Installer`_.

.. note:: See :ref:`this page <win-dev-install>` for alternative installation instructions for Windows.

Linux Installation
--------------------

To install on Linux first ensure you have at least Python 3.8 installed.

**1.** Install LedFx and all the dependencies using our `LedFx Bash Install Script`_:

.. code:: console

    $ curl -sSL https://install.ledfx.app | bash

**2.** Follow the instructions presented by the installer.

macOS Installation
--------------------

To install on macOS first ensure you have at least Python 3.8 installed.

**1.** Install LedFx and all the dependencies using `homebrew`_ and pip:

.. code:: console

    $ brew install portaudio
    $ python3 -m pip install ledfx

**2.** Alternatively, install LedFx in a `python venv`_:

.. code:: console

    $ python3 -m venv ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ python -m pip install -U pip setuptools wheel
    $ python -m pip install ledfx

**3.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: console

    $ ledfx --open-ui

macOS Installation @frontend_beta branch (Apple Silicon)
----------------------------------------------------------------

To install on macOS (Apple Silicon) first ensure you have at least Python 3.8 installed.

**1.** Install LedFx and all the dependencies using `homebrew`_ in a `python venv`_:

.. code:: console

    $ brew install python@3.9
    $ brew install portaudio --HEAD
    $ brew install virtualenv
    $ virtualenv -p python3.9 ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ pip install --force-reinstall git+https://github.com/LedFx/LedFx

    ** --force-reinstall assures that you will be up to date whenever you run the command


**2.**  If you get a numpy/aubio error please do the following:

.. code:: console

    $ pip uninstall numpy aubio
    $ pip install numpy --no-cache-dir
    $ pip install aubio --no-cache-dir

**3.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: console

    $ ledfx --open-ui

Raspberry Pi Installation
---------------------------

.. note::
  This installation method is still in development. Use at your discretion.

.. note::
  To use LedFx on a pi you will need a USB audio card.

Verify you have Python 3.8 or greater by running ``python3 --version``

**1.** Modify /usr/share/alsa/alsa.conf:

We need to change the default audio card from the built-in hardware on the pi to the USB audio card in use.

.. code:: console

    $ sudo nano /usr/share/alsa/alsa.conf

Look for the following lines and change them accordingly:

FROM:

.. code-block:: shell

    defaults.ctl.card 0
    defaults.pcm.card 0

TO:

.. code-block:: shell

    defaults.ctl.card 1
    defaults.pcm.card 1

**2.** Install LedFx and all the dependencies using our `LedFx Bash Install Script`_:

.. code:: console

    $ curl -sSL https://install.ledfx.app/ | bash

Device Firmware
-----------------

Please visit one of the following links to obtain firmware for your ESP8266/ESP32 device that works with LedFx.

    * ESPixelStick_

        - Compatible Devices:

          - ESP8266
          - :doc:`Configuration Settings </configuring>`

    * `Scott's Audio Reactive Firmware`_

        - Compatible Devices:

          - ESP8266
          - :doc:`Configuration Settings </configuring>`

    * WLED_

        - Compatible Devices:

          - ESP8266
          - ESP32
          - :doc:`Configuration Settings </configuring>`

.. Links Down Here

.. _`LedFx Windows Installer`: http://ledfx.app/download
.. _`LedFx Bash Install Script`: https://install.ledfx.app
.. _`homebrew`: https://docs.brew.sh/Installation
.. _`python venv`: https://docs.python.org/3/tutorial/venv.html
.. _`Scott's Audio Reactive Firmware`: https://github.com/scottlawsonbc/audio-reactive-led-strip
.. _ESPixelStick: https://github.com/forkineye/ESPixelStick
.. _WLED: https://github.com/Aircoookie/WLED
