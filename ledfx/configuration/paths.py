"""Config directory and file locations, logging setup and core constants."""

import datetime
import logging
import os
import sys

_LOGGER = logging.getLogger(__name__)

CONFIG_DIRECTORY = ".ledfx"

PRIVATE_KEY_FILE = "privkey.pem"
CHAIN_KEY_FILE = "fullchain.pem"

_default_wled_settings = {
    "wled_preferred_mode": "UDP",
    "realtime_gamma_enabled": False,
    "force_max_brightness": False,
    "realtime_dmx_mode": "MultiRGB",
    "start_universe_setting": 1,
    "dmx_address_start": 1,
    "inactivity_timeout": 1,
}

# Collection of keys that are used for visualisation configuration - used to check if we need to restart the visualisation event listeners
VISUALISATION_CONFIG_KEYS = [
    "visualisation_fps",
    "visualisation_maxlen",
]


# Transmission types for pixel visualisation on frontend
class Transmission:
    BASE64_COMPRESSED = "compressed"
    UNCOMPRESSED = "uncompressed"


def load_logger():
    """
    Load the logger for the current module.

    This function initializes the logger for the current module using the module's name as the logger name.

    Returns:
        None
    """
    global _LOGGER
    _LOGGER = logging.getLogger(__name__)


def get_default_config_directory() -> str:
    """
    Get the default configuration directory.

    Returns:
        str: The default configuration directory path.
    """

    base_dir = os.getenv("APPDATA") if os.name == "nt" else os.path.expanduser("~")
    return os.path.join(base_dir, CONFIG_DIRECTORY)


def get_profile_dump_location(config_dir: str) -> str:
    """
    Returns the location for dumping the profile.

    Args:
        config_dir (str): The directory where the profile dump will be stored.

    Returns:
        str: The complete path for dumping the profile.
    """
    date_time = datetime.datetime.now().astimezone().strftime("%d-%m-%y_%H-%M-%S")
    return os.path.join(config_dir, f"LedFx_{date_time}.profile")


def get_log_file_location(config_dir: str) -> str:
    """
    Returns the absolute file path of the log file.

    Args:
        config_dir (str): The directory where the log file should be located.

    Returns:
        str: The absolute file path of the log file.
    """
    log_file_path = os.path.abspath(os.path.join(config_dir, "ledfx.log"))
    return log_file_path


def get_ssl_certs(config_dir: str) -> tuple[str, str] | None:
    """
    Finds ssl certificate files in the specified config directory.

    Args:
        config_dir (str): The path to the config directory.

    Returns:
        tuple: A tuple containing the paths to the chain and key files if they exist, otherwise None.
    """
    ssl_dir = os.path.join(config_dir, "ssl")

    if not os.path.exists(ssl_dir):
        return None

    key_path = os.path.join(ssl_dir, PRIVATE_KEY_FILE)
    chain_path = os.path.join(ssl_dir, CHAIN_KEY_FILE)

    if os.path.isfile(key_path) and os.path.isfile(chain_path):
        return (chain_path, key_path)
    return None


def ensure_config_directory(config_dir: str) -> None:
    """
    Validate that the config directory is valid.

    Args:
        config_dir (str): The path to the config directory.

    Raises:
        OSError: If unable to create the configuration directory.

    """
    # If an explicit path is provided simply check if it exist and failfast
    # if it doesn't. Otherwise, if we have the default directory attempt to
    # create the file
    if not os.path.isdir(config_dir):
        try:
            os.mkdir(config_dir)
        except OSError:
            _LOGGER.critical(
                "Unable to create configuration directory at %s. Shutting down.",
                config_dir,
            )
            # Exit with code 1 to indicate that there was an error creating the configuration directory.
            sys.exit(1)
