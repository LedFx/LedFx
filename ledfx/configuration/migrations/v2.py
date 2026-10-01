"""schema_version 1 -> 2: drop runtime-only keys older builds persisted, and
move Spotify triggers out of the scenes into the Spotify integration entry."""

import logging

_LOGGER = logging.getLogger(__name__)

RUNTIME_ONLY_KEYS = ("hosts", "ledfx_presets")
# The Scene model's fields (a test pins this against the model: steps stay pure).
SCENE_FIELDS = frozenset(
    {
        "name",
        "scene_image",
        "scene_tags",
        "scene_puturl",
        "scene_payload",
        "scene_midiactivate",
        "virtuals",
    }
)


def drop_runtime_keys(raw: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in raw.items() if k not in RUNTIME_ONLY_KEYS}


def move_spotify_triggers(raw: dict[str, object]) -> dict[str, object]:
    """Older builds stored Spotify triggers as extra list-valued scene keys
    (scenes.<sid>.<song_id>-<pos> = [song_id, song_name, pos]) and the
    Spotify entry's data held a stale copy of the scenes. Move the triggers
    to that entry's data, replacing the copy."""
    scenes = raw.get("scenes")
    if not isinstance(scenes, dict):
        return raw
    triggers: dict[str, dict[str, object]] = {}
    new_scenes: dict[str, object] = {}
    for scene_id, scene in scenes.items():
        if isinstance(scene, dict):
            found: dict[str, object] = {
                k: v
                for k, v in scene.items()
                if k not in SCENE_FIELDS and isinstance(v, list) and len(v) >= 3
            }
            if found:
                triggers[str(scene_id)] = found
                scene = {k: v for k, v in scene.items() if k not in found}
        new_scenes[str(scene_id)] = scene
    integrations = raw.get("integrations")
    if not isinstance(integrations, list):
        integrations = list[object]()
    entries = [
        e for e in integrations if isinstance(e, dict) and e.get("type") == "spotify"
    ]
    if triggers and not entries:
        # ponytail: dropped; triggers do nothing without a Spotify integration.
        _LOGGER.info(
            "Dropping Spotify triggers with no Spotify integration: %s", triggers
        )
    out = {**raw, "scenes": new_scenes}
    if entries:
        out["integrations"] = [
            {**e, "data": triggers}
            if isinstance(e, dict) and e.get("type") == "spotify"
            else e
            for e in integrations
        ]
    return out


def v1_to_v2(raw: dict[str, object]) -> dict[str, object]:
    return move_spotify_triggers(drop_runtime_keys(raw))


def strip_envelope(raw: dict[str, object]) -> None:
    """Remove the on-disk envelope and runtime-only keys in place, before validating.

    The one place this list lives: `ConfigStore.load` and `ConfigEndpoint.post` both call it.
    """
    for key in ("schema_version", "configuration_version", *RUNTIME_ONLY_KEYS):
        raw.pop(key, None)
