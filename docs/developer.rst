=======================
   Development Setup
=======================

The development workflow is still being worked on, but this page covers the current state of the world.

------------------------------

-------------------------
   Backend Development
-------------------------

Linux
-------

**1.** Clone the dev branch from the LedFx Github repository:

.. code:: bash

    $ git clone https://github.com/ahodges9/LedFx.git -b dev
    $ cd LedFx

**2.** Enable development mode to prevent having to reinstall and instead just load from the git repository:

.. code:: bash

    $ python setup.py develop

**3.** This will let you run LedFx directly from your Git repository via:

.. code:: bash

    $ ledfx --open-ui

macOS
-------

**1.** Clone the dev branch from the LedFx Github repository:

.. code:: bash

    $ git clone https://github.com/ahodges9/LedFx.git -b dev
    $ cd ./ledfx

**2.** Create a conda environment for LedFx with Python 3.7 and install dependencies:

.. code:: bash

    $ conda create -n ledfx python=3.7
    $ conda activate ledfx
    $ conda config --add channels conda-forge
    $ conda install aubio portaudio

**3.** Install LedFx and its requirements using pip:

.. code:: bash

    $ pip install -r requirements.txt
    $ pip install -e .
    $ ledfx --open-ui

------------------------------

--------------------------
   Frontend Development
--------------------------

Linux
-------

Building the LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus uses NPM as the core package management. To get started, first install npm and all the requirements:

**1.** Start in the LedFx repo directory:

.. code:: bash

    $ pip install yarn
    $ yarn install

The easiest way to test and validate your changes is to run a watcher that will automatically rebuild as you save and then just leave LedFx running in a separate command window. (Note: LedFx will need to be running in development mode for everything to work).

**2.** Start LedFx in development mode and start the watcher:

.. code:: bash

    $ ledfx
    $ yarn start

At that point any change you make to the frontend will be recompiled and after a browser refresh LedFx will pick up the new files. After development and testing you will need to run a full build to generate the appropriate distribution files prior to submitting any changes.

**3.** Build the frontend:

.. code:: bash

    $ yarn build

macOS
-------

**1.** Install nodejs and NPM requirements using homebrew:

.. code:: bash

    $ brew install nodejs
    $ brew install yarn
    $ cd ~/frontend
    $ yarn install

**2.** Start LedFx in developer mode and start the NPM watcher. (Open the config.yaml file in the .ledfx folder and set ``dev_mode: true``):

.. code:: bash

    $ ledfx
    $ yarn start

**3.** Build the frontend:

.. code:: bash

    $ yarn build

------------------------------

.. include:: README.rst