# Concentric

## Overview

Concentric is a **matrix effect** that creates expanding and contracting rings from the center of the matrix.

It is **audio reactive**, using a selectable audio band-pass filter to control the speed of the rings' motion.

Here's an example with a 64x64 matrix & an 256x256 matrix:

<video width="853" height="530" controls loop>
   <source src="../../_static/effects/matrix/concentric/example.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

## Presets

**RESET** — Rings expand at a moderate speed. Rainbow gradient.
**OCEAN IMPLOSION** — Blue-green gradient, rings contracts.
**FIRE EXPLOSION** — Red-orange gradient, rings expand rapidly.
**RAINBOW EXPLOSION** — Fast rainbow gradient, rings expand rapidly.

## Settings

The Concentric effect includes a few controls:

![Concentric settings](/_static/effects/matrix/concentric/settings.png)

- **Gradient** — Gradient used for rings.
- **Frequency Range** — Selects which audio band-pass filter controls the speed of the rings' motion.
- **Rotate** — Rotates the gradient.
- **Invert** — If on, makes rings contract instead of expand.
- **Brightness** — Self-explanatory.
- **Speed Multiplier** — Factor by which the power of the frequency band is multiplied. (Higher, faster.)
- **Gradient Scale** — Scales the gradient across the matrix. (Higher, less repetitions.)
- **Stretch Height** — Stretches the rings vertically. Useful for non-square matrices or not circular renders. (Can also be width with a rotation.)
- **Center Smoothing** — Blures the center of the rings to reduce harsh color change. (Higher, blurrier.)
- **Idle speed** — Minimum speed at any time. Useful to have a not-static effect during music change or no movement in the specified frequency range. (Higher, faster.)
