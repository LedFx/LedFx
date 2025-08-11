# Soap

## Overview

Soap is a **matrix noise effect** using the vnoise lib to generate and then smear 2d noise through time.

It is inspired strongly by the original WLED Soap effect in [WLED github](https://github.com/wled/WLED/blob/3f90366aa86151e73424dd7c756f95ecbfaf143d/wled00/FX.cpp#L7563)

Which itself drew on inspiration from this [Soap Bubble Youtube](https://www.youtube.com/watch?v=DiHBgITrZck&ab_channel=StefanPetrick) by video by Stefan Petrick

In this example, three devices with 1,024, 4,096, and 16,384 pixels
(32×32, 64×64, and 128×128 matrices) are in the default configuration except that the frequency range on each is set to mid.

<video width="700" height="390" controls loop>
   <source src="../../_static/effects/matrix/soap/soap3.mp4" type="video/mp4">
   Your browser does not support the video tag.
</video>
<br><br>

```{note}
The code has been thouroughly rewritten to be numpy and vnoise based to attempt to keep performance in the python runtime. None the less, it is a very expensive effect.
If performance is a concern, monitor frame time in **Advanced → Diag switch**.
```

All further examples in this guide use a **64×64** matrix for illustration.

---

## Settings

The Soap effect includes a few unique controls:

![Soap settings](/_static/effects/matrix/soap/soap_settings.png)

- **DENSITY** — Controls density and size of the applied smear, below are examples using density of 0, 0.5 and 1

```{image} /_static/effects/matrix/soap/density_0.png
:width: 200px
```
```{image} /_static/effects/matrix/soap/density_05.png
:width: 200px
```
```{image} /_static/effects/matrix/soap/density_1.png
:width: 200px
```

- **SPEED** — Controls how fast the smear is applied through time. Increasing this value makes the smear more energetic.
- **INTENSITY** — Is used as a multiplier on the audio input. Larger values will make the audio impulse more dynamic. Setting this value to 0 will allow the effect to free run irrespective of the audio source.
- **FREQUENCY RANGE** — Controls the frequency of the band pass filter used to generate the audio impulse.

