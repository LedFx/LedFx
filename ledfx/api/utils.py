"""Config keys the /api/config endpoints accept per section."""

from ledfx.configuration.paths import _default_wled_settings

PERMITTED_KEYS = {
    "audio": (
        "min_volume",
        "audio_device",
        "delay_ms",
        "pitch_method",
        "onset_method",
        "pitch_tolerance",
    ),
    "melbanks": (
        "max_frequencies",
        "min_frequency",
        "peak_isolation",
        "coeffs_type",
        "samples",
    ),
    "melbank_collection": (
        "name",
        "min_frequency",
        "max_frequency",
    ),
    "wled_preferences": tuple(_default_wled_settings.keys()),
    "core": (
        "host",
        "port",
        "port_s",
        "dev_mode",
        "scan_on_startup",
        "create_segments",
        "visualisation_fps",
        "visualisation_maxlen",
        "transmission_mode",
        "global_transitions",
        "global_brightness",
        "melbank_collection",
        "flush_on_deactivate",
        "ui_brightness_boost",
        "startup_scene_id",
        "startup_playlist_id",
        "lifx_broadcast_address",
        "lifx_discovery_timeout",
        "sendspin_always_on",
        "allowed_origins",
        "allowed_hosts",
        "allow_null_origin",
        "now_playing_enabled",
    ),
}
