=======================
   Development Setup
=======================

The development workflow is still being worked on, but this page covers the current state of the world.

You will see ``pip install -e .`` frequently in the documentation. Please see the `pip documentation`_ for an explanation on what this does.

------------------------------

-------------------------
   Backend Development
-------------------------

.. _win-dev:

Windows
-------

*  Install Python 3.8 or above. https://www.python.org/downloads/windows/
*  Install Git. https://gitforwindows.org/
*  Install Microsoft Visual Studio 2022 Build Tools - or later

   * https://visualstudio.microsoft.com/downloads/
   * Under All Downloads / Tools for visual studio / Build Tools for Visual Studio 2022
   * Download and run the installer - then select

   * Workloads
     * Desktop development with C++
   * This should enable in the installation details
  * Included
     * C++ Build Tools core features
     * C++ 2022 Redistributable Update
     * C++ core desktop features
  * Optional
     * MSVC v143 - VS 2022 C++ x64/x86 build tools (vXX,XX)
     * Windows SDK (10.0.XXXXX.X)
     * C++ CMake tools for Windows
     * Testing tools core features - Build Tools
     * C++ AddressSanitizer

  *  Default install options are appropriate - go get some coffee

*  Reboot

.. code:: console

    $ py -m venv C:\ledfx
    $ cd C:\ledfx
    $ .\Scripts\activate.bat
    $ pip install wheel
    $ pip install pywin32
    $ python .\Scripts\pywin32_postinstall.py -install
    $ git clone https://github.com/LedFx/LedFx.git .\ledfx-git
    $ cd .\ledfx-git

Manual call to requirements.txt is a temporary step as we need to fix up setup.py

We need to install numpy first, or aubio will not be happy

.. code:: console

    $ pip install numpy==1.23.5
    $ pip install -r requirements.txt
    $ python setup.py develop
    $ ledfx --open-ui

**1.** To develop, open up a terminal and activate the ledfx virtual environment

.. code:: console

    $ C:\ledfx\Scripts\activate.bat

**2.** Make changes to LedFx's files in C:/ledfx/ledfx-git. Your changed files will be run when you run LedFx

.. code:: console

    $ ledfx --open-ui

You can keep the ledfx virtual environment open and keep making changes then running ledfx.
No need to reactivate the virtual environment between changes.

.. _linux-dev:

Linux
-------

**1.** Clone the main branch from the LedFx Github repository:

.. code:: console

    $ git clone https://github.com/LedFx/LedFx.git
    $ cd LedFx

**2.** Install system dependencies via ``apt install``:

.. code:: console

    $ sudo apt install libatlas3-base \
          libavformat58 \
          portaudio19-dev \
          pulseaudio

**3.** Install LedFx and its requirements using pip:

.. code:: console

    $ pip install -r requirements-dev.txt
    $ pip install -e .

**4.** This will let you run LedFx directly from your Git repository via:

.. code:: console

    $ ledfx --open-ui

.. _macos-dev:

macOS
-------

**1.** Clone the main branch from the LedFx Github repository:

.. code:: console

    $ git clone https://github.com/LedFx/LedFx.git
    $ cd ./LedFx

**2.** Create a python venv for LedFx with python>=3.7 and install dependencies:

.. code:: console

    $ python3 -m venv ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ brew install portaudio pulseaudio

**3.** Install LedFx and its requirements using pip:

.. code:: console

    $ pip install -r requirements-dev.txt
    $ pip install -e .

**4.** This will let you run LedFx directly from your Git repository via:

.. code:: console

    $ ledfx --open-ui

------------------------------

--------------------------
   Frontend Development
--------------------------

Building the LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus
uses NPM as the core package management.

.. note:: LedFx will need to be running in development mode for everything to work. To enable development mode,
          open the ``config.json`` file in the ``.ledfx`` folder and set ``dev_mode: true``)

.. _linux-frontend:

Linux
-------

.. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <linux-dev>`

To get started, first install npm and all the requirements:

**1.** Start in the LedFx repo directory:

.. code:: console

    $ pip install yarn
    $ cd frontend
    $ yarn

The easiest way to test and validate your changes is to run a watcher that will automatically rebuild as you save and then
just leave LedFx running in a separate command window.

**2.** Start LedFx in development mode and start the watcher:

.. code:: console

    $ python3 ledfx
    $ yarn start

At that point any change you make to the frontend will be recompiled and after a browser refresh LedFx will pick up the
new files. After development and testing you will need to run a full build to generate the appropriate distribution files
prior to submitting any changes.

**3.** When you are finished with your changes, build the frontend:

.. code:: console

    $ yarn build

.. _macos-frontend:

macOS
-------

.. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <macos-dev>`

**1.** Install nodejs and NPM requirements using `homebrew`_:

.. code:: console

    $ brew install nodejs
    $ brew install yarn
    $ cd ~/frontend
    $ yarn

**2.** Start LedFx in developer mode and start the NPM watcher:

.. code:: console

    $ python3 ledfx
    $ yarn start

**3.** When you are finished with your changes, build the frontend:

.. code:: console

    $ yarn build

------------------------------

.. include:: README.rst

.. Links Down Here

.. _`pip documentation`: https://pip.pypa.io/en/latest/reference/pip_install/#editable-installs
.. _`homebrew`: https://docs.brew.sh/Installation