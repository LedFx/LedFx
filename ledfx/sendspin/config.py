"""Sendspin configuration schema and constants."""

import logging
import urllib.parse

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

# Default Sendspin server configuration
DEFAULT_SERVER_URL = "ws://192.168.1.12:8927/sendspin"
DEFAULT_CLIENT_NAME = "LedFx"

# Buffer capacity advertised to the Sendspin server during ClientHello.
# The server sends audio up to this many bytes ahead of the current play
# position.  ~2 seconds at 48 kHz / 16-bit / stereo (192 000 B/s) gives
# enough headroom for network jitter while keeping latency reasonable.
BUFFER_CAPACITY = 384000

# Sendspin configuration schema
SENDSPIN_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("server_url", default=DEFAULT_SERVER_URL): str,
        vol.Optional("client_name", default=DEFAULT_CLIENT_NAME): str,
    }
)


def validate_sendspin_server_url(url) -> tuple[bool, str]:
    """Validate a Sendspin server WebSocket URL.

    Checks:
    - Input must be a string (returns False instead of raising AttributeError)
    - Leading/trailing whitespace is allowed by callers who strip first; this
      function validates the already-stripped value
    - Scheme must be "ws" or "wss"
    - Hostname must be non-empty
    - Port, if present, must be in the valid range 0-65535
    - Path must not contain null bytes or path-traversal sequences

    Returns:
        (True, "")            — URL is valid
        (False, reason_str)   — URL is invalid, reason describes why
    """
    if not isinstance(url, str):
        return False, "server_url must be a string"

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False, "server_url could not be parsed"

    if parsed.scheme not in ("ws", "wss"):
        return (
            False,
            f"server_url scheme '{parsed.scheme}' is not allowed; must be ws or wss",
        )

    hostname = parsed.hostname
    if not hostname:
        return False, "server_url must contain a non-empty hostname"

    if parsed.port is not None and not (0 <= parsed.port <= 65535):
        return (
            False,
            f"server_url port {parsed.port} is out of range (0-65535)",
        )

    path = parsed.path
    if "\x00" in path:
        return False, "server_url path contains null bytes"
    if ".." in path.split("/"):
        return False, "server_url path contains path-traversal sequence"

    return True, ""


def is_always_on(device_idx, query_devices, query_hostapis):
    """Check if the audio device at device_idx is a Sendspin device.

    Args:
        device_idx: The audio device index to check.
        query_devices: Callable returning the full device tuple.
        query_hostapis: Callable returning the host API tuple.

    Returns:
        True if the device is a Sendspin server.
    """
    if not isinstance(device_idx, int) or device_idx < 0:
        return False
    try:
        devices = query_devices()
        hostapis = query_hostapis()
        if device_idx >= len(devices):
            return False
        hostapi_name = hostapis[devices[device_idx]["hostapi"]]["name"]
        return hostapi_name == "SENDSPIN"
    except Exception as exc:
        _LOGGER.debug(
            "is_always_on: exception checking device %s: %s",
            device_idx,
            exc,
        )
        return False


def eager_start(ledfx):
    """Eagerly start the audio subsystem if sendspin_always_on is enabled
    and the configured audio device is a Sendspin source.

    Called from core startup after sendspin servers are loaded so the
    Sendspin audio stream begins immediately, even when no audio-reactive
    effect is active yet.
    """
    if not ledfx.config.get("sendspin_always_on", False):
        return

    audio_config = ledfx.config.get("audio", {})
    device_idx = audio_config.get("audio_device")

    # Lazy import to break circular dependency:
    # audio.py → sendspin/config.py → audio.py
    from ledfx.effects.audio import AudioAnalysisSource, AudioInputSource

    if not is_always_on(
        device_idx,
        AudioInputSource.query_devices,
        AudioInputSource.query_hostapis,
    ):
        return

    _LOGGER.info(
        "Sendspin always-on: eagerly starting audio (device %s)",
        device_idx,
    )
    ledfx.audio = AudioAnalysisSource(ledfx, audio_config)
