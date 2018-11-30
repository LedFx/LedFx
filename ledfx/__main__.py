#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Entry point for the ledfx controller. To run this script for development
purposes use:

    [console_scripts]
    python setup.py develop
    ledfx

For non-development purposes run:

    [console_scripts]
    python setup.py install
    ledfx

"""

import argparse
import sys
import logging

from ledfx.consts import (
    REQUIRED_PYTHON_VERSION, REQUIRED_PYTHON_STRING,
    PROJECT_VERSION)
from ledfx.core import LedFxCore
import ledfx.config as config_helpers

_LOGGER = logging.getLogger(__name__)

def validate_python() -> None:
    """Validate the python version for when manually running"""

    if sys.version_info[:3] < REQUIRED_PYTHON_VERSION:
        print(('Python {} is required.').format(REQUIRED_PYTHON_STRING))
        sys.exit(1)

def setup_logging(loglevel):
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")

    # Suppress some of the overly verbose logs
    logging.getLogger('sacn').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

def parse_args():
    parser = argparse.ArgumentParser(
        description="A Networked LED Effect Controller")
    parser.add_argument(
        '--version',
        action='version',
        version='ledfx {ver}'.format(ver=PROJECT_VERSION))
    parser.add_argument(
        '-c',
        '--config',
        dest="config",
        help="Directory that contains the configuration files",
        default=config_helpers.get_default_config_directory(),
        type=str)
    parser.add_argument(
        '--open-ui',
        action='store_true',
        help='Automatically open the webinterface')
    parser.add_argument(
        '-v',
        '--verbose',
        dest="loglevel",
        help="set loglevel to INFO",
        action='store_const',
        const=logging.INFO)
    parser.add_argument(
        '-vv',
        '--very-verbose',
        dest="loglevel",
        help="set loglevel to DEBUG",
        action='store_const',
        const=logging.DEBUG)
    return parser.parse_args()

def main():
    """Main entry point allowing external calls"""

    args = parse_args()
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel)

    ledfx = LedFxCore(config_dir = args.config)
    ledfx.start(open_ui = args.open_ui)

if __name__ == "__main__":
    sys.exit(main())