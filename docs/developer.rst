=======================
   Development Setup
=======================

The development workflow is still being worked on, but this page covers the current state of the world.

You will see ``pip install -e .`` frequently in the documentation. Please see the `pip documentation`_ for an explanation on what this does.

.. note:: All current development versions of LedFx now require Python >=3.8

------------------------------

-------------------------
   Backend Development
-------------------------

.. _win-dev:

Windows
-------

*  Install Python 3.8 or above.
*  Install Git.
*  Using "Build Tools for Visual Studio 2019" installer:

   *  https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2019
   *  You require the mandatory selected build tools, and the following optional tools;

      *  Windows 10 SDK (or your equivalent Windows Version)
      *  C++ CMAKE tools for Windows
      *  MSVC v142 (or above) - VS 2019 C++ x64/x86 build tools

    *  Default install options are appropriate.

*  Reboot

.. code:: console

    $ python -m venv C:\ledfx
    $ cd C:\ledfx
    $ .\Scripts\activate.bat
    $ pip install pipwin
    $ pip install wheel
    $ pipwin refresh
    $ pipwin install pyaudio
    $ pip install pywin32
    $ python .\Scripts\pywin32_postinstall.py -install
    $ git clone -b frontend_beta https://github.com/LedFx/LedFx .\ledfx-git
    $ cd .\ledfx-git
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

**1.** Clone the dev branch from the LedFx Github repository:

.. code:: console

    $ git clone https://github.com/LedFx/LedFx.git -b frontend_beta
    $ cd LedFx

**2.** Install system dependencies via ``apt install``:

.. code:: console

    $ sudo apt install python-dev \
        libatlas3-base \
        libavformat58 \
        portaudio19-dev \
        pulseaudio

**3.** Install LedFx in development mode:

.. code:: console

    $ python setup.py develop

**4.** This will let you run LedFx directly from your Git repository via:

.. code:: console

    $ ledfx --open-ui

.. _macos-dev:

macOS
-------

**1.** Clone the dev branch from the LedFx Github repository:

.. code:: console

    $ git clone https://github.com/LedFx/LedFx.git -b frontend_beta
    $ cd ./LedFx

**2.** Create a python venv for LedFx with python>=3.9 and install dependencies:

.. code:: console

    $ python3 -m venv ~/ledfx-venv
    $ source ~/ledfx-venv/bin/activate
    $ brew install portaudio pulseaudio

**3.** Install LedFx and its requirements using pip:

.. code:: console

    $ python setup.py develop

**4.** This will let you run LedFx directly from your Git repository via:

.. code:: console

    $ ledfx --open-ui

------------------------------

--------------------------
   Frontend Development
--------------------------

Building the LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus
uses yarn as the core package management.

.. note:: LedFx will need to be running in development mode for everything to work. To enable development mode,
          open the ``config.yaml`` file in the ``.ledfx`` folder and set ``dev_mode: true``)

.. _windows-frontend:

Windows
--------
.. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <win-dev>`

To get started, first install yarn and all the requirements:

**1.** Install yarn & LedFx requirements:

.. code:: console

    $ pip install yarn
    $ cd LedFx/frontend
    $ yarn install

**2.** Start in the LedFx repo directory:

.. code:: console

    $ cd LedFx
    $ ledfx

**3.**  While Ledfx is running in the background (Step 2), open a new command prompt and run the following:

.. code:: console

    $ cd LedFx/frontend
    $ yarn start

This will allow you to validate/test your changes by automatically rebuilding as you save .js and .jsx files.

.. _linux-frontend:

Linux
-------

.. note:: The following instructions assume you have already followed the steps above to :ref:`install the LedFx dev environment <linux-dev>`

To get started, first install yarn and all the requirements:

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

**1.** Install nodejs and yarn requirements using `homebrew`_:

.. code:: console

    $ brew install nodejs
    $ brew install yarn
    $ cd ~/frontend
    $ yarn

**2.** Start LedFx in developer mode and start the yarn watcher:

.. code:: console

    $ python3 ledfx
    $ yarn start

**3.** When you are finished with your changes, build the frontend:

.. code:: console

    $ yarn build

.. _LedFxReact:

Working with LedFx and React
-----------------------------------

This project was bootstrapped with Create React App.

Available Frontend Scripts
----------------------------

In the project directory, you can run:
``yarn start``
Runs the app in the development mode.
Open http://localhost:3000 to view it in the browser.
The page will reload if you make edits.
You will also see any lint errors in the console.

``yarn test``
Launches the test runner in the interactive watch mode.
See the section about running tests for more information.

``yarn build``
Builds the app for production to the build folder.
It correctly bundles React in production mode and optimizes the build for the best performance.
The build is minified and the filenames include the hashes.
Your app is ready to be deployed!
See the section about deployment for more information.

**Learn More**

You can learn more in the Create React App documentation: https://create-react-app.dev/docs/getting-started/
To learn React, check out the React documentation: https://reactjs.org/

**Code Splitting**
This section has moved here: https://facebook.github.io/create-react-app/docs/code-splitting

**Analyzing the Bundle Size**
This section has moved here: https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size

**Making a Progressive Web App**
This section has moved here: https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app

**Advanced Configuration**
This section has moved here: https://facebook.github.io/create-react-app/docs/advanced-configuration

**Deployment**
This section has moved here: https://facebook.github.io/create-react-app/docs/deployment

**yarn build fails to minify**
This section has moved here: https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify

------------------------------

.. include:: README.rst

.. Links Down Here

.. _`pip documentation`: https://pip.pypa.io/en/latest/reference/pip_install/#editable-installs
.. _`homebrew`: https://docs.brew.sh/Installation