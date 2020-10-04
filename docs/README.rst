--------------------------
   Document Development
--------------------------

The documentation is written in reStructuredText. Once you are finished
making changes, you must build the documentation. To build the LedFx
documentation follow the steps outlined below:

Linux
-----

.. code:: bash

    $ cd ~/ledfx/docs
    $ pip install -r requirements_docs.txt
    $ make html

macOS
-----

.. code:: bash

    $ conda activate ledfx
    $ cd ~/ledfx/docs
    $ pip install -r requirements_docs.txt
    $ make html