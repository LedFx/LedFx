import pathlib

__version__ = "0.1.6-alpha"
__author__ = "Austin Hodges"
__copyright__ = "Austin Hodges"
__license__ = "mit"

REQUIRED_PYTHON_VERSION = (3, 6, 0)
REQUIRED_PYTHON_STRING = '>={}.{}.{}'.format(REQUIRED_PYTHON_VERSION[0],
                                             REQUIRED_PYTHON_VERSION[1],
                                             REQUIRED_PYTHON_VERSION[2])
PROJECT_VERSION = __version__