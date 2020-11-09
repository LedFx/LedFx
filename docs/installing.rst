============================
   Installation and Setup
============================

LedFx is a network controller that aims to enable synchronization of multiple lights across a network.
LedFx doesn't currently support local control of LED strings, so you need a separate device
(e.g., ESP8266/ESP32) to control the LEDs directly. To be able to add your LED strips to LedFx your device
needs to be capable of receiving data either via the E1.31 sACN protocol or a generic (simple)
UDP protocol. See below for a list of tested ESP8266 firmware that can be used with LedFx.

Here is everything you need to get started with LedFx:

    #. A Computer (or Raspberry Pi) with Python >= 3.6 (Anaconda_ is recommended on Windows)
    #. An E1.31 capable device with addressiable LEDs connected

        - Commercial grade DMX controllers
        - ESP8266 modules can be purchased for as little as $2 USD from Aliexpress

Here is a list of tested ESP8266 firmware that works with LedFx:

    - ESPixelStick_ is a great E1.31 based firmware
    - `Scott's Audio Reactive Firmware`_ which inspired this project!
    - WLED_ has lots of firmware effects and supports E1.31 and UDP

Windows Installation
----------------------

To get started on Windows it is highly recommended that you use Anaconda_ to make installation of Cython components easier.

Please see :ref:`this page <win-alt-install>` for alternative installation instructions for Windows.

**1.** Create a `conda virtual environment`_ (this step is optional but highly recommended):

.. code:: doscon

    > conda create -n ledfx
    > conda activate ledfx

**2.** Install LedFx and all the dependencies using pip and the conda package manager:

.. code:: doscon

    > conda config --add channels conda-forge
    > conda install aubio portaudio pywin32
    > conda install -c anaconda pyaudio
    > pip install ledfx

**3.** Launch LedFx with the ``--open-ui`` option to launch the browser:

.. code:: doscon

    > ledfx --open-ui

Linux Installation
--------------------

To install on Linux first ensure you have at least Python 3.6 installed (alternatively use Anaconda_).

**1.** Install LedFx and all the dependencies using apt-get and pip:

.. code:: bash

    $ sudo apt-get install portaudio19-dev
    $ pip install ledfx

**2.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: console

    $ ledfx --open-ui

macOS Installation
--------------------

To install on macOS first ensure you have at least Python 3.6 installed (alternatively use Anaconda_).

**1.** Install LedFx and all the dependencies using homebrew and pip:

.. code:: console

    $ brew install portaudio
    $ pip install ledfx

**2.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: console

    $ ledfx --open-ui

**1.** Alternatively, create a `conda virtual environment`_:

.. code:: console

    $ conda create -n ledfx python=3.7
    $ conda activate ledfx

**2.** Install LedFx and all the dependencies using pip and the conda package manager.

.. code:: console

    $ conda config --add channels conda-forge
    $ conda install aubio portaudio
    $ pip install ledfx

**3.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: console

    $ ledfx --open-ui

Raspberry Pi Installation
---------------------------

.. note::
  This installation method is still in development. Use at your discretion.

.. note::
  To use LedFx on a pi you will need a USB audio card.

Verify you have Python 3.6 or greater by running ``python3 --version``

**1.** Install, Create, and Activate a Python virtual environment:

.. code:: console

    $ sudo apt install python3-venv python3-pip
    $ python3 -m venv ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate

**2.** Install required LedFx dependencies via ``apt``:

.. code:: console

    $ sudo apt install portaudio19-dev libatlas-base-dev libavcodec58 libavformat58 -y

**3.** Install LedFx using ``pip``:

.. code:: console

    $ pip3 install ledfx-dev

**4.** Modify /usr/share/alsa/alsa.conf:

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

**5.** Finally, start LedFx:

.. code:: console

    $ cd ~/ledfx-venv/bin
    $ ./ledfx -v

Optionally, open the UI:

.. code:: console

    $ ./ledfx --open-ui

Device Firmware
-----------------

Please visit one of the following links to obtain firmware for your ESP8266/ESP32 device that works with LedFx.

    * ESPixelStick_

        - Compatible Devices:

          - ESP8266

        - :ref:`Configuration Settings <conf-firmware>`

    * `Scott's Audio Reactive Firmware`_

        - Compatible Devices:

          - ESP8266

        - :ref:`Configuration Settings <conf-firmware>`

    * WLED_

        - Compatible Devices:

          - ESP8266
          - ESP32

        - :ref:`Configuration Settings <conf-firmware>`

.. Links Down Here

.. _Anaconda: https://www.anaconda.com/download/
.. _`conda virtual environment`: http://conda.pydata.org/docs/using/envs.html
.. _`Scott's Audio Reactive Firmware`: https://github.com/scottlawsonbc/audio-reactive-led-strip
.. _ESPixelStick: https://github.com/forkineye/ESPixelStick
.. _WLED: https://github.com/Aircoookie/WLED
