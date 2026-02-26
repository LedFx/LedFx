# Smoke

## Overview

Smoke is a **matrix gradient effect** using the FastNoiseLite library to generate smooth, flowing noise patterns that resemble wisps of smoke flowing through space.

<video width="420" height="420" controls loop>
   <source src="../../_static/effects/matrix/smoke/smoke.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

It is **audio reactive**, using low-frequency audio to dynamically adjust the zoom level, creating a breathing or pulsing effect where the pattern expands and contracts with the bass.

The effect uses **FBm (Fractional Brownian Motion)** noise generation with optimized fractal parameters to create natural-looking, organic patterns that continuously evolve through three-dimensional noise space.

<br>

```{note}
This effect leverages the high-performance FastNoiseLite library with vectorized NumPy operations for efficient rendering.
```

---

## Settings

The Smoke effect includes a few unique controls:

**SPEED** Controls how quickly the smoke pattern moves through noise space.<br>
**STRETCH**  Controls the contrast of the noise pattern before it's mapped to your gradient.<br>
**ZOOM** Controls the density and scale of the smoke detail.<br>
**IMPULSE DECAY** Controls the decay filter applied to the audio impulse signal.<br>
**MULTIPLIER** Controls how strongly audio affects the effect (audio injection multiplier).<br>