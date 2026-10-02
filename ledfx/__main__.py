"""
Entry point for LedFx.

WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING
WARNING                                                         WARNING
WARNING  ⚠️⚠️⚠️ DO NOT USE SOUNDDEVICE WITHIN MAIN.PY ⚠️⚠️⚠️ WARNING
WARNING                                                         WARNING
WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING

"""

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from ledfx.sentry_config import setup_sentry

try:
    import psutil

    have_psutil = True
except ImportError:
    have_psutil = False

import ledfx.configuration.paths as config_helpers
from ledfx.consts import PROJECT_VERSION
from ledfx.core import LedFxCore
from ledfx.utils import (
    check_optional_dependencies,
    currently_frozen,
    get_icon_path,
    log_packages,
    read_ledfx_dotenv,
)

_LOGGER = logging.getLogger(__name__)


def setup_logging(loglevel, config_dir):
    console_loglevel = loglevel or logging.WARNING
    console_logformat = "[%(levelname)-8s] %(name)-30s : %(message)s"

    file_loglevel = loglevel or logging.INFO
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
    console_formatter = logging.Formatter(console_logformat)  # a simple console format
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
    logging.getLogger("lifx").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    global _LOGGER
    _LOGGER = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="A Networked LED Effect Controller")

    parser.add_argument(
        "--version",
        action="version",
        version=f"LedFx {PROJECT_VERSION}",
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
        help="Disable crash logger and auto update checks",
    )
    parser.add_argument(
        "--sentry-crash-test",
        dest="sentry_test",
        action="store_true",
        help="This crashes LedFx to test the sentry crash logger",
    )
    parser.add_argument(
        "--ci-smoke-test",
        dest="ci_smoke_test",
        action="store_true",
        help="Launch LedFx and then exit after 5 seconds to sanity check the install",
    )

    parser.add_argument(
        "--dump-schemas",
        dest="dump_schemas",
        metavar="PATH",
        help="Write every config JSON Schema (as served by /api/schemas) to PATH and exit",
        default=None,
    )

    parser.add_argument(
        "--dump-openapi",
        dest="dump_openapi",
        metavar="PATH",
        help="Write the /api/v2 OpenAPI document (as served by /api/v2/openapi.json) to PATH and exit",
        default=None,
    )

    parser.add_argument(
        "--clear-config",
        dest="clear_config",
        action="store_true",
        help="Launch LedFx, backup the config, clear the config, and continue with a clean startup",
    )

    parser.add_argument(
        "--clear-effects",
        dest="clear_effects",
        action="store_true",
        help="Launch LedFx, load the config, clear all active effects on all virtuals. Effect configurations are persisted, just turned off",
    )

    parser.add_argument(
        "--pause-all",
        dest="pause_all",
        action="store_true",
        help="Start Ledfx with all virtuals paused",
    )

    return parser.parse_args()


def main():
    """
    Main entry point allowing external calls
    """

    args = parse_args()
    if args.dump_schemas:
        import json

        from ledfx.api.schemas import build_schemas

        with open(args.dump_schemas, "w", encoding="utf-8") as file:
            json.dump(build_schemas(None), file, indent=2)
        return 0
    if args.dump_openapi:
        import json
        from pathlib import Path

        from ledfx.api.v2.core.registry import build_standalone_spec

        # Build first, then replace atomically: a failure never truncates the
        # committed spec. newline="\n": byte-identical on every OS.
        out = Path(args.dump_openapi)
        tmp = out.with_name(out.name + ".tmp")
        try:
            text = json.dumps(build_standalone_spec(), indent=2, sort_keys=True)
            tmp.write_text(text + "\n", encoding="utf-8", newline="\n")
            tmp.replace(out)
        finally:
            tmp.unlink(missing_ok=True)
        return 0
    config_helpers.ensure_config_directory(args.config)
    setup_logging(args.loglevel, config_dir=args.config)
    config_helpers.load_logger()
    read_ledfx_dotenv()
    if _LOGGER.isEnabledFor(logging.DEBUG):
        log_packages()
    check_optional_dependencies()
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
                    "Unable to set priority, please run as root or use sudo if you are experiencing frame rate issues",
                )
        else:
            p.nice(15)

    if args.offline_mode is False:
        setup_sentry()

    if args.sentry_test:
        _LOGGER.warning("Steering LedFx into a brick wall.")
        _ = 1 / 0

    if (args.tray or currently_frozen()) and not args.no_tray:
        # If pystray is imported on a device that can't display it, it explodes. Catch it
        try:
            import pystray
        except Exception as Error:  # noqa: BLE001
            msg = f"Unable to create tray icon. Error: {Error}. Try launching LedFx via --no-tray option."
            _LOGGER.critical(msg)
            # Exit with code 3 to indicate that there was an error creating the tray icon.
            sys.exit(3)

        from PIL import Image

        icon_class = pystray.Icon
        if sys.platform == "darwin":
            from ledfx.mac_tray import Icon as icon_class

        icon_location = get_icon_path("tray.png")

        icon = icon_class("LedFx", icon=Image.open(icon_location), title="LedFx")
    else:
        icon = None

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
            ci_testing=args.ci_smoke_test,
            clear_config=args.clear_config,
            clear_effects=args.clear_effects,
            offline_mode=args.offline_mode,
        )

        exit_code = ledfx.start(open_ui=args.open_ui, pause_all=args.pause_all)

    if icon:
        icon.stop()


if __name__ == "__main__":
    sys.exit(main())
