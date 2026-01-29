=====================================================
   Welcome to LedFx ✨ *Making music come alive!*
=====================================================
|Build Status| |License| |Build Status Docs| |Discord|
|Contributor Covenant|

.. image:: https://raw.githubusercontent.com/LedFx/LedFx/main/ledfx_assets/banner.png

What is LedFx?
----------------
LedFx makes your LEDs dance to audio!
What LedFx offers is the ability to take audio input, and instantaneously processes the audio into realtime light show to multiple LED strips/matrix.
No need to spend hours on end to program one song to program your LEDs, as LedFx will do this all for you!

LedFx real-time LED strip music visualization effect controller using is a network based devices (ESP8266/ESP32/Raspberry Pi 4) with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266/ESP32 nodes allowing for cost effective synchronized effects across your entire house!

Ledfx comes with a browser based front end for configuration, control and live visualisation on port 8888 by default.

| http://localhost:8888
| http://127.0.0.1:8888


Demos
-------

Visit and join our `Discord`_ where community members show off their projects. Check out the #projects or #show-and-tell channels.

📑 Quick start guide and documentation📖
------------------------------------------

Head over to `releases`_ to get the latest releases for Windows and Mac. For linux, use pip.

**Bleeding edge (Experimental)**

If you want the absolute bleeding edge and are not afraid of using the terminal, take a look at the detailed installation instructions here: `Installation documentation`_.

**Documentation**

Documentation for the latest release can be found here: `Stable documentation`_

Documentation built against this repository can be found here: `Latest documentation`_


😍 Show me how to make one!
-----------------------------

The below image describes a basic setup - LedFx running on PC, communicating with a WLED Device controlling an LED strip.

.. image:: https://raw.githubusercontent.com/LedFx/LedFx/main/docs/_static/topology.png

.. list-table::
   :widths: 75 75
   :header-rows: 1

   * - Component
     - Example
   * - Computer running LedFx
     - Windows 10, `LedFx.exe`_
   * - Browser to access the LedFx web interface
     - Chrome/Edge/Firefox/Safari

       http://127.0.0.1:8888
   * - Networked device controlling LED Strip
     - ESP8266 NODEMCU v3 running `WLED`_
   * - Addressable LED strip
     - DC5V WS2812B 5 meters 60LED/m IP67
   * - Power supply for LED Strip and ESP
     - 5V 10 amps LED Power Supply
   * - Something to connect the wires together!
     - Soldering iron/solder

#. **Build your networked LED Strip.**
      - For most, this is the difficult step. Don't worry! There's guides here and online, and plenty of people able to help on WLED and LedFx Discord.
      - Follow the `WLED guide to connect the LED strip and ESP together <https://kno.wled.ge/basics/getting-started/>`_.
      - `Flash WLED to the ESP device <https://kno.wled.ge/basics/install-binary/>`_.
      - Ensure all WLED devices are powered on, and connected to your Wi-Fi.
      - Test you can access the WLED web interface from your PC. If so, then you're good to go!

#. **Install LedFx.**
      - For PC and Mac, see our `releases`_, or see the `installation documentation`_ for more information.
      - For linux, you can use pip to install ledfx - however you may need to install some dependencies first. See the `installation documentation`_ for more information.

#. **Direct computer audio output to LedFx.**
      - By default on Windows LedFx will attempt to listen to your system audio.
      - More information for `Linux and macOS users here <https://ledfx.readthedocs.io/en/latest/directing_audio.html>`_.
      - Play some music in the background.

#. **Start LedFx.**
      - With any desired launch options. See :doc:`Command Line Options </launch>`
      - Use --open-ui to open the web interface automatically in your default browser, or navigate to http://127.0.0.1:8888 directly.
      - Your WLED devices should appear in LedFx, automagically configured and ready to go! 🎆🔥
      - If not, on the bottom click Home,  -> ``Scan for WLED devices`` button, or click on the big plus sign and ``Add Device`` to add them manually.
      - If they're still not showing up, make sure they're powered on and properly connected to your WiFi.

#. **Start using effects!**
      - Click on the device, select an effect eg ``scroll`` under Classic
      - Your lights should now be reacting realtime to your music! Enjoy the show 🌈


🎭 Mood Detection System
------------------------

This fork includes an advanced mood detection system that analyzes your music in real-time and automatically adjusts effects, colors, and scenes based on the detected mood and musical structure.

**What is Mood Detection?**

The mood detection system analyzes audio features to determine:
- **Energy Level**: Low, medium, or high energy
- **Valence**: Emotional tone from sad/dark to happy/bright
- **Musical Structure**: Detects verses, choruses, bridges, and dramatic events (drops, builds, etc.)
- **Tempo & Dynamics**: Beat strength, tempo stability, and dynamic range

**Setup Instructions**

#. **Enable Mood Manager Integration**
      - Open LedFx web interface (usually at ``http://localhost:8888``)
      - Navigate to **Settings** → **Integrations**
      - Find **Mood Manager** and click **Enable**
      - The mood detection system will start analyzing your audio

#. **Optional: Install Advanced Audio Analysis (librosa)**
      - For enhanced mood detection accuracy, install the optional librosa dependency:
      - ``pip install librosa>=0.10.0``
      - If installing LedFx from source, you can use: ``pip install "ledfx[mood_advanced]"``
      - Then enable ``use_librosa`` in the Mood Manager configuration

#. **Configure Mood-to-Scene Mappings (Optional)**
      - If you want scenes to automatically switch based on mood:
      - Enable ``switch_scenes`` in Mood Manager settings
      - Map mood categories (e.g., "energetic", "calm", "intense") to your scene IDs
      - Use the API endpoint ``POST /api/mood/scenes`` or configure via the web interface

**Configuration Options**

The Mood Manager has extensive configuration options accessible via the web interface or API (``PUT /api/mood``):

**Basic Settings:**
- ``enabled`` (default: ``False``): Enable/disable automatic mood-based adjustments
- ``update_interval`` (default: ``0.5`` seconds): How often to check for mood changes (0.1-5.0 seconds)
- ``intensity`` (default: ``0.7``): Overall intensity of mood reactions (0.0-1.0). Higher values = more dramatic changes

**Adjustment Controls:**
- ``adjust_colors`` (default: ``True``): Automatically adjust color palettes based on mood
- ``adjust_effects`` (default: ``True``): Automatically adjust effect parameters (speed, brightness, blur) based on mood
- ``switch_scenes`` (default: ``False``): Automatically switch scenes based on music structure and mood
- ``react_to_events`` (default: ``True``): React to dramatic musical events (drops, builds, transitions)

**Scene Preservation:**
- ``preserve_scene_settings`` (default: ``True``): When switching scenes, preserve the scene's effect settings instead of applying mood adjustments. Set to ``False`` if you want mood adjustments to override scene settings.

**Change Detection:**
- ``change_threshold`` (default: ``0.2``): Minimum mood change (0.05-0.5) required to trigger updates. Lower = more sensitive
- ``min_change_interval`` (default: ``3.0`` seconds): Minimum time between mood-based changes (0.5-30.0 seconds)
- ``use_adaptive_threshold`` (default: ``True``): Automatically adjust sensitivity based on music dynamics
- ``enable_force_updates`` (default: ``False``): Enable periodic updates even without significant mood changes
- ``force_update_interval`` (default: ``60.0`` seconds): How often to force updates if enabled (10-300 seconds)

**Advanced Audio Analysis (librosa):**
- ``use_librosa`` (default: ``False``): Use librosa library for enhanced audio feature extraction
- ``librosa_buffer_duration`` (default: ``3.0`` seconds): Audio buffer size for librosa analysis (1.0-10.0 seconds)
- ``librosa_update_interval`` (default: ``2.0`` seconds): How often librosa features are updated (0.5-10.0 seconds)

**Mood Detector Settings:**
- ``history_length`` (default: ``10`` seconds): Audio history to analyze (2-60 seconds)
- ``update_rate`` (default: ``10`` Hz): Mood analysis frequency (1-30 Hz)
- ``energy_sensitivity`` (default: ``0.5``): Sensitivity to energy changes (0.0-1.0)
- ``mood_smoothing`` (default: ``0.3``): Smoothing factor for mood transitions (0.0-1.0). Higher = smoother transitions

**Targeting:**
- ``target_virtuals`` (default: ``[]``): List of virtual IDs to control. Empty list = control all virtuals

**Mood Categories**

The system detects these mood categories:
- **Calm**: Low energy, positive valence
- **Energetic**: High energy, positive valence
- **Intense**: High energy, negative valence
- **Melancholic**: Low energy, negative valence

**API Endpoints**

- ``GET /api/mood``: Get current mood metrics and structure information
- ``PUT /api/mood``: Configure mood detection settings
- ``GET /api/mood/scenes``: Get mood-to-scene mappings
- ``POST /api/mood/scenes``: Create/update mood-to-scene mapping
- ``DELETE /api/mood/scenes/{mood_category}``: Delete a mood-to-scene mapping

**Example Configuration**

To enable mood detection with automatic color and effect adjustments:

.. code-block:: json

   {
     "enabled": true,
     "adjust_colors": true,
     "adjust_effects": true,
     "switch_scenes": false,
     "intensity": 0.7,
     "preserve_scene_settings": true
   }

**Tips for Best Results**

- Start with default settings and adjust ``intensity`` based on your preference
- Enable ``preserve_scene_settings`` if you want scenes to maintain their specific effect configurations
- Use ``use_librosa`` for more accurate mood detection, especially for complex music
- Adjust ``change_threshold`` and ``min_change_interval`` to control how frequently effects change
- Map your favorite scenes to mood categories for automatic scene switching during different song sections


🧑‍💻 Join the LedFx Community
------------------------------

Join the Discord server to discuss everything about LedFx!  |Discord|

To join, click on the Discord button below:

.. image:: https://discordapp.com/api/guilds/469985374052286474/widget.png?style=banner2
   :width: 30%
   :target: https://discord.com/invite/xyyHEquZKQ

Contributing
--------------
Pull requests are welcome. Once tested, contact LedFx developer community on Discord to discuss the next step.
We expect and require all contributors to read, understand and follow our code of conduct.

Credits: `Contributors-&-About`_

License
---------
`GPL-3`_


.. _`GPL-3`: https://choosealicense.com/licenses/gpl-3.0/
.. _`LedFx.exe`: https://github.com/LedFx/LedFx/releases/latest
.. _`LedFx Guide`: https://ledfx.readthedocs.io/en/latest/index.html
.. _`WLED`: https://kno.wled.ge
.. _`releases`: https://github.com/LedFx/LedFx/releases/latest
.. _`Installation documentation`: https://ledfx.readthedocs.io/en/latest/installing.html
.. _`Stable documentation`: https://ledfx.readthedocs.io/en/stable/
.. _`Latest documentation`: https://ledfx.readthedocs.io/en/latest/
.. _`our website`: https://ledfx.app
.. _`Discord`: https://discord.gg/xyyHEquZKQ
.. _`Contributors-&-About`: https://ledfx.app/about/
.. _`How to: Enable Stereo Mix in Windows 10`: https://thegeekpage.com/stereo-mix/


.. |Build Status| image:: https://github.com/LedFx/LedFx/actions/workflows/ci-build.yml/badge.svg
   :target: https://github.com/LedFx/LedFx/actions/workflows/ci-build.yml
   :alt: Build Status
.. |Build Status Docs| image:: https://readthedocs.org/projects/ledfx/badge/?version=main
   :target: https://ledfx.readthedocs.io/
   :alt: Documentation Status
.. |License| image:: https://img.shields.io/badge/license-GPL3-blue.svg
   :alt: License
.. |Discord| image:: https://img.shields.io/badge/chat-on%20discord-7289da.svg
   :target: https://discord.gg/xyyHEquZKQ
   :alt: Discord
.. |Contributor Covenant| image:: https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg
   :target: CODE_OF_CONDUCT.md
