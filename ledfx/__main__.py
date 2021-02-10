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
import logging
import subprocess
import sys
import warnings
from logging.handlers import RotatingFileHandler

from pyupdater.client import Client

import ledfx.config as config_helpers
import ledfx.sentry_config  # noqa: F401
from ledfx.consts import (
    PROJECT_NAME,
    PROJECT_VERSION,
    REQUIRED_PYTHON_STRING,
    REQUIRED_PYTHON_VERSION,
)
from ledfx.core import LedFxCore
from ledfx.utils import currently_frozen

# Logger Variables
PYUPDATERLOGLEVEL = 35


def validate_python() -> None:
    """Validate the python version for when manually running"""

    if sys.version_info[:3] < REQUIRED_PYTHON_VERSION:
        print(("Python {} is required.").format(REQUIRED_PYTHON_STRING))
        sys.exit(1)


def reset_logging():
    manager = logging.root.manager
    manager.disabled = logging.NOTSET
    for logger in manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.setLevel(logging.NOTSET)
            logger.propagate = True
            logger.disabled = False
            logger.filters.clear()
            handlers = logger.handlers.copy()
            for handler in handlers:
                # Copied from `logging.shutdown`.
                try:
                    handler.acquire()
                    handler.flush()
                    handler.close()
                except (OSError, ValueError):
                    pass
                finally:
                    handler.release()
                logger.removeHandler(handler)


def setup_logging(loglevel):
    # Create a custom logging level to display pyupdater progress
    reset_logging()

    console_loglevel = loglevel or logging.WARNING
    console_logformat = "[%(levelname)-8s] %(name)-30s : %(message)s"

    file_loglevel = logging.INFO
    file_logformat = "%(asctime)-8s %(name)-30s %(levelname)-8s %(message)s"

    root_logger = logging.getLogger()

    file_handler = RotatingFileHandler(
        config_helpers.get_log_file_location(),
        mode="a",  # append
        maxBytes=0.5 * 1000 * 1000,  # 512kB
        encoding="utf8",
        backupCount=5,  # once it hits 2.5MB total, start removing logs.
    )
    file_handler.setLevel(file_loglevel)  # set loglevel
    file_formatter = logging.Formatter(
        file_logformat
    )  # a simple log file format
    file_handler.setFormatter(
        file_formatter
    )  # tell the file_handler to use this format

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_loglevel)  # set loglevel
    console_formatter = logging.Formatter(
        console_logformat
    )  # a simple console format
    console_handler.setFormatter(
        console_formatter
    )  # tell the console_handler to use this format

    # add the handlers to the root logger
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    logging.addLevelName(PYUPDATERLOGLEVEL, "Updater")

    # Suppress some of the overly verbose logs
    logging.getLogger("sacn").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("pyupdater").setLevel(logging.WARNING)
    logging.getLogger("zeroconf").setLevel(logging.DEBUG)

    global _LOGGER
    _LOGGER = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="A Networked LED Effect Controller"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="ledfx {ver}".format(ver=PROJECT_VERSION),
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        help="Directory that contains the configuration files",
        default=config_helpers.get_default_config_directory(),
        type=str,
    )
    parser.add_argument(
        "--open-ui",
        dest="open_ui",
        action="store_true",
        help="Automatically open the webinterface",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO,
    )
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG,
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        help="Web interface port",
        default=None,
        type=int,
    )
    parser.add_argument(
        "--host",
        dest="host",
        help="The address to host LedFx web interface",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--offline",
        dest="offline_mode",
        action="store_true",
        help="Disable automated updates and sentry crash logger",
    )
    parser.add_argument(
        "--sentry-crash-test",
        dest="sentry_test",
        action="store_true",
        help="This crashes LedFx to test the sentry crash logger",
    )
    return parser.parse_args()


def installed_via_pip():

    """Check to see if LedFx is installed via pip
    Returns:
        boolean
    """
    pip_package_command = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"]
    )
    installed_packages = [
        r.decode().split("==")[0] for r in pip_package_command.split()
    ]
    if "ledfx" in installed_packages:
        return True
    else:
        return False


def update_ledfx():

    # initialize & refresh in one update, check client

    class ClientConfig(object):
        PUBLIC_KEY = "Txce3TE9BUixsBtqzDba6V5vBYltt/0pw5oKL8ueCDg"
        APP_NAME = PROJECT_NAME
        COMPANY_NAME = "LedFx Developers"
        HTTP_TIMEOUT = 5
        MAX_DOWNLOAD_RETRIES = 2
        UPDATE_URLS = ["https://ledfx.app/downloads/"]

    client = Client(ClientConfig(), refresh=True)
    _LOGGER.log(PYUPDATERLOGLEVEL, "Checking for updates...")
    # First we check for updates.
    # If an update is found, an update object will be returned
    # If no updates are available, None will be returned
    ledfx_update = client.update_check(PROJECT_NAME, PROJECT_VERSION)
    # Download the update
    if ledfx_update is not None:
        _LOGGER.log(PYUPDATERLOGLEVEL, "Update found!")
        _LOGGER.log(PYUPDATERLOGLEVEL, "Downloading update, please wait...")
        ledfx_update.download()
        # Install and restart
        if ledfx_update.is_downloaded():
            _LOGGER.log(
                PYUPDATERLOGLEVEL,
                "Update downloaded, extracting and restarting...",
            )
            ledfx_update.extract_restart()
        else:
            _LOGGER.error("Unable to download update.")
    else:
        # No Updates, into main we go
        _LOGGER.log(
            PYUPDATERLOGLEVEL,
            "You're all up to date, enjoy the light show!",
        )


def main():
    """Main entry point allowing external calls"""
    args = parse_args()
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel)
    config_helpers.load_logger()

    if args.sentry_test:
        """ This will crash LedFx and submit a Sentry error if Sentry is configured """
        _LOGGER.warning("Steering LedFx into a brick wall")
        div_by_zero = 1 / 0

    if args.offline_mode is False and currently_frozen():

        warnings.filterwarnings("ignore", category=DeprecationWarning)
        update_ledfx()

    if args.offline_mode:
        _LOGGER.warning(
            "Offline Mode Enabled - Please check for updates regularly."
        )

    if not currently_frozen() and installed_via_pip():
        warnings.filterwarnings("ignore", category=DeprecationWarning)

    _LOGGER.info("LedFx Core is initializing")

    ledfx = LedFxCore(config_dir=args.config, host=args.host, port=args.port)

    ledfx.start(open_ui=args.open_ui)


if __name__ == "__main__":
    sys.exit(main())
