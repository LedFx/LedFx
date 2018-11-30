================================
Installation and Setup
================================

Overview
==============
LedFx is a network controller that aim to enable synchronization of multiple lights across a network. To be able to link your LED strips with LedFx you will need a device capable of speaking either the E1.31 sACN protocol, or a generic UDP protocol.

Here is what you need to get started with LedFx:
* A Computer (or RaspberryPi) with Python 3.6 or 3.7 (`Anaconda <https://www.anaconda.com/download/>`__ is recommended on Windows)
* A E1.31 capable device
    * Commercial grade DMX controllers
    * ESP8266 modules can be purchased for as little as $2 USD from Aliexpress

Here is a list of tested ESP8266 Firmware's that work with LedFx:
    * `ESPixelStick <https://github.com/forkineye/ESPixelStick>`_ works as a great E1.31 device
    * `WLED <https://github.com/Aircoookie/WLED>`_ works as either a UDP device or E1.31 device


Windows Installation
====================
To get started on Windows it is highly recommended that you use `Anaconda <https://www.anaconda.com/download/>`__ to make installation of Cython components easier.

First, create a `conda virtual environment <http://conda.pydata.org/docs/using/envs.html>`__ (this step is optional but highly recommended)

.. code:: bash

    conda create -n ledfx
    conda activate ledfx

Install dependencies using pip and the conda package manager

.. code:: bash

    conda config --add channels conda-forge
    conda install aubio portaudio pywin32
    pip install ledfx
    
Launch LedFx (with the 'open-ui' option to launch the browser):

.. code:: bash

    ledfx --open-ui

Linux Installation
==================
To install on Linux first ensure you have at least Python 3.6 (optionally use `Anaconda <https://www.anaconda.com/download/>`__) installed. Then, install the dependencies and LedFx.

.. code:: bash

    sudo apt-get install portaudio19-dev
    pip install ledfx
    ledfx --open-ui