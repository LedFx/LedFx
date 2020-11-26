import pathlib

__author__ = "Austin Hodges"
__copyright__ = "Austin Hodges"
__license__ = "mit"

PROJECT_NAME = "LedFx"

REQUIRED_PYTHON_VERSION = (3, 7, 0)
REQUIRED_PYTHON_STRING = '>={}.{}.{}'.format(REQUIRED_PYTHON_VERSION[0],
                                             REQUIRED_PYTHON_VERSION[1],
                                             REQUIRED_PYTHON_VERSION[2])

MAJOR_VERSION = 0
MINOR_VERSION = 8
MICRO_VERSION = 5
PROJECT_VERSION = '{}.{}.{}'.format(MAJOR_VERSION, MINOR_VERSION, MICRO_VERSION)

__version__ = PROJECT_VERSION
