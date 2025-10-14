# Common Settings

Settings that appear in all effects unless specifically disabled and hidden where not applicable

## All

Settings in both 1d Strip and 2d Matrix effects.

### Brightness

A 0 to 1 range slider to apply as a multiplier against the final rendered effect

### Background Color

A simple color picker for use in background render operations

### Background Brightness

A brightness slider modifier applied to background color

## 1d Strip Only

Common settings specific to 1d strip effects.

### Blur

Amount to blur the effect, range 0 to 10

### Flip

Will swap the left to right order of the effect render

### Mirror

Mirrors the effect render about the center point

## 2d Matrix Only

Common settings specific to 2d Matrix effects.

### Flip Horizontal

Will flip the 2d matrix in the horizontal plane. Reverse the left to rigth rendering

### Flip Vertical

Will flip the 2d matrix in the vertical plane. Reverse the top to bottom rendering

### Rotate

90 degree rotation of the rendered matrix effect. 0 = Normal, 1 = 90 Degrees, 2 = 180 Degrees, 3 = 270 Degrees.

## Advanced

Settings under the advanced switch are hidden unless enabled

### Diag

Enables diagnostic dialog and adds extra performance logging for the effect rendering.

See the [LedFx Effect and Device Performance Stats](/troubleshoot/network.md#ledfx-effect-and-device-performance-stats) for more details.

### Background Mode

Currently only implemented for 2d matrix effects. Some effects where background mode is not practical or applicable have all background controls default and hidden.

The `background_mode` setting controls how an effect composes a configured background color with the effect's generated pixels.

Choices
- `additive` (default) — the background color is added to the effect pixels. This brightens pixels by component-wise addition and is useful for tinting or subtly brightening the effect.
- `overwrite` — the background color is filled into the render space at the beginning of each frame and the effect overwritten on top. There is no alpha blending.
