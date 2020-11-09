import voluptuous as vol
import logging
import yaml
import sys
import os

_LOGGER = logging.getLogger(__name__)

CONFIG_DIRECTORY = '.ledfx'
CONFIG_FILE_NAME = 'config.yaml'
DEFAULT_PRESETS_FILE_NAME = 'default_presets.yaml'

CORE_CONFIG_SCHEMA = vol.Schema({
    vol.Optional('host', default = '127.0.0.1'): str,
    vol.Optional('port', default = 8888): int,
    vol.Optional('dev_mode', default = False): bool,
    vol.Optional('max_workers', default = 10): int,
    vol.Optional('devices', default = []): list,
    vol.Optional('default_presets', default = {}): dict,
    vol.Optional('custom_presets', default = {}): dict,
    vol.Optional('scenes', default = {}): dict,
    vol.Optional('fade', default = 1.0): float
}, extra=vol.ALLOW_EXTRA)

def get_default_config_directory() -> str:
    """Get the default configuration directory"""

    base_dir = os.getenv('APPDATA') if os.name == "nt" \
        else os.path.expanduser('~')
    return os.path.join(base_dir, CONFIG_DIRECTORY)

def get_config_file(config_dir: str) -> str:
    """Finds a supported configuration fill in the provided directory"""

    config_path = os.path.join(config_dir, CONFIG_FILE_NAME)
    return config_path if os.path.isfile(config_path) else None

def create_default_config(config_dir: str) -> str:
    """Creates a default configuration in the provided directory"""

    config_path = os.path.join(config_dir, CONFIG_FILE_NAME)
    try:
        with open(config_path, 'wt') as file:
            yaml.dump(CORE_CONFIG_SCHEMA({}), file, default_flow_style=False)
        return config_path

    except IOError:
        print(('Unable to create default configuration file {}').format(config_path))
        return None

def ensure_config_file(config_dir: str) -> str:
    """Checks if a config file exsit, and otherwise creates one"""

    ensure_config_directory(config_dir)
    config_path = get_config_file(config_dir)
    if config_path is None:
        config_path = create_default_config(config_dir)

    return config_path

def ensure_config_directory(config_dir: str) -> None:
    """Validate that the config directory is valid."""

    # If an explict path is provided simply check if it exist and failfast
    # if it doesn't. Otherwise, if we have the default directory attempt to
    # create the file
    if not os.path.isdir(config_dir):
        if config_dir != get_default_config_directory():
            print(('Error: Invalid configuration directory {}').format(config_dir))
            sys.exit(1)

        try:
            os.mkdir(config_dir)
        except OSError:
            print(('Error: Unable to create configuration directory {}').format(config_dir))
            sys.exit(1)

def load_config(config_dir: str) -> dict:
    """Validates and loads the configuration file in the provided directory"""

    config_file = ensure_config_file(config_dir)
    print(('Loading configuration file from {}').format(config_dir))
    with open(config_file, 'rt') as file:
        config_yaml = yaml.safe_load(file)
        if config_yaml is None:
            config_yaml = {}
        return CORE_CONFIG_SCHEMA(config_yaml)

def load_default_presets() -> dict:
    ledfx_dir = os.path.dirname(os.path.realpath(__file__))
    default_presets_path = os.path.join(ledfx_dir, DEFAULT_PRESETS_FILE_NAME)
    print('Loading default presets from {}'.format(ledfx_dir))
    if not os.path.isfile(default_presets_path):
        print('Failed to load {}'.format(DEFAULT_PRESETS_FILE_NAME))
    with open(default_presets_path, 'rt') as file:
        return yaml.safe_load(file)

def save_config(config: dict, config_dir: str) -> None:
    """Saves the configuration to the provided directory"""

    config_file = ensure_config_file(config_dir)
    _LOGGER.info(('Saving configuration file to {}').format(config_dir))
    # prevent defaults being saved to config.yaml by creating a copy (python no pass by value)
    config_view = dict(config)
    if "default_presets" in config_view.keys():
        del config_view["default_presets"]
    with open(config_file, 'w') as file:
        yaml.dump(config_view, file, default_flow_style=False)