import logging
from collections import namedtuple
from typing import Optional, Tuple, Union

import numpy as np
from numpy.typing import NDArray
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

    def sample(self, position: float) -> str:
        """
        Return a hex color string sampled from this Gradient at a normalized
        position in [0.0, 1.0].
        """
        pos = max(0.0, min(1.0, float(position)))

        # Expecting self.colors as iterable of (RGB, pos) pairs
        stops = list(self.colors)
        # Ensure sorted by position
        stops.sort(key=lambda c: c[1])

        # Fast bounds
        first_color, first_pos = stops[0]
        last_color, last_pos = stops[-1]
        if pos <= first_pos:
            return "#{:02x}{:02x}{:02x}".format(
                first_color.red,
                first_color.green,
                first_color.blue,
            )
        if pos >= last_pos:
            return "#{:02x}{:02x}{:02x}".format(
                last_color.red,
                last_color.green,
                last_color.blue,
            )

        # Find containing segment and linearly interpolate
        for (c1, p1), (c2, p2) in zip(stops, stops[1:]):
            if p1 <= pos <= p2:
                t = 0.0 if p2 == p1 else (pos - p1) / (p2 - p1)
                r = int(round(c1.red + (c2.red - c1.red) * t))
                g = int(round(c1.green + (c2.green - c1.green) * t))
                b = int(round(c1.blue + (c2.blue - c1.blue) * t))
                return "#{:02x}{:02x}{:02x}".format(r, g, b)

        # Fallback
        return "#000000"


def hsv_to_rgb(hue: NDArray, saturation: float, value: float) -> NDArray:
    """
    Converts an array of Hues using provided saturation and value properties to an RGB array.

    Args:
        hue (numpy.ndarray): Array of hue values (0 to 1).
        saturation (float between 0 and 1): The saturation ("brightness") of the color.
        value (float between 0 and 1): The value ("colorfulness") of the color.

    Returns:
        numpy.ndarray: An array of RGB values where each RGB value is in the range
                       0 to 255.

    """

    # The hue value is scaled by 6 to map it to one of the six sections of the
    # RGB color wheel.
    hue_i = hue * 6

    # The integer part of h_i determines the section of the color wheel the hue
    # belongs to.
    i = np.floor(hue_i).astype(int)

    # The fractional part of h_i.
    f = hue_i - i

    # Intermediate values for the RGB conversion process.
    p = value * (1 - saturation)
    q = value * (1 - saturation * f)
    t = value * (1 - saturation * (1 - f))

    # Ensure that i values are within the range [0, 5].
    i = i % 6

    # Preparing an array for RGB values.
    rgb = np.zeros((hue.shape[0], 3))

    # Assigning the red, green, and blue components based on the section of the
    # color wheel. 'np.choose' is used to efficiently select values for each pixel.
    rgb[:, 0] = np.choose(i, [value, q, p, p, t, value], mode="wrap")
    rgb[:, 1] = np.choose(i, [t, value, value, q, p, p], mode="wrap")
    rgb[:, 2] = np.choose(i, [p, p, t, value, value, q], mode="wrap")

    # Scale the RGB values to the 0-255 range
    return rgb * 255


def hsv_to_rgb_vect(h, s, v, out=None):
    """
    h, s, v: float32 arrays (N,) in [0,1]
    Returns float32 RGB in [0,255]. If `out` (N,3) float32 is provided, writes in-place.
    """
    h = np.asarray(h, dtype=np.float32)
    s = np.asarray(s, dtype=np.float32)
    v = np.asarray(v, dtype=np.float32)

    N = h.shape[0]
    if out is None:
        out = np.empty((N, 3), dtype=np.float32)

    r = out[:, 0]
    g = out[:, 1]
    b = out[:, 2]

    h6 = (h * 6.0).astype(np.float32)
    i = np.floor(h6).astype(np.int32)  # sector 0..5
    f = h6 - i

    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    m0 = i == 0
    r[m0] = v[m0]
    g[m0] = t[m0]
    b[m0] = p[m0]
    m1 = i == 1
    r[m1] = q[m1]
    g[m1] = v[m1]
    b[m1] = p[m1]
    m2 = i == 2
    r[m2] = p[m2]
    g[m2] = v[m2]
    b[m2] = t[m2]
    m3 = i == 3
    r[m3] = p[m3]
    g[m3] = q[m3]
    b[m3] = v[m3]
    m4 = i == 4
    r[m4] = t[m4]
    g[m4] = p[m4]
    b[m4] = v[m4]
    m5 = i >= 5
    r[m5] = v[m5]
    g[m5] = p[m5]
    b[m5] = q[m5]

    out *= 255.0
    return out


def rgb_to_hsv_vect(rgb, out=None):
    """
    rgb: (N,3) or (3,) uint8/float; returns float32 HSV in [0,1].
    If `out` (N,3) float32 is provided, writes in-place.
    """
    arr = np.asarray(rgb, dtype=np.float32)
    scalar = arr.ndim == 1
    if scalar:
        arr = arr[np.newaxis, :]

    arr = arr / 255.0
    r, g, b = arr[:, 0], arr[:, 1], arr[:, 2]

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    if out is None:
        out = np.empty((arr.shape[0], 3), dtype=np.float32)
    h = out[:, 0]
    s = out[:, 1]
    v = out[:, 2]

    v[:] = maxc

    s[:] = 0.0
    nz = maxc != 0.0
    s[nz] = delta[nz] / maxc[nz]

    h[:] = 0.0
    mask = delta > 0.0
    r_eq = (maxc == r) & mask
    g_eq = (maxc == g) & mask
    b_eq = (maxc == b) & mask

    h[r_eq] = ((g[r_eq] - b[r_eq]) / delta[r_eq]) % 6.0
    h[g_eq] = ((b[g_eq] - r[g_eq]) / delta[g_eq]) + 2.0
    h[b_eq] = ((r[b_eq] - g[b_eq]) / delta[b_eq]) + 4.0

    h[:] = (h / 6.0) % 1.0
    return out[0] if scalar else out


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


def get_color_at_position(gradient_like, position: float) -> str:
    """
    Accepts a Gradient instance, an inline gradient string, or a simple color
    string and returns a hex color sampled at `position` (0.0..1.0).
    """
    # If caller passed a Gradient instance, use it directly
    if isinstance(gradient_like, Gradient):
        return gradient_like.sample(position)

    # If it is a simple RGB value returned by parse_gradient, handle
    try:
        parsed = parse_gradient(gradient_like)
    except Exception:
        # If parse fails, assume it's a color string and validate
        return validate_color(gradient_like)

    if isinstance(parsed, RGB):
        return "#%02x%02x%02x" % parsed

    # Otherwise parsed is a Gradient
    return parsed.sample(position)


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


def resolve_gradient(
    value: str, gradients_collection
) -> tuple[str, Optional[Gradient]]:
    """Resolve a gradient input into a config string and an optional parsed Gradient.

    Args:
        value: user input (preset name or inline gradient string)
        gradients_collection: collection object exposing get_all() and __getitem__()

    Returns:
        (config_string, parsed_gradient_or_None)

    Raises:
        ValueError: if the inline gradient is invalid.
    """
    trimmed = value.strip()

    # prefer user gradients over builtins for the stored config string
    defaults, user_vals = gradients_collection.get_all()
    raw_gradient = user_vals.get(trimmed) or defaults.get(trimmed)

    if raw_gradient:
        config_string = raw_gradient
    else:
        # validate inline gradient string, will raise if invalid
        validate_gradient(trimmed)
        config_string = trimmed

    # Resolve parsed gradient for sampling: prefer collection lookup
    parsed = None
    try:
        parsed = gradients_collection[trimmed]
    except Exception:
        try:
            parsed = parse_gradient(trimmed)
        except Exception as e:
            _LOGGER.warning(f"Failed to parse gradient {trimmed}: {e}")
            parsed = None

    return config_string, parsed


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
