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
        "linear-gradient(90deg, #7873f5 0%, #800000 50%, #ec77ab 100%)"
        "mode(angle, *colors)"
        where each color is associated with a % value for its position in the gradient
        """
        # Get mode
        mode, angle_colors = gradient_str.split("(")
        mode.strip("-gradient")
        # Get angle
        angle, *colors = angle_colors.strip(")").split(",")
        angle = int(angle.strip("deg"))
        # Split each color/position string
        colors = [color.strip(" ").split(" ") for color in colors]
        # Parse color and position
        colors = [
            (parse_color(color), float(position.strip("%")) / 100.0)
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


def validate_color(color: str) -> str:
    try:
        return "#%02x%02x%02x" % parse_color(color)
    except ValueError:
        return "#000000"


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
    "Rainbow": {
        "colors": [
            "red",
            "orange",
            "yellow",
            "green",
            "green-turquoise",
            "blue",
            "purple",
            "pink",
        ]
    },
    "Dancefloor": {"colors": ["red", "pink", "blue"]},
    "Plasma": {"colors": ["blue", "purple", "red", "orange-deep", "yellow"]},
    "Ocean": {"colors": ["blue-aqua", "blue"]},
    "Viridis": {"colors": ["purple", "blue", "green-teal", "green", "yellow"]},
    "Jungle": {"colors": ["green", "green-forest", "orange"]},
    "Spring": {"colors": ["pink", "orange-deep", "yellow"]},
    "Winter": {"colors": ["green-turquoise", "green-coral"]},
    "Frost": {"colors": ["blue", "blue-aqua", "purple", "pink"]},
    "Sunset": {"colors": ["blue-navy", "orange", "red"]},
    "Borealis": {
        "colors": [
            "orange-deep",
            "purple",
            "green-turquoise",
            "green",
        ]
    },
    "Rust": {"colors": ["orange-deep", "red"]},
    "Christmas": {
        "colors": [
            "red",
            "red",
            "red",
            "red",
            "red",
            "green",
            "green",
            "green",
            "green",
            "green",
        ],
        "method": "repeat",
    },
    "Winamp": {
        "colors": [
            "green",
            "yellow",
            "orange",
            "orange-deep",
            "red",
        ]
    },
}
