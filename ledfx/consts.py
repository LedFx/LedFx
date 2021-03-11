# Couldn't get this to work. Will revisit.
# from packaging.version import Version

__author__ = "Austin Hodges"
__copyright__ = "Austin Hodges"
__license__ = "mit"

PROJECT_NAME = "LedFx"

REQUIRED_PYTHON_VERSION = (3, 9, 0)
REQUIRED_PYTHON_STRING = ">={}.{}.{}".format(
    REQUIRED_PYTHON_VERSION[0],
    REQUIRED_PYTHON_VERSION[1],
    REQUIRED_PYTHON_VERSION[2],
)

MAJOR_VERSION = 1
MINOR_VERSION = 0
MICRO_VERSION = 0
POST = 0
DEV = 1
PROJECT_VERSION = "{}.{}.{}".format(
    MAJOR_VERSION, MINOR_VERSION, MICRO_VERSION
)
DEV_VERSION = 0
POST_VERSION = 0
CONFIG_MAJOR_VERSION = 1
CONFIG_MINOR_VERSION = 0
CONFIG_MICRO_VERSION = 0

CONFIGURATION_VERSION = "{}.{}.{}".format(
    CONFIG_MAJOR_VERSION, CONFIG_MINOR_VERSION, CONFIG_MICRO_VERSION
)

if DEV > 0:
    DEV_VERSION = "{}-dev{}".format(PROJECT_VERSION, DEV)

if POST > 0:
    POST_VERSION = "{}-post{}".format(PROJECT_VERSION, POST)

__version__ = PROJECT_VERSION

if __name__ == "__main__":
    print(__version__)
