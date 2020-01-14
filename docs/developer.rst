================================
Development Setup
================================

The development workflow is still being worked on, but this covers the current state of the world.


Backend Development
================================

To start running the development brach you need to first clone the repository:

.. code:: bash

    git clone https://github.com/LedFx/LedFx.git
    cd LedFx
    git checkout origin dev

Then enabled development mode to prevent having to reinstall and instead just load from the git repository:

.. code:: bash

    python setup.py develop

This will let you run LedFx directly from your Git repository via:

.. code:: bash

    ledfx --open-ui

Frontend Development
================================

Building LedFx frontend is different from how the core backend is built. The frontend is based on React.js and thus uses NPM as the core package management. To get started, first install npm and all the requirements:

.. code:: bash

    pip install npm
    npm install

The easiest way to test and validate your changes is to run a watcher that will automatically rebuild as you save and then just leave LedFx running in a separate command window. (Note: LedFx will need to be running in development mode for everything to work). To start the watcher run:

.. code:: bash

    npm run watch

At that point any change you make to the frontend will be recompiled and after a browser refresh LedFx will pick up the new files. After development and testing you will need to run a full build to generate the appropriate distrobution files prior to submitting any changes:

.. code:: bash

    npm run build

Document Development
================================

To build the LedFx documentation simply enter the "docs" folder and run the following:

.. code:: bash

    make html