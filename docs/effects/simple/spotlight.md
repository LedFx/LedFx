# Spotlight

## Overview

Spotlight is an audio-reactive 1D effect that spawns short, fading light cones at random positions on a strip.

It is designed for perimeter strips (for example, around a room ceiling) where multiple independent light bursts should appear and decay naturally with the music.

The effect combines:

- adaptive activity tracking with internal tuning defaults
- adaptive burst detection from onset and volume-beat events
- multiple simultaneous spotlights with smooth fade-out
- optional gradient-based color selection with animated color progression

I had the idea to this effect when I was watching a concert on my television with Hyperion/Ambilight enabled and wanted to recreate the effect of the spotlights on the stage spreading outside of my television. And then I had more and more ideas :joy:

The general idea is to have a base spawn rate of spots, even when no music is playing, and, based on activity of the music, increase the spawn rate of new spots. But each spot decays over time.

## Settings

### Spot Width

Relative spotlight width in percent of strip length.

- lower values create narrow, punchy highlights
![Narrow width](/_static/effects/simple/spotlight/narrow_width.png)
- higher values create wider wash-like beams
![Higher value for width](/_static/effects/simple/spotlight/wider_width.png)

### Fade Time

How long each spotlight remains visible before fading out completely. It is measured in seconds. If you set it to higher values, it will take longer for the spots to fade and therefor fill the maximum amount of active spots (Advanced Settings > Max active Spots).


## Presets

The effect ships with three built-in presets:

| Preset                  | Spot Width | Fade Time | Max Active Spots | Use Gradient | Gradient Speed | Spot Color Span |
|-------------------------|------------|-----------|------------------|--------------|----------------|-----------------|
| Reset / Standard Values | 8%         | 0.8s      | 28               | Yes          | 0.12           | 0.08            |
| Club Smooth             | 8%         | 0.45s     | 34               | Yes          | 0.18           | 0.1             |
| Club Drop Max           | 4%         | 0.2s      | 96               | Yes          | 0.35           | 0.18            |
| Small Spotlights        | 2%         | 0.15s     | 128              | Yes          | 0.12           | 0.08            |

These are available through the normal LedFx preset system.

## Advanced Controls

### Max Active Spots

This number controls how many spots you can have at the same time. It is limited to 128, which is already a lot and might be to much on low end devices. Here is an example for max 4 active spots
![Low amount of spots](/_static/effects/simple/spotlight/less_active_spots.png)
and here for max 128 active spots (it is hard to make a screenshot at the right moment in time, so trust me, 128 can be a lot :joy:)
![High amount of spots](/_static/effects/simple/spotlight/more_active_spots.png)
For both screenshots I had to set the spot width to 2% to make it more visible.

### Use Gradient

When enabled, spotlight colors are sampled from the selected gradient. I highly suggest this option. It can be further controlled with the Options Gradient Speed and Spot Color Span. For this screenshot I set the Gradient Speed to a higher value to see the different colors in the screenshot.
![Use Gradient True](/_static/effects/simple/spotlight/use_gradient_true.png)

When disabled, the effect falls back to selectable center/edge colors. This might be useful if you have a corporate event and want to only have the brand colors. This option is hard to show in a screenshot, I had to increase the Spot Width and select a bright yellow as edge color with white as center color to make it visible on the screenshot. Less bright colors look good in reality, but not on the screenshot.
![Use Gradient False](/_static/effects/simple/spotlight/use_gradient_false.png)

### Gradient Speed

Speed of color progression through the gradient over time. High values will make the spotlights change colors much faster and you will get the effect that during the same time spots on your LED strip have different colors (the next spawned spots will have a different colort while other spots are fading out). You can see it pretty good on the screenshot for the Use Gradient option. 

The Graident Speed is the amount the hue value changes during spawn cycles.

This option only makes sense if you enable Use Gradient.

### Spot Color Span

Offset in gradient space between center and edge colors for each spotlight. When a new spot is spawned, the center color is choosen based on the Gradient and the Gradient Speed. After that the edge color is just an offset from the center color. I prefer smaller values for this option, otherwise you get quite odd looking color gradients for each spot. But maybe you like it :smiley:
![High Spot Color Span](/_static/effects/simple/spotlight/high_spot_color_span.png)

This option only makes sense if you enable Use Gradient.
