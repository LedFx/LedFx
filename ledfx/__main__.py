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

from ledfx.consts import (
    REQUIRED_PYTHON_VERSION, REQUIRED_PYTHON_STRING,
    PROJECT_VERSION, PROJECT_NAME)
from ledfx.core import LedFxCore
import ledfx.config as config_helpers

_LOGGER = logging.getLogger(__name__)

def validate_python() -> None:
    """Validate the python version for when manually running"""

    if sys.version_info[:3] < REQUIRED_PYTHON_VERSION:
        print(('Python {} is required.').format(REQUIRED_PYTHON_STRING))
        sys.exit(1)

def setup_logging(loglevel):
    loglevel = loglevel if loglevel else logging.WARNING
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")
    logging.getLogger().setLevel(loglevel)

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

def check_frozen():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def update_ledfx():
    # in future we can use the defined consts, but for now for dev
    # initialize & refresh in one update check client
    class ClientConfig(object):
        PUBLIC_KEY = 'Txce3TE9BUixsBtqzDba6V5vBYltt/0pw5oKL8ueCDg'
        APP_NAME = PROJECT_NAME
        COMPANY_NAME = 'LedFx Developers'
        HTTP_TIMEOUT = 30
        MAX_DOWNLOAD_RETRIES = 3
        UPDATE_URLS = ['https://ledfx.app/downloads/']

    client = Client(ClientConfig(), refresh=True)
    _LOGGER.info('Checking for updates...')
    # First we check for updates.
    # If an update is found an update object will be returned
    # If no updates are available, None will be returned
    ledfx_update = client.update_check(PROJECT_NAME, PROJECT_VERSION)
    # Download the update
    if ledfx_update is not None:
        _LOGGER.info("Update found!")
        _LOGGER.info("Downloading update, please wait...")
        ledfx_update.download()
        # Install and restart
        if ledfx_update.is_downloaded():
            _LOGGER.info("Update downloaded, extracting and restarting...")
            ledfx_update.extract_restart()
        else:
            _LOGGER.info("Unable to download update.")
    else:
        # No Updates, into main we go
        _LOGGER.info("You're all up to date, enjoy the light show!")

def main():
    """Main entry point allowing external calls"""
    args = parse_args()
    setup_logging(args.loglevel)
    # If LedFx is a frozen windows build, it can auto-update itself
    if check_frozen():
        update_ledfx()
    config_helpers.ensure_config_directory(args.config)
    ledfx = LedFxCore(config_dir = args.config,
                      host = args.host,
                      port = args.port)

    ledfx.start(open_ui = args.open_ui)


if __name__ == "__main__":
    sys.exit(main())
