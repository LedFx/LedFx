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

| Key                | Type    | Default   | Description |
|--------------------|---------|-----------|-------------|
| `display_value`    | float   | 0.0       | The number to display. Can be set dynamically via API or automation. |
| `whole_digits`     | int     | 2         | Number of digits before the decimal point (minimum width). |
| `decimal_digits`   | int     | 0         | Number of digits after the decimal point. |
| `color`            | color   | #ffffff   | Text color. |
| `background_color` | color   | #000000   | Background color. |

### Advanced Settings

| Key                | Type    | Default   | Description |
|--------------------|---------|-----------|-------------|
| `negative`         | bool    | false     | Reserve space for a negative sign (for template sizing). |
| `centered`         | bool    | true      | Center the text horizontally and vertically. |
| `height_percent`   | int     | 100       | Text height as a percent of the matrix height. |
| `font`             | string  | (default) | Font name or path. |

**Notes:**
- `whole_digits` and `decimal_digits` control the template used for sizing, so the text size remains stable as the value changes.
- If `negative` is enabled, space is reserved for a minus sign in the template sizing, even if the value is always positive.
- `centered` is recommended for most use cases.
