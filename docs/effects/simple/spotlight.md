# Spotlight

## Overview

Spotlight is an audio-reactive 1D effect that spawns short, fading light cones at random positions on a strip.

It is designed for perimeter strips (for example, around a room ceiling) where multiple independent light bursts should appear and decay naturally with the music.

The effect combines:

- adaptive activity tracking with internal tuning defaults
- optional beat/onset burst triggers
- multiple simultaneous spotlights with smooth fade-out
- optional gradient-based color selection with animated color progression

## Settings

### Spot Width

Relative spotlight width in percent of strip length.

- lower values create narrow, punchy highlights
- higher values create wider wash-like beams

### Fade Time

How long each spotlight remains visible before fading out completely.

### Use Gradient

When enabled, spotlight colors are sampled from the selected gradient.

When disabled, the effect falls back to built-in center/edge colors.

### Gradient Speed

Speed of color progression through the gradient over time.

### Spot Color Span

Offset in gradient space between center and edge colors for each spotlight.

## Presets

The effect ships with three built-in presets:

- Club Smooth
- Club Drop Max
- Small Spotlights

These are available through the normal LedFx preset system.

## Advanced Controls

The following controls are advanced:

- Beat Trigger
- Max Active Spots
- Use Gradient
- Gradient Speed
- Spot Color Span
- Center Color
- Edge Color

Other spawn and weighting internals are intentionally fixed to keep the effect simple and predictable.

The edge softness and fade curve are currently fixed internally.

For most users, adjusting only these gives good results:

- Spot Width
- Edge Softness
- Fade Time
- Fade Curve
- Use Gradient
- Gradient Speed
