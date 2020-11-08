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
# If we're frozen, grab the pyupdater stuff so we can do updates
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    class ClientConfigData(object):
        PUBLIC_KEY = 'Txce3TE9BUixsBtqzDba6V5vBYltt/0pw5oKL8ueCDg'
        APP_NAME = 'LedFx'
        COMPANY_NAME = 'LedFx Developers'
        HTTP_TIMEOUT = 30
        MAX_DOWNLOAD_RETRIES = 3
        UPDATE_URLS = ['https://ledfx.app/downloads/']
    def print_status_info(info):
        # Here you could as the user here if they would
        # like to install the new update and restart
        total = info.get(u'total')
        downloaded = info.get(u'downloaded')
        status = info.get(u'status')
        print(downloaded, total, status)
    from pyupdater.client import Client


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

## Pyupdater stuff

## Are we frozen? Pyupdater needs to be called. If not, main it is.
def checkfrozen():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        pyupdaterprocess()
    else:
        main()

def pyupdaterprocess():
    # in future we can use the defined consts, but for now for dev
    APP_NAME = 'LedFx'
    APP_VERSION = '0.0.4'
    # initialize & refresh in one update check client
    client = Client(ClientConfigData(), refresh=True, callback=print_status_info)
    # First we check for updates.
    # If an update is found an update object will be returned
    # If no updates are available, None will be returned
    ledfx_update = client.update_check(APP_NAME, APP_VERSION)
    # Download the update
    if ledfx_update is not None:
        ledfx_update.download()
        print_status_info(ledfx_update)
    # Install and restart

    if ledfx_update is not None and ledfx_update.is_downloaded():
       ledfx_update.extract_restart()
    else:
        # No Updates, into main we go
        main()
    #  End PyUpdater Block

def main():
    """Main entry point allowing external calls"""
    args = parse_args()
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel)
    ledfx = LedFxCore(config_dir = args.config, 
        host = args.host, 
        port = args.port)
    ledfx.start(open_ui = args.open_ui)
if __name__ == "__main__":
    sys.exit(main())