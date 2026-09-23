"""Snapcast configuration schema and constants."""

import logging

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 1704
DEFAULT_CLIENT_NAME = "LedFx"

# Device names in the audio device list are "SNAPCAST: <server id>"
DEVICE_PREFIX = "SNAPCAST:"
HOSTAPI_NAME = "SNAPCAST"


def validate_snapcast_host(host) -> tuple[bool, str]:
    """Validate a snapserver hostname or IP address.

    Returns:
        (True, "")            — host is valid
        (False, reason_str)   — host is invalid, reason describes why
    """
    if not isinstance(host, str):
        return False, "host must be a string"
    if not host:
        return False, "host must not be empty"
    if "://" in host:
        return False, "host must be a hostname or IP address, not a URL"
    if any(ch.isspace() for ch in host) or "\x00" in host or "/" in host:
        return False, "host contains invalid characters"
    return True, ""


def validate_snapcast_port(port) -> tuple[bool, str]:
    if isinstance(port, bool) or not isinstance(port, int):
        return False, "port must be an integer"
    if not 1 <= port <= 65535:
        return False, f"port {port} is out of range (1-65535)"
    return True, ""


def is_always_on(device_idx, query_devices, query_hostapis):
    """Check if the audio device at device_idx is a Snapcast device."""
    if not isinstance(device_idx, int) or device_idx < 0:
        return False
    try:
        devices = query_devices()
        hostapis = query_hostapis()
        if device_idx >= len(devices):
            return False
        hostapi_name = hostapis[devices[device_idx]["hostapi"]]["name"]
        return hostapi_name == HOSTAPI_NAME
    except Exception as exc:
        _LOGGER.debug(
            "is_always_on: exception checking device %s: %s",
            device_idx,
            exc,
        )
        return False


def eager_start(ledfx):
    """Start the audio subsystem immediately when snapcast_always_on is
    enabled and the configured audio device is a Snapcast source.

    A normal snapclient stays connected permanently, so with always-on LedFx
    remains visible in the server's client list even when no audio-reactive
    effect is running.
    """
    if not ledfx.config.get("snapcast_always_on", True):
        return

    audio_config = ledfx.config.get("audio", {})
    device_idx = audio_config.get("audio_device")
    device_name = audio_config.get("audio_device_name", "")

    # Lazy import to break circular dependency:
    # audio.py → snapcast/config.py → audio.py
    from ledfx.effects.audio import AudioAnalysisSource, AudioInputSource

    if not (
        device_name.startswith(DEVICE_PREFIX)
        or is_always_on(
            device_idx,
            AudioInputSource.query_devices,
            AudioInputSource.query_hostapis,
        )
    ):
        return

    _LOGGER.info(
        "Snapcast always-on: eagerly starting audio (device %s, name=%r)",
        device_idx,
        device_name,
    )

    existing_audio = getattr(ledfx, "audio", None)
    if existing_audio is not None:
        existing_audio.update_config(audio_config)
        return

    ledfx.audio = AudioAnalysisSource(ledfx, audio_config)


def build_server_config(data: dict, existing: dict | None = None):
    """Validate API input and merge it into a server config entry.

    Args:
        data: Fields supplied by the client (host, port, client_name).
        existing: The current entry when updating; None when creating, in
            which case ``host`` is required.

    Returns:
        (entry, "") on success, or (None, reason) if the input is invalid.
    """
    entry = dict(existing) if existing else {}
    if existing is None:
        if "host" not in data:
            return None, "Required key not provided: 'host'"
        entry = {"port": DEFAULT_PORT, "client_name": DEFAULT_CLIENT_NAME}

    if "host" in data:
        host = data["host"]
        if isinstance(host, str):
            host = host.strip()
        valid, reason = validate_snapcast_host(host)
        if not valid:
            return None, reason
        entry["host"] = host

    if "port" in data:
        valid, reason = validate_snapcast_port(data["port"])
        if not valid:
            return None, reason
        entry["port"] = data["port"]

    if "client_name" in data:
        client_name = data["client_name"]
        if not isinstance(client_name, str) or not client_name.strip():
            return None, "client_name must be a non-empty string"
        entry["client_name"] = client_name.strip()

    return entry, ""
