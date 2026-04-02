"""Sendspin configuration schema and constants."""

import voluptuous as vol

# Default Sendspin server configuration
DEFAULT_SERVER_URL = "ws://192.168.1.12:8927/sendspin"
DEFAULT_CLIENT_NAME = "LedFx Visualizer"
DEFAULT_BUFFER_CAPACITY = 1000000  # 1MB buffer (~1-2 seconds at 48kHz stereo)

# Sendspin configuration schema
SENDSPIN_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("server_url", default=DEFAULT_SERVER_URL): str,
        vol.Optional("client_name", default=DEFAULT_CLIENT_NAME): str,
        vol.Optional("preferred_codec", default="pcm"): vol.In(
            ["pcm", "opus", "flac"]
        ),
        vol.Optional("sample_rate", default=48000): vol.In([44100, 48000]),
        vol.Optional("buffer_capacity", default=DEFAULT_BUFFER_CAPACITY): int,
        vol.Optional("auto_reconnect", default=True): bool,
    }
)
