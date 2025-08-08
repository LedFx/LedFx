# Flame

## Overview

Flame is a **matrix particle effect** that simulates fire-like motion.

It is **audio reactive**, using **low**, **mid**, and **high** band-pass audio filters to control three independent particle groups.
Each group ***flares*** and becomes more energetic in response to the instantaneous audio level for its band.

In this example, three devices with 1,024, 4,096, and 16,384 pixels
(32×32, 64×64, and 128×128 matrices) are set to the **FIRE** preset:

<video width="700" height="390" controls loop>
   <source src="../../_static/effects/matrix/flame/flame3.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

```{note}
Particle effects are inherently more CPU-intensive.
If performance is a concern, monitor frame time in **Advanced → Diag switch**.
```

All further examples in this guide use a **64×64** matrix for illustration.

---

## Presets

Base colors are assigned to the low, mid, and high audio bands.

- **RESET** — Similar to **RGB**, but with a slightly higher particle spawn rate. Uses red, green, and blue.
- **FIRE** — Uses red, orange, and yellow for a classic flame look.
- **PLAGUE** — Uses white, bright green, and dark green for a sickly flame.

![Presets Group 1](/_static/effects/matrix/flame/presets1.png)

Some presets disable certain bands entirely by setting their base color to black.
Particles from disabled bands are **not spawned or rendered**.

- **BASE RED** — Only renders red, driven by the low band.
- **MID GREEN** — Only renders green, driven by the mid band.
- **HIGH BLUE** — Only renders blue, driven by the high band.

![Presets Group 2](/_static/effects/matrix/flame/presets2.png)

---

## Settings

The Flame effect includes a few unique controls:

![Flame settings](/_static/effects/matrix/flame/settings.png)

- **LOW BAND** — Base color for particles driven by the low band-pass filter.
- **MID BAND** — Base color for particles driven by the mid band-pass filter.
- **HIGH BAND** — Base color for particles driven by the high band-pass filter.

- **BLUR AMOUNT** — Horizontal blur applied to soften particles.
- **SPAWN RATE** — Controls how many new particles are generated, relative to the matrix width.
- **VELOCITY** — Approximate number of seconds a particle takes to travel from bottom to top. On spawn, this is randomized between 0.5× and 1.2× the set value.
- **INTENSITY** — Scales how strongly audio input affects wobble and lift.
  Setting this to **0** produces a steady, non-audio-reactive flame.

---

Enjoy — and don’t burn yourself! 🔥
