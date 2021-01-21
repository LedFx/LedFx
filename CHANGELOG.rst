=========
Changelog
=========

Version 0.9.2
=============

- **This is an interim release** while we prepare to release v1.0, which is currently in active `beta <https://github.com/LedFx/LedFx/tree/dev>`_.

- **High Priority Bugfix.**

- **Automatic crash reporting with Sentry:** If something breaks, we'll know about it! Any errors will be automatically transmitted to the developers
  so we can fix them - in the unlikely event any sensitive personal data is transmitted with a crash report the developers will remove it as soon as possible.
  The crash reporter we use is Sentry - you can see their `privacy policy <https://sentry.io/privacy/>`_ that developers are held to. The LedFx privacy policy
  is pretty simple - we will use the logs to fix LedFx. We don't use any user analytics, user tracking or any of that.

Version 0.9.1
=============
- **Bugfixes.**

Version 0.9.0
=============

- **Sliders.** Effect configuration needs sliders, not numbers! What year is it?
- **Polish.** Smooth transitions between effects.
- **Automatic Updates.** Installable EXE will automatically update itself at launch if there's a new version available

Version 0.8.0
=============

- **New Effects**
    - *BPM Based Effects:* Bar, MultiBar, Strobe
    - *EQ-Like Effects:* Blocks, Equalizer
    - *Other Effects:* Power, Magnitude
- **Scenes & Presets**
    - *Scenes:* Save current effects of all devices as a *scene*, and reactivate any saved scene from the dashboard.
    - *Presets:* Effects have presets, with different settings to demo how the effect can be configured. You can save your own effect configurations as a *custom preset*.
- **Facelift.**
    - More polished interface.
    - New colour scheme.
    - More icons.
- **Device Auto Discovery.** WLED devices on the network are automatically found at launch if no devices are present. Scan for WLED devices in Device Management.
- **Improved Documentation.** better guides for installation across Win, Mac, and Linux

Version 0.7.0
=============

- Updating React and front end dependencies
- separated JS code from PY code moved front end to top level folder
- Removed webpack in favor of CRA for less complexity and faster dev work

Version 0.2.0
=============

- More effects and support for UDP devices
- Frontend converted to react and more features added

Version 0.1.0
=============

- **Initial release with basic feature set!**
    - Added a framework for highly customizable effects and outputs
    - Added support for E1.31 devices
    - Added some basic effects and audio reaction ones