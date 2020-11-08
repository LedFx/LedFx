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

from pyupdater.client import Client
from client_config import ClientConfig

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
    parser.add_argument(
        '-p',
        '--port',
        dest="port",
        help="Web interface port",
        default=None,
        type=int)
    parser.add_argument(
        '--host',
        dest="host",
        help="The address to host LedFx web interface",
        default=None,
        type=str)
    return parser.parse_args()

def main():
    """Main entry point allowing external calls"""
#
# PYUPDATER BLOCK
#



APP_NAME = 'LedFx'
# in future we can use the defined consts, but for now for dev
APP_VERSION = '0.0.4'


# PyUpdater uses callbacks for download progress
def print_status_info(info):
    # Here you could as the user here if they would
    # like to install the new update and restart
    total = info.get(u'total')
    downloaded = info.get(u'downloaded')
    status = info.get(u'status')
    print(downloaded, total, status)

# initialize & refresh in one update check client
client = Client(ClientConfig(), refresh=True, callback=print_status_info)
# First we check for updates.
# If an update is found an update object will be returned
# If no updates are available, None will be returned
ledfx_update = client.update_check(APP_NAME, APP_VERSION)
# Example of downloading on the main thread
if ledfx_update is not None:
    ledfx_update.download()
    print_status_info(ledfx_update)



# Install and restart with one method
# Note if your updating a lib this method will not be available
    if ledfx_update is not None and ledfx_update.is_downloaded():
        ledfx_update.extract_restart()
else:
#
#  End PyUpdater Block
#  Don't forget to remove the indents if you move pyupdater functions, you idiot
    args = parse_args()
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel)

    ledfx = LedFxCore(config_dir = args.config, 
                      host = args.host, 
                      port = args.port)
    ledfx.start(open_ui = args.open_ui)
if __name__ == "__main__":
    sys.exit(main())