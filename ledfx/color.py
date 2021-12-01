import logging
from collections import namedtuple

from PIL import ImageColor

_LOGGER = logging.getLogger(__name__)
RGBA = namedtuple("RGBA", ("red", "green", "blue", "alpha"), defaults=(255,))
RGB = namedtuple("RGB", ("red", "green", "blue"))


class Gradient:
    __slots__ = "colors", "mode", "angle"

    @classmethod
    def from_string(cls, gradient_str: str):
        """
        Parses gradient from string of format eg.
        "linear-gradient(90deg, rgb(100, 0, 255) 0%, #800000 50%, #ec77ab 100%)"
        "mode(angle, *colors)"
        where each color is associated with a % value for its position in the gradient
        """
        # If gradient is predefined, get the definition
        gradient_str = GRADIENTS.get(gradient_str, gradient_str)
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


def parse_color(color: (str, list, tuple)) -> RGB:
    try:
        # If it's a list/tuple, interpret it as RGB(A removed)
        if isinstance(color, (list, tuple)):
            # assert 3 <= len(color) <= 4
            assert len(color) == 3
            return RGB(*color)
        # Otherwise, it needs to be a string to continue
        if not isinstance(color, str):
            raise ValueError
        # Try to parse it as a HEX (with or without alpha)
        if color.startswith("#"):
            color = color.strip("#")
            # return RGB(*int(color, 16).to_bytes(len(color) // 2, "big"))
            return RGB(*int(color, 16).to_bytes(3, "big"))
        # Try to find the color in the pre-defined dict
        if color in COLORS:
            return COLORS[color]
        # Failing that, try to parse it using ImageColor
        return RGB(*ImageColor.getrgb(color))
    except (ValueError, AssertionError):
        msg = f"Invalid colour: {color}"
        _LOGGER.error(msg)
        raise ValueError(msg)


def parse_gradient(gradient: str):
    # Gradient can just be a color, or a full gradient
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
    return "#%02x%02x%02x" % parse_color(color)


def validate_gradient(gradient: str) -> str:
    parse_gradient(gradient)
    return gradient


COLORS = {
    "red": RGB(255, 0, 0),
    "orange-deep": RGB(255, 40, 0),
    "orange": RGB(255, 120, 0),
    "yellow": RGB(255, 200, 0),
    "yellow-acid": RGB(160, 255, 0),
    "green": RGB(0, 255, 0),
    "green-forest": RGB(34, 139, 34),
    "green-spring": RGB(0, 255, 127),
    "green-teal": RGB(0, 128, 128),
    "green-turquoise": RGB(0, 199, 140),
    "green-coral": RGB(0, 255, 50),
    "cyan": RGB(0, 255, 255),
    "blue": RGB(0, 0, 255),
    "blue-light": RGB(65, 105, 225),
    "blue-navy": RGB(0, 0, 128),
    "blue-aqua": RGB(0, 255, 255),
    "purple": RGB(128, 0, 128),
    "pink": RGB(255, 0, 178),
    "magenta": RGB(255, 0, 255),
    "black": RGB(0, 0, 0),
    "white": RGB(255, 255, 255),
    "gold": RGB(255, 215, 0),
    "hotpink": RGB(255, 105, 180),
    "lightblue": RGB(173, 216, 230),
    "lightgreen": RGB(152, 251, 152),
    "lightpink": RGB(255, 182, 193),
    "lightyellow": RGB(255, 255, 224),
    "maroon": RGB(128, 0, 0),
    "mint": RGB(189, 252, 201),
    "olive": RGB(85, 107, 47),
    "peach": RGB(255, 100, 100),
    "plum": RGB(221, 160, 221),
    "sepia": RGB(94, 38, 18),
    "skyblue": RGB(135, 206, 235),
    "steelblue": RGB(70, 130, 180),
    "tan": RGB(210, 180, 140),
    "violetred": RGB(208, 32, 144),
}


GRADIENTS = {
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
