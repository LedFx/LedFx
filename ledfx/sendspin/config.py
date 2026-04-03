"""Sendspin configuration schema and constants."""

import voluptuous as vol

# Default Sendspin server configuration
DEFAULT_SERVER_URL = "ws://192.168.1.12:8927/sendspin"
DEFAULT_CLIENT_NAME = "LedFx"

# Buffer capacity advertised to the Sendspin server during ClientHello.
# ~64 KB is enough for a few hundred ms at 48kHz/16-bit stereo — keeps
# latency low for a visualization client.
BUFFER_CAPACITY = 65536

# Sendspin configuration schema
SENDSPIN_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("server_url", default=DEFAULT_SERVER_URL): str,
        vol.Optional("client_name", default=DEFAULT_CLIENT_NAME): str,
    }
)
