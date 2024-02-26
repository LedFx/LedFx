=======================
   Development Setup
=======================
.. _backend-dev:

-------------------------
   Backend Development
-------------------------

.. warning::

    Always be aware of piping commands to any shell - this is the recommended method for poetry but there are `other options <https://python-poetry.org/docs/#installation>`_.

Windows
-------
.. note::

    Do not install python from the Windows Store - it will not work with these instructions.

#. Install `python <https://www.python.org/downloads/windows/>`_ version 3.9 or above.
#. Install `git <https://gitforwindows.org/>`_.
#. Install `Build Tools for Visual Studio 2022 <https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022>`_

     - When asked for Workloads, select "Desktop development with C++"
     - Included
         - C++ Build Tools core features
         - C++ 2022 Redistributable Update
         - C++ Core desktop features
     - Optional
         - MSVC v143 - VS 2022 C++ x64/x86 build tools (vXX,XX)
         - Windows SDK
         - C++ CMake tools for Windows
         - Testing tools core features - Build Tools
         - C++ AddressSanitizer
     - The default install options are appropriate.
#. Reboot
#. Install poetry using PowerShell:

   .. code:: console

    $ (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

#. Clone the main branch from the LedFx Github repository:

   .. code:: console

    $ git clone https://github.com/LedFx/LedFx.git


#. Install LedFx and its requirements using poetry:

   .. code:: console

    $ cd LedFx
    $ poetry install

#. This will let you run LedFx directly from the cloned repository via:

   .. code:: console

    $ poetry run ledfx --open-ui

.. _linux-dev:

Linux
-------
.. note::

    This assumes an apt based system such as ubuntu.
    If your system uses another package manager you should be able use it to get the required packages.

#. Install poetry:

   .. code:: console

    $ curl -sSL https://install.python-poetry.org | python3 -

#. Clone the main branch from the LedFx Github repository:

   .. code:: console

    $ git clone https://github.com/LedFx/LedFx.git

#. Install system dependencies via ``apt install``:

   .. code:: console

    $ sudo apt install libatlas3-base \
          libavformat58 \
          portaudio19-dev \
          pulseaudio \
          cmake \

#. Install LedFx and its requirements using poetry:

   .. code:: console

    $ cd LedFx
    $ poetry install

#. This will let you run LedFx directly from your local copy via:

   .. code:: console

    $ poetry run ledfx --open-ui

.. _macos-dev:

macOS
-------
#. Install poetry:

   .. code:: console

    $ curl -sSL https://install.python-poetry.org | python3 -

#. Clone the main branch from the LedFx Github repository:

   .. code:: console

    $ git clone https://github.com/LedFx/LedFx.git

#. Install LedFx and its requirements using poetry:

   .. code:: console

    $ cd LedFx
    $ poetry install

#. This will let you run LedFx directly from your local copy via:

   .. code:: console

    $ poetry run ledfx --open-ui

------------------------------

--------------------------
   Frontend Development
--------------------------

Building the LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus
uses pnpm as the core package management.

.. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <backend-dev>`
          and have the backend running. If you have not done so, please do so before continuing.

.. note:: LedFx will need to be running in development mode for everything to work. To enable development mode,
          open the ``config.json`` file in the ``.ledfx`` folder and set ``dev_mode: true``)
.. _windows-frontend:

Windows
-------


**1.** Install Node.js and pnpm:

First, you need to install Node.js. You can download it from `Node.js official website <https://nodejs.org/en/download/>`_. After installing Node.js, you can install pnpm via npm (which is installed with Node.js).

.. code:: console

    $ npm install -g pnpm

**2.** Navigate to the frontend directory and install the dependencies:

.. code:: console

    $ cd frontend
    $ pnpm install

**3.** Start LedFx in developer mode and start the pnpm watcher:

.. code:: console

    $ poetry shell ledfx
    $ pnpm start

At this point, any changes you make to the frontend will be recompiled, and after a browser refresh, LedFx will pick up the new files. After development and testing, you will need to run a full build to generate the appropriate distribution files prior to submitting any changes.

**4.** When you are finished with your changes, build the frontend:

.. code:: console

    $ pnpm build

.. _linux-frontend:

Linux
-------

**1.** Install Node.js:

Node.js is a prerequisite for pnpm. You can install it using your distribution's package manager. For Ubuntu, you can use the following commands:

.. code:: console

    $ sudo apt-get update
    $ sudo apt-get install nodejs

**2.** Install pnpm:

.. code:: console

    $ curl -fsSL https://get.pnpm.io/install.sh | sh -

**3.** Navigate to the frontend directory and install the dependencies:

.. code:: console

    $ cd frontend
    $ pnpm install

The easiest way to test and validate your changes is to run a watcher that will automatically rebuild as you save and then
just leave LedFx running in a separate command window.

**4.** Start LedFx in development mode and start the watcher:

.. code:: console

    $ poetry shell ledfx
    $ pnpm start

At that point any change you make to the frontend will be recompiled and after a browser refresh LedFx will pick up the
new files. After development and testing you will need to run a full build to generate the appropriate distribution files
prior to submitting any changes.

**5.** When you are finished with your changes, build the frontend:

.. code:: console

    $ pnpm build

.. _macos-frontend:

macOS
-------

**1.** Install nodejs and NPM requirements using `homebrew`_:

.. code:: console

    $ brew install nodejs
    $ brew install pnpm
    $ cd ~/frontend
    $ pnpm install

**2.** Start LedFx in developer mode and start the NPM watcher:

.. code:: console

    $ poetry shell ledfx
    $ pnpm start

**3.** When you are finished with your changes, build the frontend:

.. code:: console

    $ pnpm build

------------------------------

.. include:: README.rst

.. Links Down Here

.. _`pip documentation`: https://pip.pypa.io/en/latest/reference/pip_install/#editable-installs
.. _`homebrew`: https://docs.brew.sh/Installation