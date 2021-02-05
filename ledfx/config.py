import datetime
import json
import logging
import os
import sys

import voluptuous as vol
import yaml

CONFIG_DIRECTORY = ".ledfx"
CONFIG_FILE_NAME = "config.json"
OLD_CONFIG_FILE_NAME = "config.yaml"
DEFAULT_PRESETS_FILE_NAME = "default_presets.json"

CORE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("host", default="0.0.0.0"): str,
        vol.Optional("port", default=8888): int,
        vol.Optional("dev_mode", default=False): bool,
        vol.Optional("crossfade", default=1.0): float,
        vol.Optional("devices", default=[]): list,
        vol.Optional("default_presets", default={}): dict,
        vol.Optional("custom_presets", default={}): dict,
        vol.Optional("scenes", default={}): dict,
        vol.Optional("integrations", default=[]): list,
        vol.Optional("fade", default=1.0): float,
        vol.Optional("virtuals", default=[]): list,
    },
    extra=vol.ALLOW_EXTRA,
)


def load_logger():
    global _LOGGER
    _LOGGER = logging.getLogger(__name__)


def get_default_config_directory() -> str:
    """Get the default configuration directory"""

    base_dir = (
        os.getenv("APPDATA") if os.name == "nt" else os.path.expanduser("~")
    )
    return os.path.join(base_dir, CONFIG_DIRECTORY)


def get_config_file(config_dir: str) -> str:
    """Finds a supported configuration file in the provided directory"""

    json_path = os.path.join(config_dir, CONFIG_FILE_NAME)
    if os.path.isfile(json_path) is False:  # Can't find a JSON file
        yaml_path = os.path.join(
            config_dir, OLD_CONFIG_FILE_NAME
        )  # Look for an old YAML file
        if os.path.isfile(yaml_path):  # Found one!
            return yaml_path  # Return the YAML File
        else:
            return None  # No Valid Configs, return None to build another one
    return json_path  # Return the JSON file if we find one.


def get_log_file_location():
    config_dir = get_default_config_directory()
    log_file_path = os.path.abspath(os.path.join(config_dir, "LedFx.log"))
    return log_file_path


def create_default_config(config_dir: str) -> str:
    """Creates a default configuration in the provided directory"""

    config_path = os.path.join(config_dir, CONFIG_FILE_NAME)
    try:
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(
                CORE_CONFIG_SCHEMA({}),
                file,
                ensure_ascii=False,
                sort_keys=True,
                indent=4,
            )
        return config_path

    except IOError:
        print(f"Unable to create default configuration file {config_path}.")

        return None


def ensure_config_file(config_dir: str) -> str:
    """Checks if a config file exists, and otherwise creates one"""

    ensure_config_directory(config_dir)
    config_path = get_config_file(config_dir)
    if config_path is None:
        config_path = create_default_config(config_dir)

    return config_path


def ensure_config_directory(config_dir: str) -> None:
    """Validate that the config directory is valid."""

    # If an explicit path is provided simply check if it exist and failfast
    # if it doesn't. Otherwise, if we have the default directory attempt to
    # create the file
    if not os.path.isdir(config_dir):
        if config_dir != get_default_config_directory():
            print(
                ("Error: Invalid configuration directory {}").format(
                    config_dir
                )
            )
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError:
            print(
                ("Error: Unable to create configuration directory {}").format(
                    config_dir
                )
            )
            sys.exit(1)


def load_config(config_dir: str) -> dict:
    """Validates and loads the configuration file in the provided directory"""

    config_file = ensure_config_file(config_dir)
    print(("Loading configuration file from {}").format(config_dir))

    if config_file.endswith("yaml"):
        migrate_config(config_dir, config_file)
        config_file = os.path.join(config_dir, CONFIG_FILE_NAME)
    try:

        with open(config_file, encoding="utf-8") as file:
            config_json = json.load(file)
            return CORE_CONFIG_SCHEMA(config_json)
    except json.JSONDecodeError:
        date = datetime.date.today()
        backup_location = os.path.join(
            config_dir, f"config.json.backup.{date}"
        )
        os.rename(config_file, backup_location)
        _LOGGER.warning(
            "Error loading configuration. Backup created, empty configuration used."
        )
        _LOGGER.warning(
            f"Please check the backup for JSON errors if required - {backup_location}"
        )
        return CORE_CONFIG_SCHEMA({})


def load_default_presets() -> dict:
    ledfx_dir = os.path.dirname(os.path.realpath(__file__))
    default_presets_path = os.path.join(ledfx_dir, DEFAULT_PRESETS_FILE_NAME)
    print("Loading default presets from {}".format(ledfx_dir))
    if not os.path.isfile(default_presets_path):
        print("Failed to load {}".format(DEFAULT_PRESETS_FILE_NAME))
    with open(default_presets_path, encoding="utf-8") as file:
        return json.load(file)


def save_config(config: dict, config_dir: str) -> None:
    """Saves the configuration to the provided directory"""

    config_file = ensure_config_file(config_dir)
    _LOGGER.info(("Saving configuration file to {}").format(config_dir))
    # prevent defaults being saved to config.yaml by creating a copy (python
    # no pass by value)
    config_view = dict(config)
    if "default_presets" in config_view.keys():
        del config_view["default_presets"]
    with open(config_file, "w", encoding="utf-8") as file:
        json.dump(
            config_view, file, ensure_ascii=False, sort_keys=True, indent=4
        )


def migrate_config(config_dir, config_file):
    """Save the old configuration file as a new JSON object and resume the loading process"""

    print("Migrating configuration file to JSON")
    with open(config_file, "rt") as file:
        config_yaml = yaml.safe_load(file)
        json_config_file = os.path.join(config_dir, CONFIG_FILE_NAME)
        with open(json_config_file, "w", encoding="utf-8") as file:
            json.dump(
                config_yaml, file, ensure_ascii=False, sort_keys=True, indent=4
            )
    try:
        old_config_location = os.path.join(
            config_dir, f"{datetime.date.today()}_config.yaml.backup"
        )
        _LOGGER.info(f"Renaming old configuration to {old_config_location}")
        os.rename(config_file, old_config_location)
    except PermissionError as DelError:
        _LOGGER.warning(
            f"Unable to rename old configuration file: {DelError}."
        )
