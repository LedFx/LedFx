================================
LedFx Documentation
================================

This project is still in very early development and the documentation is currently rather scarce. Stay tuned.

Installation
==============
To install LedFx first clone (or download) the repository and then simply run the following to install all dependencies and launch LedFx. As with most pyhthon projects its highly recommended to run LedFx in a virtual environment such as Anaconda.


.. code:: bash

    python setup.py install
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
    pip install ledfx
    
You should now be able to launch LedFx:

.. code:: bash

    ledfx --open-ui

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
