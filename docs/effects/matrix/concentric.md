# Concentric

## Overview

Concentric is a **matrix effect** that creates expanding and contracting rings from the center of the matrix.

It is **audio reactive**, using a selectable audio band-pass filter to control the speed of the rings' motion.

Here's an example with a 64x64 matrix & an 256x256 matrix:

<video width="700" height="435" controls loop>
   <source src="../../_static/effects/matrix/concentric/example.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Presets

- **RESET** — Rainbow gradient; rings expand at a moderate speed.
- **OCEAN IMPLOSION** — Blue-green gradient; rings contract.
- **FIRE EXPLOSION** — Red-orange gradient; rings expand rapidly.
- **RAINBOW EXPLOSION** — Fast rainbow gradient; rings expand rapidly.

## Settings

The Concentric effect includes a few controls:

![Concentric settings](/_static/effects/matrix/concentric/settings.png)

- **Rotate** — Rotates the effect by 90° for every unit.
- **Brightness** — Self-explanatory.

Concentric effect specific settings:

- **Gradient** — Gradient used for rings.
- **Frequency Range** — Selects which audio band-pass filter controls the speed of the rings' motion.
- **Invert** — If enabled, makes rings contract instead of expand.
- **Speed Multiplier** — Factor by which the power of the frequency band is multiplied. (Higher = faster.)
- **Gradient Scale** — Scales the gradient across the matrix. (Higher, less repetitions.)
- **Stretch Height** — Stretches the rings vertically. Useful for non-square matrices or not circular renders. (Can also be width with a rotation.)
- **Center Smoothing** — Blurs the center of the rings to reduce harsh color changes. (Higher = blurrier.)
- **Idle speed** — Minimum speed at any time. Useful to have a not-static effect during music changes or when no movement occurs in the specified frequency range. (Higher = faster.)
