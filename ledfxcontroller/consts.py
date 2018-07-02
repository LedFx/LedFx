import pathlib

__version__ = "0.1.0a0"
__author__ = "Austin Hodges"
__copyright__ = "Austin Hodges"
__license__ = "mit"

REQUIRED_PYTHON_VERSION = (3, 5, 3)
REQUIRED_PYTHON_STRING = '>={}.{}.{}'.format(
    REQUIRED_PYTHON_VERSION[0],
    REQUIRED_PYTHON_VERSION[1],
    REQUIRED_PYTHON_VERSION[2])

PROJECT_ROOT = pathlib.Path(__file__).parent
PROJECT_VERSION = __version__

COLOR_TABLE = {
    "Red":(255,0,0),
    "Orange":(255,40,0),
    "Yellow":(255,255,0),
    "Green":(0,255,0),
    "Blue":(0,0,255),
    "Light Blue":(1,247,161),
    "Purple":(80,5,252),
    "Pink":(255,0,178),
    "White":(255,255,255)
}