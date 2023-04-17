import datetime
import json
import logging
import os
import shutil
import sys

import voluptuous as vol
from pkg_resources import parse_version

from ledfx.consts import CONFIGURATION_VERSION

CONFIG_DIRECTORY = ".ledfx"
CONFIG_FILE_NAME = "config.json"
PRESETS_FILE_NAME = "presets.json"

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


# adds the {setting: ..., user: ...} thing to the defaults dict
def parse_default_wled_setting(setting):
    key, value = setting
    return (key, {"setting": value, "user_enabled": False})


# creates validators for the different wled preferences
def wled_validator_generator(data_type):
    return vol.Schema(
        {
            vol.Optional("setting"): data_type,
            vol.Optional("user_enabled"): bool,
        }
    )


# creates the vol.optionals using the above two functions
def wled_optional_generator(setting):
    key, default = setting
    return (
        vol.Optional(key, default=default),
        wled_validator_generator(type(default["setting"])),
    )


# generate the default settings with the setting, user enabled dict thing
_default_wled_settings = dict(
    map(parse_default_wled_setting, _default_wled_settings.items())
)

# generate the config schema to validate changes
WLED_CONFIG_SCHEMA = vol.Schema(
    dict(map(wled_optional_generator, _default_wled_settings.items()))
)

CORE_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("host", default="0.0.0.0"): str,
        vol.Optional("port", default=8888): int,
        vol.Optional("port_s", default=8443): int,
        vol.Optional("dev_mode", default=False): bool,
        vol.Optional("devices", default=[]): list,
        vol.Optional("virtuals", default=[]): list,
        vol.Optional("audio", default={}): dict,
        vol.Optional("melbanks", default={}): dict,
        vol.Optional("ledfx_presets", default={}): dict,
        vol.Optional("user_presets", default={}): dict,
        vol.Optional("scenes", default={}): dict,
        vol.Optional("integrations", default=[]): list,
        vol.Optional("visualisation_fps", default=30): vol.All(
            int, vol.Range(1, 60)
        ),
        vol.Optional("visualisation_maxlen", default=81): vol.All(
            int, vol.Range(5, 300)
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
        vol.Optional("wled_preferences", default={}): dict,
        vol.Optional(
            "configuration_version", default=CONFIGURATION_VERSION
        ): str,
        vol.Optional("global_brightness", default=1.0): vol.All(
            vol.Coerce(float), vol.Range(0, 1.0)
        ),
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
        return None  # No Valid Configs, return None to build another one
    return json_path  # Return the JSON file if we find one.


def get_preset_file(config_dir: str) -> str:
    """Finds a supported preset file in the provided directory"""

    json_path = os.path.join(config_dir, PRESETS_FILE_NAME)
    if os.path.isfile(json_path) is False:  # Can't find a JSON file
        return None  # No Valid Configs, return None to build another one
    return json_path  # Return the JSON file if we find one.


def get_profile_dump_location(config_dir) -> str:
    date_time = datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S")
    return os.path.join(config_dir, f"LedFx_{date_time}.profile")


def get_log_file_location(config_dir):
    log_file_path = os.path.abspath(os.path.join(config_dir, "LedFx.log"))
    return log_file_path


def get_ssl_certs(config_dir) -> tuple:
    """Finds ssl certificate files in config dir"""
    ssl_dir = os.path.join(config_dir, "ssl")

    if not os.path.exists(ssl_dir):
        return None

    key_path = os.path.join(ssl_dir, PRIVATE_KEY_FILE)
    chain_path = os.path.join(ssl_dir, CHAIN_KEY_FILE)

    if os.path.isfile(key_path) and os.path.isfile(key_path):
        return (chain_path, key_path)
    return None


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

    except OSError:
        print(f"Unable to create default configuration file {config_path}.")

        return None


def ensure_config_file(config_dir: str) -> str:
    """Checks if a config file exists, and otherwise creates one"""

    ensure_config_directory(config_dir)
    config_path = get_config_file(config_dir)
    if config_path is None:
        config_path = create_default_config(config_dir)

    return config_path


def check_preset_file(config_dir: str) -> str:
    ensure_config_directory(config_dir)
    presets_path = get_preset_file(config_dir)
    if presets_path is None:
        return None

    return presets_path


def ensure_config_directory(config_dir: str) -> None:
    """Validate that the config directory is valid."""

    # If an explicit path is provided simply check if it exist and failfast
    # if it doesn't. Otherwise, if we have the default directory attempt to
    # create the file
    if not os.path.isdir(config_dir):
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
    print(
        f"Loading configuration file: {os.path.join(os.path.abspath(config_dir), CONFIG_FILE_NAME)}"
    )
    try:
        with open(config_file, encoding="utf-8") as file:
            config_json = json.load(file)
            try:
                # If there's no config version in the config, it's pre-1.0.0 and won't work
                # Probably scope to iterate through it and create a virtual for every device, but that's beyond me
                _LOGGER.info(
                    f"LedFx Configuration Version: {config_json['configuration_version']}"
                )
                assert parse_version(
                    config_json["configuration_version"]
                ) == parse_version(CONFIGURATION_VERSION)
                return CORE_CONFIG_SCHEMA(config_json)
            except (KeyError, AssertionError):
                create_backup(config_dir, config_file, "VERSION")
                _LOGGER.warning(
                    f"LedFx config version: {CONFIGURATION_VERSION}, your config version: {config_json.get('configuration_version', 'UNDEFINED (old!)')}"
                )
                try:
                    config = migrate_config(config_json)
                    save_config(config, config_dir)
                except Exception as e:
                    _LOGGER.exception(
                        f"Failed to migrate your config to the new standard :( Your old config is backed up safely. Please let a developer know what happened: {e}"
                    )
                    config = {}
                return CORE_CONFIG_SCHEMA(config)
    except json.JSONDecodeError:
        create_backup(config_dir, config_file, "DECODE")
        return CORE_CONFIG_SCHEMA({})
    except OSError:
        create_backup(config_dir, config_file, "OSERROR")
        return CORE_CONFIG_SCHEMA({})


def migrate_config(old_config):
    """
    attempts to update an old config to a working state
    """
    _LOGGER.warning("Attempting to migrate old config to new version...")

    # most invalid keys were from invalid frequency ranges.
    # this replacement dict should fix that
    replacement_frequency_ranges = {
        "Ultra Low (1-20Hz)": "Beat",
        "Sub Bass (20-60Hz)": "Lows (beat+bass)",
        "Bass (60-250Hz)": "Lows (beat+bass)",
        "Low Midrange (250-500Hz)": "Lows (beat+bass)",
        "Midrange (500Hz-2kHz)": "Mids",
        "Upper Midrange (2Khz-4kHz)": "Mids",
        "High Midrange (4kHz-6kHz)": "High",
        "High Frequency (6kHz-24kHz)": "High",
    }

    class DummyLedfx:
        def dev_enabled(_):
            return False

    import copy

    import voluptuous as vol

    from ledfx.effects import Effects

    effects = Effects(DummyLedfx()).classes()

    # initialise some things that will help us match up old effect info to new effect info
    def get_matching_effect_id(dirty_effect_id):
        def clean_effect_id(effect_id):
            return effect_id.lower().replace("(reactive)", "").replace("_", "")

        candidate_effect_id = clean_effect_id(dirty_effect_id)
        for effect_id in effects:
            if clean_effect_id(effect_id) == candidate_effect_id:
                return effect_id
        else:
            return None

    def sanitise_effect_config(effect_type, old_config):
        # checks each config key against the current schema, discarding any values that dont match
        schema = effects[effect_type].schema().schema
        new_config = {}
        for old_key in old_config:
            new_key = old_key.replace("colour", "color")
            if new_key in schema:
                try:
                    if (
                        old_key == "frequency_range"
                        and old_config.get(old_key)
                        not in replacement_frequency_ranges.values()
                    ):
                        old_config[old_key] = replacement_frequency_ranges[
                            old_config.get(old_key)
                        ]
                    schema[new_key](old_config[old_key])
                    new_config[new_key] = old_config[old_key]
                except (vol.MultipleInvalid, vol.InInvalid, Exception):
                    _LOGGER.warning(
                        f"Preset for {effect_type} with config item {old_key} : {old_config[old_key]} is invalid. Discarding."
                    )
                    continue
            else:
                _LOGGER.warning(
                    f"Preset for {effect_type} cannot match config item {old_key}. Discarding item from preset."
                )
                continue
        return new_config

    new_config = copy.deepcopy(old_config)

    # if not using new config "audio_device", delete audio config
    if not old_config.get("audio", {}).get("audio_device", None):
        new_config.pop("audio", None)

    # remove old transition things
    new_config.pop("crossfade", None)
    new_config.pop("fade", None)

    # update devices
    new_config["devices"] = []
    for device in old_config.get("devices", ()):
        if device["type"].lower() == "fxmatrix":
            _LOGGER.warning(
                "FXMatrix devices are no longer supported. Add it as plain UDP or WLED."
            )
            continue
        device.pop("effect", None)
        new_config["devices"].append(device)

    # if displays/virtuals are present, remove their effects and rename to virtuals
    # else if no virtuals saved, create virtuals for all the devices
    virtuals = new_config.pop("displays", None) or new_config.pop(
        "virtuals", None
    )
    if virtuals:
        for virtual in virtuals:
            effect = virtual.get("effect", None)
            if effect:
                effect_id, effect_config = (
                    effect.get("type", None),
                    effect.get("config", None),
                )
                if effect_id:
                    new_effect_id = get_matching_effect_id(effect_id)
                    if not new_effect_id:
                        _LOGGER.warning(
                            f"Could not match effect id {effect_id} to any current effects. Discarding this effect from virtual {virtual['id']}."
                        )
                        continue
                    new_effect_config = sanitise_effect_config(
                        new_effect_id, effect_config
                    )
                virtual["effect"] = {
                    "config": new_effect_config,
                    "type": new_effect_id,
                }
            virtual["auto_generated"] = virtual.get("auto_generated", False)
        new_config["virtuals"] = virtuals
    else:  # time to make some virtuals
        from ledfx.utils import generate_id

        new_config["virtuals"] = []
        for device in new_config["devices"]:
            # Generate virtual configuration for the device
            name = device["config"]["name"]
            _LOGGER.info(f"Creating a virtual for device {name}")

            virtual_config = {
                "name": name,
                # "icon_name": device_config["icon_name"],
            }
            segments = [
                [device["id"], 0, device["config"]["pixel_count"] - 1, False]
            ]

            new_config["virtuals"].append(
                {
                    "id": generate_id(name),
                    "is_device": device["id"],
                    "auto_generated": False,
                    "config": virtual_config,
                    "segments": segments,
                }
            )

    # clean up user presets. effect names have changed, we'll try to clean them up here
    user_presets = new_config.pop("custom_presets", ()) or new_config.pop(
        "user_presets", ()
    )
    new_config["user_presets"] = {}
    for effect_id in user_presets:
        new_effect_id = get_matching_effect_id(effect_id)
        if not new_effect_id:
            _LOGGER.warning(
                f"Could not match effect id {effect_id} to any current effects. Discarding presets for this effect."
            )
            continue
        new_config["user_presets"][new_effect_id] = {}
        for preset_id in user_presets[effect_id]:
            new_config["user_presets"][new_effect_id][preset_id] = {
                "name": user_presets[effect_id][preset_id]["name"],
                "config": sanitise_effect_config(
                    new_effect_id, user_presets[effect_id][preset_id]["config"]
                ),
            }

    # clean up scenes. if you are reading this, sorry for the confusing variable naming. i've tried my best :D
    scenes = new_config.pop("scenes", ())
    new_config["scenes"] = {}
    if scenes:
        scenes_mode = next(
            mode
            for mode in scenes[next(iter(scenes))]
            if mode in ("devices", "displays", "virtuals")
        )
    for scene_id in scenes:
        virtuals_ish = scenes[scene_id].pop(scenes_mode, ())
        new_virtuals = {}
        for virtual_ish in virtuals_ish:
            # if scenes are populated by devices, then we should by now have virtuals made for each device.
            # we need to find the corresponding virtual for the device
            if scenes_mode == "devices":
                corresponding_virtual = next(
                    (
                        real_virtual["id"]
                        for real_virtual in new_config["virtuals"]
                        if real_virtual.get("is_device", None) == virtual_ish
                    ),
                    None,
                )
                if not corresponding_virtual:
                    _LOGGER.warning(
                        f"Could not match device id {device} to any virtuals. Discarding this device from scene {scene_id}."
                    )
                    continue
                actual_virtual = corresponding_virtual
            else:
                # if it's displays or virtuals, these should already exist in the user's config
                actual_virtual = virtual_ish
            # with the virtuals_ish now sanitised to an actual virtual, we need to clean up the effect type and config
            effect_id, effect_config = (
                virtuals_ish[virtual_ish].get("type", None),
                virtuals_ish[virtual_ish].get("config", None),
            )
            if effect_id and effect_config:
                new_effect_id = get_matching_effect_id(effect_id)
                if not new_effect_id:
                    _LOGGER.warning(
                        f"Could not match effect id {effect_id} to any current effects. Discarding this effect from scene {scene_id}."
                    )
                    continue
                new_effect_config = sanitise_effect_config(
                    new_effect_id, effect_config
                )
                new_virtuals[actual_virtual] = {
                    "config": new_effect_config,
                    "type": new_effect_id,
                }
            else:
                new_virtuals[actual_virtual] = {}

        new_config["scenes"][scene_id] = {
            "virtuals": new_virtuals,
            "name": scenes[scene_id]["name"],
        }

    _LOGGER.warning("Finished migrating config.")
    return new_config


def create_backup(config_dir, config_file, errortype):
    """This function creates a backup of the current configuration file - it uses the format dd-mm-yyyy_hh-mm-ss for the backup file.

    Args:
        config_dir (path): The path to the current configuration directory
        config_file (path): The path to the current configuration file
        errortype (string): The type of error we encounter to allow for better logging
    """

    date = datetime.datetime.now().strftime("%d-%m-%y_%H-%M-%S")
    backup_location = os.path.join(config_dir, f"config_backup_{date}.json")
    try:
        os.rename(config_file, backup_location)
    except OSError:
        shutil.copy2(config_file, backup_location)

    if errortype == "DECODE":
        _LOGGER.warning(
            "Error loading configuration. Backup created, empty configuration used."
        )

    if errortype == "VERSION":
        _LOGGER.warning("Incompatible Configuration Detected. Backup Created.")

    if errortype == "OSERROR":
        _LOGGER.warning(
            "Unable to Open Configuration. Backup Created, empty configuration used."
        )

    _LOGGER.warning(f"Backup Located at: {backup_location}")


def save_config(config: dict, config_dir: str) -> None:
    """Saves the configuration to the provided directory"""

    config_file = ensure_config_file(config_dir)
    _LOGGER.info(("Saving configuration file to {}").format(config_dir))
    config["configuration_version"] = CONFIGURATION_VERSION
    config_view = dict(config)
    unneeded_keys = ["ledfx_presets"]
    for key in [key for key in config_view if key in unneeded_keys]:
        del config_view[key]

    with open(config_file, "w", encoding="utf-8") as file:
        json.dump(
            config_view, file, ensure_ascii=False, sort_keys=True, indent=4
        )


def save_presets(config: dict, config_dir: str) -> None:
    """Saves the configuration to the provided directory"""

    presets_file = check_preset_file(config_dir)
    _LOGGER.info(("Saving user presets to {}").format(config_dir))

    config_view = dict(config)
    for key in [key for key in config_view if key != "user_presets"]:
        del config_view[key]

    with open(presets_file, "w", encoding="utf-8") as file:
        json.dump(
            config_view, file, ensure_ascii=False, sort_keys=True, indent=4
        )
