# Number

## Overview

The **Number** effect is a diagnostic matrix effect that displays a numeric value or time at the maximum possible text size on a matrix. It inherits from the Texter2d effect and is designed for real-time monitoring, debugging, and displaying time on LED matrices.

## Features

- **Maximum Text Size**: Automatically displays numbers or time at the largest size that fits on the matrix
- **Real-time Updates**: Updates the displayed value every render frame (time modes update regardless of audio input)
- **Stable Display**: Configurable digit width ensures the text size remains stable regardless of the actual value
- **Time Display**: Can display current time in HH:MM or HH:MM:SS format
- **Easy Integration**: Simple interface for setting diagnostic values from anywhere in the codebase
- **Audio Integration**: By default displays audio metrics (BPM, BPM Confidence), but also supports time display

## Configuration

**number** exposes the following configuration options. Settings are grouped as follows:

- **Normal Settings**: Commonly used options for typical use.
- **Advanced Settings**: Options for fine-tuning appearance or behavior.

### Normal Settings

| Key              | Type   | Default        | Description |
|------------------|--------|----------------|-------------|
| `value_source`   | string | BPM            | Source of the value to display (BPM, BPM Confidence, Time (HH:MM), Time (HH:MM:SS)). |
| `whole_digits`   | int    | 3              | Number of digits to reserve before decimal point (for stable text size, numeric modes only). |
| `decimal_digits` | int    | 2              | Number of digits to display after decimal point (for stable text size, numeric modes only). |
| `negative`       | bool   | false          | Support negative values (include negative sign in sizing, numeric modes only). |

### Advanced Settings

| Key                      | Type   | Default   | Description |
|--------------------------|--------|-----------|-------------|
| `text_color`             | color  | #ffffff   | Text color. |
| `font`                   | string | Press Start 2 P | Font name or path. |
| `resize_method`          | string | LANCZOS   | Image resize method for text rendering. |
| `background_brightness`  | float  | 1.0       | Background brightness level. |
| `background_mode`        | string | additive | Background display mode. |
| `background_color`       | color  | #000000   | Background color. |

**Notes:**
- `whole_digits` and `decimal_digits` control the template used for sizing in numeric modes, so the text size remains stable as the value changes. These settings do not apply to time display modes.
- If `negative` is enabled, space is reserved for a minus sign in the template sizing, and negative values will display with a '-' prefix. This only applies to numeric modes.
- Time modes (HH:MM and HH:MM:SS) update every frame regardless of audio input, ensuring the clock is always accurate.
- The effect is automatically centered (enforced internally).
- `display_value` is an instance attribute that can be set programmatically but is not a config option.
