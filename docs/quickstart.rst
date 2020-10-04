============================
   Installation and Setup
============================

LedFx is a network controller that aims to enable synchronization of multiple lights across a network. LedFx doesn't currently support local control of LED strings, so you need a separate device (e.g., ESP8266) to control the LEDs directly. To be able to add your LED strips to LedFx your device needs to be capable of receiving data either via the E1.31 sACN protocol or a generic (simple) UDP protocol. See below for a list of tested ESP8266 firmware that can be used with LedFx.

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
--------------------

To get started on Windows it is highly recommended that you use Anaconda_ to make installation of Cython components easier.

**1.** Create a `conda virtual environment <http://conda.pydata.org/docs/using/envs.html>`_ (this step is optional but highly recommended):

.. code:: console

    $ conda create -n ledfx
    $ conda activate ledfx

**2.** Install LedFx and all the dependencies using pip and the conda package manager:

.. code:: bash

    $ conda config --add channels conda-forge
    $ conda install aubio portaudio pywin32
    $ conda install -c anaconda pyaudio
    $ pip install ledfx

**3.** Launch LedFx with the ``--open-ui`` option to launch the browser:

.. code:: bash

    $ ledfx --open-ui

Linux Installation
------------------

To install on Linux first ensure you have at least Python 3.6 installed (alternatively use Anaconda_).

**1.** Install LedFx and all the dependencies using apt-get and pip:

.. code:: bash

    sudo apt-get install portaudio19-dev
    pip install ledfx

**2.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: bash

    ledfx --open-ui

macOS Installation
------------------

To install on macOS first ensure you have at least Python 3.6 installed (alternatively use `Anaconda <https://www.anaconda.com/download/>`_).

**1.** Install LedFx and all the dependencies using homebrew and pip:

.. code:: bash

    brew install portaudio
    pip install ledfx

**2.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: bash

    ledfx --open-ui

**1.** Alternatively, create a `conda virtual environment <http://conda.pydata.org/docs/using/envs.html>`_:

.. code:: bash

    conda create -n ledfx python=3.7
    conda activate ledfx

**2.** Install LedFx and all the dependencies using pip and the conda package manager.

.. code:: bash

    conda config --add channels conda-forge
    conda install aubio portaudio
    pip install ledfx

**3.** Launch LedFx with the ``open-ui`` option to launch the browser:

.. code:: bash

    ledfx --open-ui

Device Configuration
--------------------

Once you have LedFx running, it's time to add some devices! After you have set up a device with appropriate firmware for integration with LedFx, navigate to the 'Device Management' page and click the "Add Device" button at the lower right of the web page. Add the device using the following configuration based on your firmware:

    * ESPixelStick_

        - Add the device as a E1.31 device. The default E1.31 settings should work fine.

    * `Scott's Audio Reactive Firmware`_

        - Add the device as a UDP
        - Click 'Additional Properties' and check 'Include Indexes'

    * WLED_

        - Enabled E1.31 support from the WLED web-interface
        - Add the device as an E1.31 device
        - If you have more than 170 LEDs click 'Additional Properties' and set the 'Universe Size' to 510

.. Links Down Here

.. _Anaconda: https://www.anaconda.com/download/
.. _`Scott's Audio Reactive Firmware`: https://github.com/scottlawsonbc/audio-reactive-led-strip
.. _ESPixelStick: https://github.com/forkineye/ESPixelStick
.. _WLED: https://github.com/Aircoookie/WLED