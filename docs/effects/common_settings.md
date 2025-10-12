# Common Settings

WIP: This is not an exhaustive list and will be updated over time

## Advanced

Settings under the advanced switch are hidden unless enabled

### Background Mode

Currently only implemented for 2d matrix effects. Some effects where background mode is not practical or applicable have all background controls default and hidden.

The `background_mode` setting controls how an effect composes a configured background color with the effect's generated pixels.

Choices
- `additive` (default) — the background color is added to the effect pixels. This brightens	pixels by component-wise addition and is useful for tinting or subtly brightening the effect.
- `overwrite` — the background color is filled into the render space at the beginning of each frame and the effect overwritten on top. There is no alpha blending.

### Background Color

A simple color picker for use in background render operations

### Background Brightness

A brightness slider modifyier applied to background color

