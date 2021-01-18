from collections import namedtuple

RGB = namedtuple("RGB", "red, green, blue")

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
    "brown": RGB(139, 69, 19),
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
