================================
Installation and Setup
================================

LedFx is a network controller that aims to enable synchronization of multiple lights across a network. LedFx doesn't currently support local control of LED strings so you will need a seperate device (e.g. ESP8266) to directly control the LEDs. To be able to add your LED strips to LedFx your device will need to be capable of receiving data either via the E1.31 sACN protocol, or a generic (simple) UDP protocol. See below for a list of tested ESP8266 firmware that can be used with LedFx.

Here is everything you need to get started with LedFx:

    #. A Computer (or Raspberry Pi) with Python 3.6 or 3.7 (`Anaconda <https://www.anaconda.com/download/>`__ is recommended on Windows)
    #. A E1.31 capable device with addressiable LEDs connected
    
        - Commercial grade DMX controllers
        - ESP8266 modules can be purchased for as little as $2 USD from Aliexpress

Here is a list of tested ESP8266 firmware that work with LedFx:

    - `ESPixelStick <https://github.com/forkineye/ESPixelStick>`_ is a great E1.31 based firmware
    - `Scott's Audio Reactive Firmware <https://github.com/scottlawsonbc/audio-reactive-led-strip>`_ which inspired this project!
    - `WLED <https://github.com/Aircoookie/WLED>`_ has lots of firmware effects and supports E1.31 and UDP

Windows Installation
====================
To get started on Windows it is highly recommended that you use `Anaconda <https://www.anaconda.com/download/>`__ to make installation of Cython components easier.

First, create a `conda virtual environment <http://conda.pydata.org/docs/using/envs.html>`__ (this step is optional but highly recommended)

.. code:: bash

    conda create -n ledfx
    conda activate ledfx

Install LedFx and all the dependencies using pip and the conda package manager

.. code:: bash

    conda config --add channels conda-forge
    conda install aubio portaudio pywin32
    pip install ledfx
    
Launch LedFx (with the 'open-ui' option to launch the browser):

.. code:: bash

    ledfx --open-ui

Linux Installation
==================
To install on Linux first ensure you have at least Python 3.6 (optionally use `Anaconda <https://www.anaconda.com/download/>`__) installed. 

Install LedFx and all the dependencies using apt-get and pip:

.. code:: bash

    sudo apt-get install portaudio19-dev
    pip install ledfx
    ledfx --open-ui

Device Configuration
====================
Once you have LedFx running it's time to add devices! Once you have a device setup with appropriate firmware for integration to LedFx nagivate the the 'Device Management' page and click the '+' in the bottom right. Add the device using the following configuration based on your firmware:

    * `ESPixelStick <https://github.com/forkineye/ESPixelStick>`_
    
        - Add the device as a E1.31 device. The default E1.31 settings should work fine.
        
    * `Scott's Audio Reactive Firmware <https://github.com/scottlawsonbc/audio-reactive-led-strip>`_
    
        - Add the device as a UDP
        - Click 'Additional Properties' and check 'Include Indexes'
        
    * `WLED <https://github.com/Aircoookie/WLED>`_
    
        - Enabled E1.31 support from the WLED web-interface
        - Add the device as an E1.31 device
        - If you have more than 170 LEDs click 'Additional Properties' and set the 'Universe Size' to 510
