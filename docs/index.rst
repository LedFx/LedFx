================================
LedFx Documentation
================================

This project is still in very early development and the documentation is currently rather scarce. Stay tuned.

Installation
==============
To install LedFx first clone (or download) the repository and then simply run the following to install all dependencies and launch LedFx. As with most pyhthon projects its highly recommended to run LedFx in a virtual environment such as Anaconda.


.. code:: bash

    pip install ledfx
    ledfx --open-ui
    
Windows
--------------
To get started on Windows it is highly recommended that you use `Anaconda <https://www.anaconda.com/download/>`__ to make installation of Cython components easier.

Start by creating a new environment for LedFx:

.. code:: bash

    conda create -n ledfx python=3.7
    conda activate ledfx

Next install all the dependencies:

.. code:: bash

    conda config --add channels conda-forge
    conda install aubio portaudio pywin32
    
Install and launch LedFx:

.. code:: bash

    pip install ledfx
    ledfx --open-ui

Linux
--------------
WARNING: Linux is mostly untested

.. code:: bash

    sudo apt-get install portaudio19-dev
    pip install ledfx
    ledfx --open-ui

Device Support
==============
LedFx currently only supports networked attached lights that speak either the E1.31 sACN protocol, or a generic UDP protocol. There are a ton of options ranging from cheap ESP8266 based devices, to professional DMX/sACN controllers. NodeMCU's are great for beginners and you can run a small WS2812B or 5V WS2811 without any soldering!

Here is a list of tested ESP8266 Firmware's that work with LedFx:
    * `ESPixelStick <https://github.com/forkineye/ESPixelStick>`_ works as a great E1.31 device
    * `WLED <https://github.com/Aircoookie/WLED>`_ works as either a UDP device or E1.31 device


Links
==============

.. toctree::
   :maxdepth: 2
   :glob:

   developer/*
   
.. toctree::
   :maxdepth: 1
   :glob:

   api/*
