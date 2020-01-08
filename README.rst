LedFx
================================================================================= 
|License| |Discord|

LedFx is a network based LED effect controller with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266 nodes allowing for cost effectvice syncronized effects across your entire house!

.. image:: https://raw.githubusercontent.com/ahodges9/LedFx/master/demos/ledfx_demo.gif

.. |Build Status| image:: https://travis-ci.org/ahodges9/LedFx.svg?branch=master
   :target: https://travis-ci.org/ahodges9/LedFx
.. |License| image:: https://img.shields.io/badge/license-MIT-blue.svg
.. |Discord| image:: https://img.shields.io/badge/chat-on%20discord-7289da.svg
   :target: https://discord.gg/wJ755dY

Build Instructions
------------------
For Mattallmighty/LedFx on Windows OS:

Programs to download and install:

- https://www.anaconda.com/distribution/#download-section - Python 3.7 version

- https://git-scm.com/downloads

- Optional, but good to have: https://www.npmjs.com/get-npm - There will be an option through the install to install recommended programs through Chocolatey (Tick that box)

Once installed, search for the program anaconda navigator.

Left side panel you will see 'Environments', followed at the bottom of your screen 'Create'

- Name: LedFx-Mattallmighty

- Python: 3.6

click create.

Once created, click on the icon that looks like a play button, and select 'Open Terminal'.

You should see something like: ``(LedFx-Mattallmighty) C:\Users\Your User>`` This is where we are going to install LedFx on your PC. 

Copy the below:

``git clone https://github.com/Mattallmighty/LedFx.git``

Copy the below, but change 'Your User' to what is displayed in the command prompt. 

``cd C:\Users\Your User\LedFx``
    
For example I used: ``cd C:\Users\mattremote\LedFx``

Then copy and paste the below commands::

    pip install -r requirements.txt
    conda config --add channels conda-forge
    conda install aubio portaudio pywin32
    y
    pip install -r requirements.txt
    pip install .

Open directory ``C:\Users\mattremote\Documents\GitHub\LedFx\ledfx\devices``

Delete the file: ``fadecandy.py``

Back to command prompt enter: ``ledfx --open``

Done! Any issues, message the Discord LedFx community for help.
