=======================
   Development Setup
=======================

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

.. --------------------------
..    Frontend Development
.. --------------------------

.. Building the LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus
.. uses NPM as the core package management.

.. .. note:: LedFx will need to be running in development mode for everything to work. To enable development mode,
..           open the ``config.json`` file in the ``.ledfx`` folder and set ``dev_mode: true``)

.. .. _linux-frontend:

.. Linux
.. -------

.. .. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <linux-dev>`

.. To get started, first install npm and all the requirements:

.. **1.** Start in the LedFx repo directory:

.. .. code:: console

..     $ pip install yarn
..     $ cd frontend
..     $ yarn

.. The easiest way to test and validate your changes is to run a watcher that will automatically rebuild as you save and then
.. just leave LedFx running in a separate command window.

.. **2.** Start LedFx in development mode and start the watcher:

.. .. code:: console

..     $ python3 ledfx
..     $ yarn start

.. At that point any change you make to the frontend will be recompiled and after a browser refresh LedFx will pick up the
.. new files. After development and testing you will need to run a full build to generate the appropriate distribution files
.. prior to submitting any changes.

.. **3.** When you are finished with your changes, build the frontend:

.. .. code:: console

..     $ yarn build

.. .. _macos-frontend:

.. macOS
.. -------

.. .. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <macos-dev>`

.. **1.** Install nodejs and NPM requirements using `homebrew`_:

.. .. code:: console

..     $ brew install nodejs
..     $ brew install yarn
..     $ cd ~/frontend
..     $ yarn

.. **2.** Start LedFx in developer mode and start the NPM watcher:

.. .. code:: console

..     $ python3 ledfx
..     $ yarn start

.. **3.** When you are finished with your changes, build the frontend:

.. .. code:: console

..     $ yarn build

.. ------------------------------

.. include:: README.rst

.. Links Down Here

.. _`pip documentation`: https://pip.pypa.io/en/latest/reference/pip_install/#editable-installs
.. _`homebrew`: https://docs.brew.sh/Installation