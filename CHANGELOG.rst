=========
Changelog
=========

Version 0.
===========

- Updating React and front end dependencies
- separated JS code from PY code moved front end to top level folder
- Removed webpack in favor of CRA for less complexity and faster dev work

Version 0.2
===========

- More effects and support for UDP devices
- Frontend converted to react and more features added

Version 0.1
===========

- **Initial release with basic feature set!**
    - Added a framework for highly customizable effects and outputs
    - Added support for E1.31 devices
    - Added some basic effects and audio reaction ones

Version 0.8
===========

- **New Effects**
    - _BPM Based Effects:_ Bar, MultiBar, Strobe
    - _EQ-Like Effects:_ Blocks, Equalizer
    - _Other Effects:_ Power, Magnitude
- **Scenes & Presets**
    - _Scenes:_ Save current effects of all devices as a _scene_, and reactivate any saved scene from the dashboard.
    - _Presets:_ Effects have presets, with different settings to demo how the effect can be configured. You can save your own effect configurations as a _custom preset_.
- **Facelift.** 
    - More polished interface.
    - New colour scheme.
    - More icons.
- **Device Auto Discovery.** WLED devices on the network are automatically found at launch if no devices are present. Scan for WLED devices in Device Management.
- **Improved Documentation.** better guides for installation across Win, Mac, and Linux

Version 0.9
===========

- **Sliders.** Effect configuration needs sliders, not numbers! What year is it?
- **Polish.** Smooth transitions between effects.
- **Automatic Updates.** Installable EXE will automatically update itself at launch if there's a new version available