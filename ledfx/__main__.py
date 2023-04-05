#!/usr/bin/env python
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
import importlib
import logging
import os
import subprocess
import sys
from logging.handlers import RotatingFileHandler

try:
    import psutil

    have_psutil = True
except ImportError:
    have_psutil = False


import ledfx.config as config_helpers
from ledfx.consts import (
    PROJECT_VERSION,
    REQUIRED_PYTHON_STRING,
    REQUIRED_PYTHON_VERSION,
)
from ledfx.core import LedFxCore
from ledfx.utils import currently_frozen, get_icon_path


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


def setup_logging(loglevel, config_dir):
    console_loglevel = loglevel or logging.WARNING
    console_logformat = "[%(levelname)-8s] %(name)-30s : %(message)s"

    file_loglevel = logging.INFO
    file_logformat = "%(asctime)-8s %(name)-30s %(levelname)-8s %(message)s"

    root_logger = logging.getLogger()

    file_handler = RotatingFileHandler(
        config_helpers.get_log_file_location(config_dir),
        mode="a",  # append
        maxBytes=0.5 * 1000 * 1000,  # 512kB
        encoding="utf8",
        backupCount=5,  # once it hits 2.5MB total, start removing logs.
    )
    file_handler.setLevel(file_loglevel)  # set loglevel
    file_formatter = logging.Formatter(file_logformat)
    file_handler.setFormatter(file_formatter)

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

    # Suppress some of the overly verbose logs
    logging.getLogger("sacn").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("zeroconf").setLevel(logging.WARNING)

    global _LOGGER
    _LOGGER = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="A Networked LED Effect Controller"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"ledfx {PROJECT_VERSION}",
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
        help="Web interface port (HTTP)",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-p_s",
        "--port_secure",
        dest="port_s",
        help="Web interface port (HTTPS)",
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

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--tray",
        dest="tray",
        action="store_true",
        help="Force LedFx system tray icon",
    )

    group.add_argument(
        "--no-tray",
        dest="no_tray",
        action="store_true",
        help="Force no LedFx system tray icon",
    )

    parser.add_argument(
        "--offline",
        dest="offline_mode",
        action="store_true",
        help="Disable sentry crash logger",
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
    pip_spec = importlib.util.find_spec("pip")
    if pip_spec is None:
        return False
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


def log_packages():
    from platform import (
        processor,
        python_build,
        python_implementation,
        python_version,
        release,
        system,
    )

    from pkg_resources import working_set

    _LOGGER.debug(f"{system()} : {release()} : {processor()}")
    _LOGGER.debug(
        f"{python_version()} : {python_build()} : {python_implementation()}"
    )
    _LOGGER.debug("Packages")
    dists = [d for d in working_set]
    dists.sort(key=lambda x: x.project_name)
    for dist in dists:
        _LOGGER.debug(f"{dist.project_name} : {dist.version}")


def main():
    """Main entry point allowing external calls"""
    args = parse_args()
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel, config_dir=args.config)
    config_helpers.load_logger()

    # Set some process priority optimisations
    if have_psutil:
        p = psutil.Process(os.getpid())

        if psutil.WINDOWS:
            try:
                p.nice(psutil.HIGH_PRIORITY_CLASS)
            except psutil.Error:
                _LOGGER.info(
                    "Unable to set priority, please run as Administrator if you are experiencing frame rate issues"
                )
            # p.ionice(psutil.IOPRIO_HIGH)
        elif psutil.LINUX:
            try:
                p.nice(15)
                p.ionice(psutil.IOPRIO_CLASS_RT, value=7)
            except psutil.Error:
                _LOGGER.info(
                    "Unable to set priority, please run as root or sudo if you are experiencing frame rate issues",
                )
        else:
            p.nice(15)

    if (
        not (currently_frozen() or installed_via_pip())
        and args.offline_mode is False
    ):
        import ledfx.sentry_config  # noqa: F401

    if args.sentry_test:
        """This will crash LedFx and submit a Sentry error if Sentry is configured"""
        _LOGGER.warning("Steering LedFx into a brick wall")
        div_by_zero = 1 / 0

    if (args.tray or currently_frozen()) and not args.no_tray:
        # If pystray is imported on a device that can't display it, it explodes. Catch it
        try:
            import pystray
        except Exception as Error:
            msg = f"Error: Unable to virtual tray icon. Shutting down. Error: {Error}"
            _LOGGER.critical(msg)
            raise Exception(msg)
            sys.exit(0)

        from PIL import Image

        icon_location = get_icon_path("tray.png")

        icon = pystray.Icon(
            "LedFx", icon=Image.open(icon_location), title="LedFx"
        )
    else:
        icon = None

    if _LOGGER.isEnabledFor(logging.DEBUG):
        log_packages()

    if icon:
        icon.run(setup=entry_point)
    else:
        entry_point()


def entry_point(icon=None):
    # have to re-parse args here :/ no way to pass them through pysicon's setup
    args = parse_args()

    if icon:
        icon.visible = True

    exit_code = 4
    while exit_code == 4:
        _LOGGER.info("LedFx Core is initializing")

        ledfx = LedFxCore(
            config_dir=args.config,
            host=args.host,
            port=args.port,
            port_s=args.port_s,
            icon=icon,
        )

        exit_code = ledfx.start(open_ui=args.open_ui)

    if icon:
        icon.stop()


if __name__ == "__main__":
    sys.exit(main())
