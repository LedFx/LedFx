"""schema_version 0 -> 1: port of the pre-overhaul migrate_config()."""

import copy
import logging

from packaging.version import InvalidVersion
from packaging.version import parse as parse_version

from ledfx.configuration.jsonshape import as_dict as _obj
from ledfx.configuration.jsonshape import as_list as _items
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)

# Effect ids that existed when this step was frozen (2026-09-29). Legacy files
# can only reference effects that existed then; never update this set.
LEGACY_EFFECT_IDS = frozenset(
    {
        "bands", "bands_matrix", "bar", "blade_power_plus", "bleep", "blender",
        "block_reflections", "blocks", "clone", "concentric", "crawler",
        "digitalrain2d", "energy", "energy2", "equalizer", "equalizer2d", "fade",
        "filter", "fire", "flame2d", "frontend", "game_of_life", "gifplayer",
        "glitch", "gradient", "hierarchy", "imagespin", "keybeat2d", "lava_lamp",
        "magnitude", "marching", "melt", "melt_and_sparkle", "metro", "multiBar",
        "noise2d", "number", "pitchSpectrum", "pixels", "plasma2d", "plasmawled",
        "power", "radial", "rain", "rainbow", "random_flash", "real_strobe",
        "scan", "scan_and_flare", "scan_multi", "scroll", "scroll_plus",
        "singleColor", "smoke2d", "soap2d", "spectrum", "spotlight", "strobe",
        "texter2d", "vumeter", "water", "waterfall2d", "wavelength",
    }
)  # fmt: skip

FREQUENCY_RANGE_REMAP = {
    "Ultra Low (1-20Hz)": "Beat",
    "Sub Bass (20-60Hz)": "Lows (beat+bass)",
    "Bass (60-250Hz)": "Lows (beat+bass)",
    "Low Midrange (250-500Hz)": "Lows (beat+bass)",
    "Midrange (500Hz-2kHz)": "Mids",
    "Upper Midrange (2Khz-4kHz)": "Mids",
    "High Midrange (4kHz-6kHz)": "High",
    "High Frequency (6kHz-24kHz)": "High",
}

RENAMED_KEYS = {
    "flip horizontal": "flip_horizontal",
    "flip vertical": "flip_vertical",
    "peak percent": "peak_percent",
    "peak decay": "peak_decay",
    "peak marks": "peak_marks",
    "max vs mean": "max_vs_mean",
    "spin multiplier": "spin_multiplier",
    "spin decay": "spin_decay",
    "GIF FPS": "gif_fps",
    "Min Size": "min_size",
    "pp skip": "ping_pong_skip",
    "stretch hor": "stretch_horizontal",
    "stretch ver": "stretch_vertical",
    "v_stretch": "stretch_vertical",
    "center hor": "center_horizontal",
    "center ver": "center_vertical",
    "gif_path": "image_location",
    "gif at": "image_location",
    "beat frames": "beat_frames",
    "skip frames": "skip_frames",
    "force aspect": "keep_aspect_ratio",
    "force fit": "force_fit",
    "ping pong": "ping_pong",
    "half beat": "half_beat",
    "v density": "density_vertical",
    "size x": "size_multiplication",
    "speed x": "speed_multiplication",
    "Alpha": "alpha_options",
    "Diagnostic": "diag",
    "RGB Mix": "rgb_mix",
    "diag2": "deep_diag",
}

ARTNET_OUTPUT_MODES = {
    "RGB": ("RGB", "None"),
    "RGBW No White": ("RGB", "Zero"),
    "RGBW Accurate": ("RGB", "Accurate"),
    "RGBW Brighter": ("RGB", "Brighter"),
}


def _clean_effect_id(effect_id: str) -> str:
    return effect_id.lower().replace("(reactive)", "").replace("_", "")


def _match_effect_id(dirty_effect_id: str) -> str | None:
    candidate = _clean_effect_id(dirty_effect_id)
    for effect_id in LEGACY_EFFECT_IDS:
        if _clean_effect_id(effect_id) == candidate:
            return effect_id
    return None


def _sanitise_effect_config(old: dict[str, object]) -> dict[str, object]:
    new: dict[str, object] = {}
    for key, value in old.items():
        new_key = RENAMED_KEYS.get(key, key).replace("colour", "color")
        if (
            key == "frequency_range"
            and isinstance(value, str)
            and value in FREQUENCY_RANGE_REMAP
        ):
            value = FREQUENCY_RANGE_REMAP[value]
        new[new_key] = value
    return new


def _is_current(raw: dict[str, object]) -> bool:
    version = raw.get("configuration_version")
    if not isinstance(version, str):
        return False
    try:
        return parse_version(version) >= parse_version("2.3.6")
    except InvalidVersion:
        return False


def _invert_equalizer2d_flip(effect_config: object) -> object:
    if not isinstance(effect_config, dict):
        return effect_config
    if (
        effect_config.get("ring", True) is False
        and effect_config.get("center", True) is False
    ):
        effect_config["flip_vertical"] = not effect_config.get("flip_vertical", False)
    return effect_config


def legacy_to_v1(raw: dict[str, object]) -> dict[str, object]:
    """Upgrade any pre-overhaul config.json to schema_version 1.

    Malformed list or mapping entries the old code crashed on (a device, preset
    or scene entry that is not an object) are passed through unchanged, never
    replaced with defaults or used to synthesise data; validation after the
    migration quarantines them with the original value intact.
    """
    if _is_current(raw):
        return copy.deepcopy(raw)
    _LOGGER.warning("Migrating a pre-2.3.6 config to the current format.")
    old = copy.deepcopy(raw)
    new = copy.deepcopy(raw)

    if not _obj(old.get("audio")).get("audio_device"):
        new.pop("audio", None)
    new.pop("crossfade", None)
    new.pop("fade", None)

    devices: list[object] = []
    for item in _items(old.get("devices")):
        if not isinstance(item, dict):
            devices.append(item)
            continue
        device = item
        device_type = str(device.get("type", "")).lower()
        if device_type == "fxmatrix":
            _LOGGER.warning(
                "Dropping unsupported FXMatrix device %s.", device.get("id")
            )
            continue
        cfg = _obj(device.get("config"))
        if device_type == "artnet" and "device_repeat" in cfg:
            cfg["pixels_per_device"] = cfg.pop("device_repeat")
        if device_type == "artnet" and "output_mode" in cfg:
            rgb_order, white_mode = ARTNET_OUTPUT_MODES.get(
                str(cfg.pop("output_mode")), ("RGB", "None")
            )
            cfg["rgb_order"] = rgb_order
            cfg["white_mode"] = white_mode
        device.pop("effect", None)
        devices.append(device)
    new["devices"] = devices

    virtuals = _items(new.pop("displays", None)) or _items(new.pop("virtuals", None))
    if virtuals:
        for item in virtuals:
            virtual = _obj(item)
            effect = _obj(virtual.get("effect"))
            if effect:
                effect_id = effect.get("type")
                new_effect_id = _match_effect_id(str(effect_id)) if effect_id else None
                if not new_effect_id:
                    _LOGGER.warning(
                        "Dropping unknown effect %s from virtual %s.",
                        effect_id,
                        virtual.get("id"),
                    )
                    virtual.pop("effect", None)
                else:
                    virtual["effect"] = {
                        "config": _sanitise_effect_config(_obj(effect.get("config"))),
                        "type": new_effect_id,
                    }
            virtual["auto_generated"] = virtual.get("auto_generated", False)
    else:
        for device in devices:
            if not isinstance(device, dict):
                continue
            cfg = _obj(device.get("config"))
            if not isinstance(cfg.get("name"), str) or not cfg["name"]:
                continue
            name = cfg["name"]
            pixel_count = cfg.get("pixel_count", 1)
            last = pixel_count - 1 if isinstance(pixel_count, int) else 0
            virtuals.append(
                {
                    "id": generate_id(name),
                    "is_device": device.get("id"),
                    "auto_generated": False,
                    "config": {"name": name},
                    "segments": [[device.get("id"), 0, last, False]],
                }
            )
    new["virtuals"] = virtuals

    user_presets = _obj(new.pop("custom_presets", None)) or _obj(
        new.pop("user_presets", None)
    )
    new_presets: dict[str, object] = {}
    for effect_id, presets in user_presets.items():
        new_effect_id = _match_effect_id(effect_id)
        if not new_effect_id:
            _LOGGER.warning("Dropping presets for unknown effect %s.", effect_id)
            continue
        if not isinstance(presets, dict):
            new_presets[new_effect_id] = presets
            continue
        new_presets[new_effect_id] = {
            preset_id: (
                {
                    "name": preset.get("name"),
                    "config": _sanitise_effect_config(_obj(preset.get("config"))),
                }
                if isinstance(preset, dict)
                else preset
            )
            for preset_id, preset in presets.items()
        }
    new["user_presets"] = new_presets

    scenes = _obj(new.pop("scenes", None))
    new_scenes: dict[str, object] = {}
    for scene_id, raw_scene in scenes.items():
        if not isinstance(raw_scene, dict):
            new_scenes[scene_id] = raw_scene
            continue
        scene = raw_scene
        mode = next(
            (m for m in scene if m in ("devices", "displays", "virtuals")), None
        )
        entries: dict[str, object] = _obj(scene.pop(mode, None)) if mode else {}
        new_virtuals: dict[str, object] = {}
        for entry_id, raw_entry in entries.items():
            if mode == "devices":
                match = next(
                    (
                        _obj(v).get("id")
                        for v in virtuals
                        if _obj(v).get("is_device") == entry_id
                    ),
                    None,
                )
                if not match:
                    _LOGGER.warning(
                        "Dropping device %s from scene %s: no matching virtual.",
                        entry_id,
                        scene_id,
                    )
                    continue
                virtual_id = str(match)
            else:
                virtual_id = entry_id
            if not isinstance(raw_entry, dict):
                new_virtuals[virtual_id] = raw_entry
                continue
            entry = raw_entry
            effect_id = entry.get("type")
            effect_config = entry.get("config")
            if effect_id and effect_config:
                new_effect_id = _match_effect_id(str(effect_id))
                if not new_effect_id:
                    _LOGGER.warning(
                        "Dropping unknown effect %s from scene %s.", effect_id, scene_id
                    )
                    continue
                new_virtuals[virtual_id] = {
                    "config": _sanitise_effect_config(_obj(effect_config)),
                    "type": new_effect_id,
                }
            else:
                new_virtuals[virtual_id] = {}
        new_scenes[scene_id] = {"virtuals": new_virtuals, "name": scene.get("name")}
    new["scenes"] = new_scenes

    audio = _obj(new.get("audio"))
    min_volume = audio.get("min_volume", 0)
    if isinstance(min_volume, (int, float)) and min_volume > 1:
        audio["min_volume"] = 0.2

    try:
        needs_eq_fix = parse_version(
            str(old.get("configuration_version", "0.0.0"))
        ) < parse_version("2.3.6")
    except InvalidVersion:
        needs_eq_fix = True
    if needs_eq_fix:
        for item in virtuals:
            virtual = _obj(item)
            effect = _obj(virtual.get("effect"))
            if effect.get("type") == "equalizer2d":
                effect["config"] = _invert_equalizer2d_flip(
                    effect.get("config", dict[str, object]())
                )
            stored = _obj(virtual.get("effects"))
            if "equalizer2d" in stored:
                stored_eq = _obj(stored["equalizer2d"])
                stored_eq["config"] = _invert_equalizer2d_flip(
                    stored_eq.get("config", dict[str, object]())
                )
        for preset in _obj(new_presets.get("equalizer2d")).values():
            preset_obj = _obj(preset)
            preset_obj["config"] = _invert_equalizer2d_flip(
                preset_obj.get("config", dict[str, object]())
            )
        for scene in new_scenes.values():
            for virtual_effect in _obj(_obj(scene).get("virtuals")).values():
                effect = _obj(virtual_effect)
                if effect.get("type") == "equalizer2d":
                    effect["config"] = _invert_equalizer2d_flip(
                        effect.get("config", dict[str, object]())
                    )
    return new
