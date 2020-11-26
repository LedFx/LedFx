import pathlib
# Couldn't get this to work. Will revisit.
#from packaging.version import Version

__author__ = "Austin Hodges"
__copyright__ = "Austin Hodges"
__license__ = "mit"

PROJECT_NAME = "LedFx"

REQUIRED_PYTHON_VERSION = (3, 7, 0)
REQUIRED_PYTHON_STRING = '>={}.{}.{}'.format(REQUIRED_PYTHON_VERSION[0],
                                             REQUIRED_PYTHON_VERSION[1],
                                             REQUIRED_PYTHON_VERSION[2])

MAJOR_VERSION = 0
MINOR_VERSION = 9
MICRO_VERSION = 0
POST          = 0
DEV           = 0
PROJECT_VERSION = '{}.{}.{}'.format(MAJOR_VERSION, MINOR_VERSION, MICRO_VERSION)

if DEV > 0:
  DEV_VERSION = '{}-dev{}'.format(PROJECT_VERSION, DEV)
  #DEV_VERSION = Version(DEV_VERSION).public

if POST > 0:
  POST_VERSION = '{}-post{}'.format(PROJECT_VERSION, POST)
  #POST_VERSION = Version(POST_VERSION).public

#PROJECT_VERSION = Version(PROJECT_VERSION).public

__version__ = PROJECT_VERSION