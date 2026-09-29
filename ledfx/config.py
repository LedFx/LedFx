import datetime
import ipaddress
import logging
import os
import sys
import uuid

import voluptuous as vol

from ledfx.consts import CONFIGURATION_VERSION

_LOGGER = logging.getLogger(__name__)

CONFIG_DIRECTORY = ".ledfx"
CONFIG_FILE_NAME = "config.json"

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

# Some core config keys that don't need a restart to take effect - list them here to use elsewhere
CORE_CONFIG_KEYS_NO_RESTART = [
    "global_brightness",
    "create_segments",
    "scan_on_startup",
    "user_presets",
    "visualisation_maxlen",
    "visualisation_fps",
    "flush_on_deactivate",
    "ui_brightness_boost",
    "startup_scene_id",
    "startup_playlist_id",
    "lifx_broadcast_address",
    "lifx_discovery_timeout",
    "sendspin_always_on",
    "now_playing",
    "allowed_origins",
    "allowed_hosts",
    "allow_null_origin",
]
# Collection of keys that are used for visualisation configuration - used to check if we need to restart the visualisation event listeners
VISUALISATION_CONFIG_KEYS = [
    "visualisation_fps",
    "visualisation_maxlen",
]

UI_ONLY_KEYS_IGNORED_FOR_CONFIG_COMPARISON = [
    "advanced",
    "diag",
    "gradient_name",  # UI field that gets expanded to gradient value
]


# Transmission types for pixel visualisation on frontend
class Transmission:
    BASE64_COMPRESSED = "compressed"
    UNCOMPRESSED = "uncompressed"

    @staticmethod
    def get_list():
        transmission_dict = vars(Transmission)
        t_list = []
        for attribute in transmission_dict:
            if attribute[:2] != "__" and attribute != "get_list":
                t_list.append(getattr(Transmission, attribute))
        return t_list


def validate_ipv4_address(value):
    """Validate that value is a valid IPv4 address (including broadcast).

    Args:
        value: The value to validate.

    Returns:
        str: The validated IPv4 address string.

    Raises:
        vol.Invalid: If the value is not a valid IPv4 address.
    """
    try:
        addr = ipaddress.IPv4Address(value)
        return str(addr)
    except ipaddress.AddressValueError:
        raise vol.Invalid(f"Invalid IPv4 address: {value}")


CORE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("host", default="0.0.0.0"): str,
        vol.Optional("hosts", default=[]): list,
        vol.Optional("port", default=8888): int,
        vol.Optional("port_s", default=8443): int,
        vol.Optional("dev_mode", default=False): bool,
        vol.Optional("devices", default=[]): list,
        vol.Optional("virtuals", default=[]): list,
        vol.Optional("audio", default={}): dict,
        vol.Optional("melbank_collection", default=[]): list,
        vol.Optional("melbanks", default={}): dict,
        vol.Optional("ledfx_presets", default={}): dict,
        vol.Optional("user_presets", default={}): dict,
        vol.Optional("scenes", default={}): dict,
        vol.Optional("playlists", default={}): dict,
        vol.Optional("integrations", default=[]): list,
        vol.Optional("transmission_mode", default="compressed"): vol.In(
            Transmission.get_list()
        ),
        vol.Optional("visualisation_fps", default=30): vol.All(int, vol.Range(1, 60)),
        vol.Optional("visualisation_maxlen", default=81): vol.All(
            int, vol.Range(5, 65536)
        ),
        vol.Optional(
            "global_transitions",
            description="Changes to any virtual's transitions apply to all other virtuals",
            default=True,
        ): bool,
        vol.Optional("user_colors", default={}): dict,
        vol.Optional("user_gradients", default={}): dict,
        vol.Optional("scan_on_startup", default=False): bool,
        vol.Optional("create_segments", default=False): bool,
        vol.Optional("flush_on_deactivate", default=False): bool,
        vol.Optional("wled_preferences", default={}): dict,
        vol.Optional("configuration_version", default=CONFIGURATION_VERSION): str,
        vol.Optional("global_brightness", default=1.0): vol.All(
            vol.Coerce(float), vol.Range(0, 1.0)
        ),
        vol.Optional("ui_brightness_boost", default=0.0): vol.All(
            vol.Coerce(float), vol.Range(0, 1.0)
        ),
        vol.Optional("startup_scene_id", default=""): str,
        vol.Optional("startup_playlist_id", default=""): str,
        vol.Optional(
            "lifx_broadcast_address", default="255.255.255.255"
        ): validate_ipv4_address,
        vol.Optional("lifx_discovery_timeout", default=30): vol.All(
            int, vol.Range(min=1, max=120)
        ),
        vol.Optional("instance_id", default=""): str,
        vol.Optional("sendspin_servers", default={}): dict,
        vol.Optional("sendspin_always_on", default=True): bool,
        vol.Optional("now_playing", default={}): dict,
        vol.Optional(
            "allowed_origins",
            default=[],
            description='Extra web origins (e.g. "https://ledfx.example.com") allowed to use the API from a browser. "*" allows every origin',
        ): [str],
        vol.Optional(
            "allowed_hosts",
            default=[],
            description='Extra host names (e.g. "ledfx.example.com") that browsers may use to reach LedFx. "*" allows every name',
        ): [str],
        vol.Optional(
            "allow_null_origin",
            default=False,
            description='Accept browser requests whose Origin is "null"',
        ): bool,
    },
    extra=vol.ALLOW_EXTRA,
)


def ensure_instance_id(config):
    """
    Ensure the config has a persistent LedFx instance UUID.

    Generates a random UUID if ``instance_id`` is missing or empty and
    stores it back in *config* so it is saved on the next
    :func:`save_config` call.  The value is stable across restarts and
    uniquely identifies this LedFx installation.
    """
    if not config.get("instance_id"):
        config["instance_id"] = str(uuid.uuid4())


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


def get_default_config_path() -> str:
    """
    Get the default fully qualified configuration file path.

    Returns:
        str: The fully qualified configuration file path.
    """
    return os.path.join(get_default_config_directory(), CONFIG_FILE_NAME)


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


def get_ssl_certs(config_dir) -> tuple:
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


def create_backup(config_dir: str, backup_reason: str) -> None:
    """Move config.json aside (used by --clear-config so a fresh one is created)."""
    from ledfx.configuration.store import backup_config_file

    backup_config_file(config_dir, backup_reason, move=True)


def save_config(config: dict, config_dir: str) -> None:
    """Persist config.

    Routes to the live ConfigStore (debounced, atomic) when one is registered for
    config_dir; otherwise writes atomically now (scripts and tests).
    """
    from ledfx.configuration.store import ConfigStore

    store = ConfigStore.registered(config_dir)
    if store is not None:
        if config is not store.data:
            _LOGGER.debug("save_config called with a dict that is not the live config")
        store.request_save()
        return
    ensure_config_directory(config_dir)
    ConfigStore(config_dir, config, CORE_CONFIG_SCHEMA).save_now()


def filter_config_for_comparison(config):
    """Filter out UI-only keys from effect configuration for comparison.

    Removes keys like 'advanced' and 'diag' that are UI-only and don't
    affect the actual effect behavior.

    Args:
        config (dict): The configuration dictionary to filter.

    Returns:
        dict: A new dictionary with UI-only keys removed.
    """
    if not isinstance(config, dict):
        return {}
    return {
        k: v
        for k, v in config.items()
        if k not in UI_ONLY_KEYS_IGNORED_FOR_CONFIG_COMPARISON
    }


def configs_match(config1, config2):
    """Compare two effect configurations, ignoring UI-only keys.

    Args:
        config1 (dict): First configuration to compare.
        config2 (dict): Second configuration to compare.

    Returns:
        bool: True if configurations match (ignoring UI-only keys), False otherwise.
    """
    return filter_config_for_comparison(config1) == filter_config_for_comparison(
        config2
    )


def find_matching_preset(
    ledfx_presets, user_presets, ledfx_effects, effect_type, effect_config
):
    """Find a matching preset for the given effect configuration.

    Searches through both system (ledfx) and user presets to find a preset
    that matches the given effect configuration. Ignores UI-only keys like
    'advanced' and 'diag' during comparison.

    Args:
        ledfx_presets (dict): The system presets configuration.
        user_presets (dict): The user presets configuration.
        ledfx_effects (dict): The effects registry.
        effect_type (str): The type of effect to match.
        effect_config (dict): The effect configuration to match against presets.

    Returns:
        tuple: (preset_id, category) if a match is found, otherwise (None, None).
            category will be either 'ledfx_presets' or 'user_presets'.
    """
    from ledfx.utils import generate_defaults

    if not isinstance(effect_config, dict):
        return None, None

    # Check ledfx_presets first
    ledfx_defaults = generate_defaults(ledfx_presets, ledfx_effects, effect_type)
    for preset_id, preset_data in ledfx_defaults.items():
        preset_config = preset_data.get("config", {})
        if configs_match(preset_config, effect_config):
            return preset_id, "ledfx_presets"

    # Check user_presets
    if effect_type in user_presets:
        for preset_id, preset_data in user_presets[effect_type].items():
            preset_config = preset_data.get("config", {})
            if configs_match(preset_config, effect_config):
                return preset_id, "user_presets"

    return None, None


def remove_virtuals_active_effects(config: dict) -> None:
    """
    Removes active effects from virtuals
    All effects configs will remain in the virtuals, but the active effect will be removed
    This allows for recovery from scenarios where an effect configuration is poisened
    The user retains all their other settings.
    The poisoned effect config will still be present in the virtuals effects list and will crash the app if it is selected
    This may be addreessed by future fixes in the application or manual removal
    of the effect from virtuals effects list once it is identified
    This can only be identified via selective activation of effects to the point of crash
    """

    for virtual in config["virtuals"]:
        virtual.pop("effect", None)
