import logging
from collections import namedtuple

import numpy as np
from PIL import ImageColor

_LOGGER = logging.getLogger(__name__)
RGBA = namedtuple("RGBA", ("red", "green", "blue", "alpha"), defaults=(255,))
RGB = namedtuple("RGB", ("red", "green", "blue"))


class Gradient:
    """
    Represents a gradient with a list of colors and a mode.

    Attributes:
        colors (list): A list of tuples representing colors and their positions in the gradient.
        mode (str): The mode of the gradient (e.g., "linear", "radial").
        angle (str): The angle of the gradient (e.g., "90deg").

    Methods:
        from_string(cls, gradient_str: str) -> Gradient: Parses a gradient from a string.
    """

    __slots__ = "colors", "mode", "angle"

    @classmethod
    def from_string(cls, gradient_str: str):
        """
        Parses a gradient from a string of the format:
        "linear-gradient(90deg, rgb(100, 0, 255) 0%, #800000 50%, #ec77ab 100%)"
        or
        "mode(angle, *colors)"
        where each color is associated with a % value for its position in the gradient.

        Args:
            gradient_str (str): The string representation of the gradient.

        Returns:
            Gradient: The parsed gradient object.
        """
        # If gradient is predefined, get the definition
        gradient_str = LEDFX_GRADIENTS.get(gradient_str, gradient_str)
        # Get mode
        mode, angle_colors = gradient_str.split("(", 1)
        mode.strip("-gradient")
        # Get angle
        angle, colors = angle_colors.strip(")").split(",", 1)
        angle = int(angle.strip("deg"))
        # Split each color/position string
        colors = colors.split("%")
        colors = [
            color.strip(", ").rsplit(" ", 1)
            for color in colors
            if color.strip()
        ]
        # Parse color and position
        colors = [
            (parse_color(color), float(position) / 100.0)
            for color, position in colors
        ]
        # Sort color list by position (0.0->1.0)
        colors.sort(key=lambda tup: tup[1])

        return cls(colors, mode, angle)

    def __init__(self, colors, mode="linear", angle="90"):
        self.colors = colors
        self.mode = mode
        self.angle = angle


def hsv_to_rgb(hsv):
    """
    Vectorized conversion of an entire pixel array from hsv colorspace to rgb colorspace.
    Approx 3x faster than using colorsys.hsv_to_rgb on a single pixel, and performance improvement is exponential with the number of pixels.

    Algorithm from https://en.wikipedia.org/wiki/HSL_and_HSV#HSV_to_RGB

    Parameters:
    - hsv: numpy array of shape (n, 3) representing the HSV values of pixels

    Returns:
    - rgb: numpy array of shape (n, 3) representing the RGB values of pixels
    """
    # Extract the hue, saturation, and value components from the HSV color space
    hue, saturation, value = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    # Compute the chroma, which is the colorfulness relative to the brightness of another color that appears white under similar viewing conditions
    chroma = value * saturation

    # Multiply the hue by 6 to map it to a sector number, as per the HSV to RGB conversion algorithm
    # These six hue sectors represent the six transitions between primary and secondary colors on the color wheel
    # The hue value is an angle between 0 and 360 degrees, so we need to multiply it by 6 to map it to a sector number
    hue *= 6

    # Compute the intermediate value used in the RGB conversion
    intermediate_value = chroma * (1 - np.abs(hue % 2 - 1))

    # Initialize the RGB values array with zeros, having the same shape as the HSV input
    rgb_values = np.zeros(hsv.shape)

    # For each sector of the hue, calculate the corresponding RGB values
    # The RGB conversion algorithm is different for each sector of the hue

    # Sector 0 to 1 (red to yellow)
    mask = (0 <= hue) & (hue <= 1)
    rgb_values[mask, 0] = chroma[mask]  # Red is dominant
    rgb_values[mask, 1] = intermediate_value[mask]  # Green is increasing

    # Sector 1 to 2 (yellow to green)
    mask = (1 < hue) & (hue <= 2)
    rgb_values[mask, 0] = intermediate_value[mask]  # Red is decreasing
    rgb_values[mask, 1] = chroma[mask]  # Green is dominant

    # Sector 2 to 3 (green to cyan)
    mask = (2 < hue) & (hue <= 3)
    rgb_values[mask, 1] = chroma[mask]  # Green is dominant
    rgb_values[mask, 2] = intermediate_value[mask]  # Blue is increasing

    # Sector 3 to 4 (cyan to blue)
    mask = (3 < hue) & (hue <= 4)
    rgb_values[mask, 1] = intermediate_value[mask]  # Green is decreasing
    rgb_values[mask, 2] = chroma[mask]  # Blue is dominant

    # Sector 4 to 5 (blue to magenta)
    mask = (4 < hue) & (hue <= 5)
    rgb_values[mask, 0] = intermediate_value[mask]  # Red is increasing
    rgb_values[mask, 2] = chroma[mask]  # Blue is dominant

    # Sector 5 to 6 (magenta to red)
    mask = (5 < hue) & (hue <= 6)
    rgb_values[mask, 0] = chroma[mask]  # Red is dominant
    rgb_values[mask, 2] = intermediate_value[mask]  # Blue is decreasing

    # Compute the match value to match the RGB values with the original value
    match_value = value - chroma

    # Add the match value to each RGB component to align it with the original value
    rgb_values[:, 0] += match_value
    rgb_values[:, 1] += match_value
    rgb_values[:, 2] += match_value

    # Return the RGB values, scaled to the range 0-255 as per the standard RGB color space
    return rgb_values * 255


def parse_color(color: (str, list, tuple)) -> RGB:
    """
    Parses a color value and returns an RGB object.

    Args:
        color (str, list, tuple): The color value to be parsed. It can be a string representing a color name,
                                 a list/tuple representing RGB values, or a string representing a HEX color code.

    Returns:
        RGB: An RGB object representing the parsed color.

    Raises:
        ValueError: If the color value is invalid or cannot be parsed.

    """
    try:
        # If it's a list/tuple, interpret it as RGB(A removed)
        if isinstance(color, (list, tuple)):
            # assert 3 <= len(color) <= 4
            assert len(color) == 3
            return RGB(*color)
        # Otherwise, it needs to be a string to continue
        if not isinstance(color, str):
            raise ValueError
        # Try to find the color in the pre-defined dict
        if color in LEDFX_COLORS:
            color = LEDFX_COLORS[color]
        # Try to parse it as a HEX (with or without alpha)
        if color.startswith("#"):
            color = color.strip("#")
            # return RGB(*int(color, 16).to_bytes(len(color) // 2, "big"))
            return RGB(*int(color, 16).to_bytes(3, "big"))
        # Failing that, try to parse it using ImageColor
        return RGB(*ImageColor.getrgb(color))
    except (ValueError, AssertionError):
        msg = f"Invalid color: {color}"
        # _LOGGER.error(msg)
        raise ValueError(msg)


def parse_gradient(gradient: str):
    """
    Parse a gradient string and return the corresponding gradient object.

    The gradient can be either a color or a full gradient. The function tries to parse
    the gradient using the `Gradient.from_string` and `parse_color` functions. If
    successful, it returns the parsed gradient object. If parsing fails, an error message
    is logged and a `ValueError` is raised.

    Args:
        gradient (str): The gradient string to parse.

    Returns:
        Gradient: The parsed gradient object.

    Raises:
        ValueError: If the gradient string is invalid.
    """
    for func in Gradient.from_string, parse_color:
        try:
            return func(gradient)
        except Exception:
            continue
    else:
        msg = f"Invalid gradient: {gradient}"
        _LOGGER.error(msg)
        raise ValueError(msg)


def validate_color(color: str) -> str:
    """
    Validates and formats a color string.

    Args:
        color (str): The color string to validate.

    Returns:
        str: The validated and formatted color string.

    """
    return "#%02x%02x%02x" % parse_color(color)


def validate_gradient(gradient: str) -> str:
    """
    Validates the given gradient string.

    Args:
        gradient (str): The gradient string to be validated.

    Returns:
        str: The validated gradient string.
    """
    parse_gradient(gradient)
    return gradient


LEDFX_COLORS = {
    "red": "#ff0000",
    "orange-deep": "#ff2800",
    "orange": "#ff7800",
    "yellow": "#ffc800",
    "yellow-acid": "#a0ff00",
    "green": "#00ff00",
    "green-forest": "#228b22",
    "green-spring": "#00ff7f",
    "green-teal": "#008080",
    "green-turquoise": "#00c78c",
    "green-coral": "#00ff32",
    "cyan": "#00ffff",
    "blue": "#0000ff",
    "blue-light": "#4169e1",
    "blue-navy": "#000080",
    "blue-aqua": "#00ffff",
    "purple": "#800080",
    "pink": "#ff00b2",
    "magenta": "#ff00ff",
    "black": "#000000",
    "white": "#ffffff",
    "gold": "#ffd700",
    "hotpink": "#ff69b4",
    "lightblue": "#add8e6",
    "lightgreen": "#98fb98",
    "lightpink": "#ffb6c1",
    "lightyellow": "#ffffe0",
    "maroon": "#800000",
    "mint": "#bdfcc9",
    "olive": "#556b2f",
    "peach": "#ff6464",
    "plum": "#dda0dd",
    "sepia": "#5e2612",
    "skyblue": "#87ceeb",
    "steelblue": "#4682b4",
    "tan": "#d2b48c",
    "violetred": "#d02090",
}

LEDFX_GRADIENTS = {
    "Rainbow": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)",
    "Dancefloor": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 0, 178) 50%, rgb(0, 0, 255) 100%)",
    "Plasma": "linear-gradient(90deg, rgb(0, 0, 255) 0%, rgb(128, 0, 128) 25%, rgb(255, 0, 0) 50%, rgb(255, 40, 0) 75%, rgb(255, 200, 0) 100%)",
    "Ocean": "linear-gradient(90deg, rgb(0, 255, 255) 0%, rgb(0, 0, 255) 100%)",
    "Viridis": "linear-gradient(90deg, rgb(128, 0, 128) 0%, rgb(0, 0, 255) 25%, rgb(0, 128, 128) 50%, rgb(0, 255, 0) 75%, rgb(255, 200, 0) 100%)",
    "Jungle": "linear-gradient(90deg, rgb(0, 255, 0) 0%, rgb(34, 139, 34) 50%, rgb(255, 120, 0) 100%)",
    "Spring": "linear-gradient(90deg, rgb(255, 0, 178) 0%, rgb(255, 40, 0) 50%, rgb(255, 200, 0) 100%)",
    "Winter": "linear-gradient(90deg, rgb(0, 199, 140) 0%, rgb(0, 255, 50) 100%)",
    "Frost": "linear-gradient(90deg, rgb(0, 0, 255) 0%, rgb(0, 255, 255) 33%, rgb(128, 0, 128) 66%, rgb(255, 0, 178) 99%)",
    "Sunset": "linear-gradient(90deg, rgb(0, 0, 128) 0%, rgb(255, 120, 0) 50%, rgb(255, 0, 0) 100%)",
    "Borealis": "linear-gradient(90deg, rgb(255, 40, 0) 0%, rgb(128, 0, 128) 33%, rgb(0, 199, 140) 66%, rgb(0, 255, 0) 99%)",
    "Rust": "linear-gradient(90deg, rgb(255, 40, 0) 0%, rgb(255, 0, 0) 100%)",
    "Winamp": "linear-gradient(90deg, rgb(0, 255, 0) 0%, rgb(255, 200, 0) 25%, rgb(255, 120, 0) 50%, rgb(255, 40, 0) 75%, rgb(255, 0, 0) 100%)",
}
