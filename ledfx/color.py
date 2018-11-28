from collections import namedtuple

RGB = namedtuple('RGB','red, green, blue')

COLORS = {
    'aqua': RGB(0, 255, 255),
    'black': RGB(0, 0, 0),
    'blue': RGB(0, 0, 255),
    'gold': RGB(255, 215, 0),
    'green': RGB(0, 128, 0),
    'hotpink': RGB(255, 105, 180),
    'lightblue': RGB(173, 216, 230),
    'lightgreen': RGB(152, 251, 152),
    'lightpink': RGB(255, 182, 193),
    'lightyellow': RGB(255, 255, 224),
    'magenta': RGB(255, 0, 255),
    'maroon': RGB(128, 0, 0),
    'mint': RGB(189, 252, 201),
    'navy': RGB(0, 0, 128),
    'orange': RGB(255, 128, 0),
    'orangered': RGB(255, 69, 0),
    'pink': RGB(255, 0, 178),
    'plum': RGB(221, 160, 221),
    'purple': RGB(128, 0, 128),
    'red': RGB(255, 0, 0),
    'royalblue': RGB(65, 105, 225),
    'sepia': RGB(94, 38, 18),
    'skyblue': RGB(135, 206, 235),
    'springgreen': RGB(0, 255, 127),
    'steelblue': RGB(70, 130, 180),
    'tan': RGB(210, 180, 140),
    'teal': RGB(0, 128, 128),
    'turquoise': RGB(64, 224, 208),
    'turquoiseblue': RGB(0, 199, 140),
    'violet': RGB(238, 130, 238),
    'violetred': RGB(208, 32, 144),
    'white': RGB(255, 255, 255),
    'yellow': RGB(255, 255, 0),
}

GRADIENTS = {
    "spectral"  : { 
        "colors": ["red", "orange", "yellow", "green", "lightblue", "blue", "purple", "pink"]
    },
    "dancefloor": {
        "colors": ["red", "pink", "purple", "blue"]
    },
    "sunset"    : {
        "colors": ["red", "orange", "yellow"]
    },
    "ocean"     : {
        "colors": ["green", "lightblue", "blue"]
    },
    "jungle"    : {
        "colors": ["green", "red", "orange"]
    },
    "sunny"     : {
        "colors": ["yellow", "lightblue", "orange", "blue"]
    },
    "fruity"    : {
        "colors": ["orange", "blue"]
    },
    "peach"     : {
        "colors": ["orange", "pink"]
    },
    "rust"      : {
        "colors": ["orange", "red"]
    },
    "christmas" : { 
        "colors": ["red", "red", "red", "red", "red", "green", "green", "green", "green", "green"],
        "method": "repeat"
    }
}