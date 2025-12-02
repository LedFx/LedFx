# Number

## Overview

The **Number** effect is a diagnostic matrix effect that displays a numeric value at the maximum possible text size on a matrix. It inherits from the Texter2d effect and is designed for real-time monitoring and debugging of numeric values on LED matrices.

## Features

- **Maximum Text Size**: Automatically displays numbers at the largest size that fits on the matrix
- **Real-time Updates**: Updates the displayed value every render frame
- **Stable Display**: Configurable digit width ensures the text size remains stable regardless of the actual value
- **Easy Integration**: Simple interface for setting diagnostic values from anywhere in the codebase
- **Audio Integration**: By default displays audio metrics, but easily customizable

## Configuration

**number** exposes the following configuration options. Settings are grouped as follows:

- **Normal Settings**: Commonly used options for typical use.
- **Advanced Settings**: Options for fine-tuning appearance or behavior.

### Normal Settings

| Key              | Type   | Default        | Description |
|------------------|--------|----------------|-------------|
| `value_source`   | string | BPM            | Source of the numeric value to display (BPM, BPM Confidence). |
| `whole_digits`   | int    | 3              | Number of digits to reserve before decimal point (for stable text size). |
| `decimal_digits` | int    | 2              | Number of digits to display after decimal point (for stable text size). |
| `negative`       | bool   | false          | Support negative values (include negative sign in sizing). |

### Advanced Settings

| Key            | Type   | Default   | Description |
|----------------|--------|-----------|-------------|
| `text_color`   | color  | #ffffff   | Text color. |
| `font`         | string | (default) | Font name or path. |
| `resize_method`| string | LANCZOS   | Image resize method for text rendering. |

**Notes:**
- `whole_digits` and `decimal_digits` control the template used for sizing, so the text size remains stable as the value changes.
- If `negative` is enabled, space is reserved for a minus sign in the template sizing, even if the value is always positive.
- The effect is automatically centered (enforced internally).
- `display_value` is an instance attribute that can be set programmatically but is not a config option.
- The following parent options are hidden: `background_color`, `background_mode`, `height_percent`, `gradient`, and various text animation options.
