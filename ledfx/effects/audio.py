import logging
import threading
import time
from collections.abc import Callable
from functools import cache, cached_property, lru_cache
from typing import ClassVar

import numpy as np
import sounddevice as sd

import ledfx.api.websocket
from ledfx.api.websocket import WEB_AUDIO_CLIENTS, WebAudioStream
from ledfx.audio_process.client import AudioProcessClient, AudioProcessError
from ledfx.configuration.fields import (
    RUNTIME_CONTEXT,
    EnumSource,
    register_enum_source,
)
from ledfx.configuration.models import AudioConfig, replace_model
from ledfx.effects import Effect
from ledfx.effects.audio_analyzer import FREQ_MAX_MELS, AudioAnalyzer
from ledfx.effects.math import ExpFilter
from ledfx.effects.melbank import Melbanks
from ledfx.events import AudioDeviceChangeEvent, AudioSourceErrorEvent, Event
from ledfx.sendspin import SENDSPIN_AVAILABLE
from ledfx.sendspin.config import is_always_on as is_sendspin_always_on

# Sendspin server configurations discovered or configured
SENDSPIN_SERVERS = {}

_LOGGER = logging.getLogger(__name__)

MIN_MIDI = 21
MAX_MIDI = 108


class RemoteAudioStream:
    """A capture device opened in the audio process, with InputStream's
    start/stop/close, so the activation code drives it like a local one."""

    def __init__(self, client, **open_args):
        self._client = client
        self._open_args = open_args

    def start(self):
        self._client.open(**self._open_args)

    def stop(self):
        if self._client.alive:
            try:
                self._client.close()
            except AudioProcessError:
                _LOGGER.warning("The audio process did not confirm closing the device")

    def close(self):
        pass


class _IdleTempo:
    """What the tempo tracker reports before any audio has been analysed."""

    @staticmethod
    def get_bpm():
        return 0.0

    @staticmethod
    def get_confidence():
        return 0.0

    @staticmethod
    def get_period_s():
        return 0.0


_IDLE_TEMPO = _IdleTempo()


class AudioInputSource:
    _audio_stream_active = False
    _audio = None
    _stream = None
    _callbacks: ClassVar[list[Callable[[], None]]] = []
    _audioWindowSize = 4
    _analyzer = None
    _results = None
    # Set while this source's capture and analysis run in the audio process.
    _remote = None
    # The audio process client, shared by every source instance.
    _audio_process = None
    _subscriber_threshold = 0
    _timer = None
    _last_active = None
    # Track device by name, not index (indices can change)
    _last_device_name = None
    _device_list_cache = None  # Cache for device list
    _class_lock = threading.Lock()  # Class-level lock for shared state
    _activating = False  # Re-entry guard for activate()

    @staticmethod
    def refresh_device_list():
        """
        Force sounddevice/PortAudio to rescan audio devices.
        This is necessary because PortAudio caches the device list at initialization.

        If an audio stream is active, it will be gracefully stopped before refreshing.

        Serialized with activate() via _activating guard to prevent
        sd._terminate()/_initialize() from running concurrently with
        open_audio_stream().

        Returns:
            bool: True if an audio stream was active before refresh (and should be reactivated),
                  False otherwise
        """
        # Wait for any in-progress activation to complete before touching
        # PortAudio.  Setting _activating = True also blocks concurrent
        # activate() calls while the refresh is running.
        deadline = time.monotonic() + 10
        while True:
            with AudioInputSource._class_lock:
                if not AudioInputSource._activating:
                    AudioInputSource._activating = True
                    break
            if time.monotonic() > deadline:
                _LOGGER.warning(
                    "Timed out waiting for activation to complete before device list refresh"
                )
                return False
            time.sleep(0.05)

        try:
            # Check if there's an active stream that needs to be stopped
            # Use class lock to safely cache and clear the stream reference
            stream_to_close = None
            with AudioInputSource._class_lock:
                was_active = AudioInputSource._audio_stream_active

                if was_active:
                    _LOGGER.info("Stopping audio stream before device list refresh...")
                    # Cache and clear inside lock (atomic operation)
                    stream_to_close = AudioInputSource._stream
                    AudioInputSource._stream = None
                    AudioInputSource._audio_stream_active = False

            # Close outside lock to avoid deadlock with audio callbacks
            if stream_to_close:
                try:
                    stream_to_close.stop()
                    stream_to_close.close()
                except Exception as e:  # noqa: BLE001
                    _LOGGER.warning("Error closing stream during refresh: %s", e)

            try:
                # Force PortAudio to rescan devices by terminating and reinitializing
                sd._terminate()
                sd._initialize()
                # Clear the device list cache
                AudioInputSource._device_list_cache = None
                _LOGGER.info("Audio device list refreshed")
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning("Failed to refresh audio device list: %s", e)

            return was_active
        finally:
            with AudioInputSource._class_lock:
                AudioInputSource._activating = False

    def _persist_config(self):
        """
        Sync audio config to central config and persist to disk.
        No-op when _ledfx is not available (e.g. in tests).
        Returns True on success, False on failure or unavailable.
        """
        if not (hasattr(self, "_ledfx") and self._ledfx):
            return False
        try:
            self._ledfx.config.audio = self._config
            self._ledfx.config_store.request_save()
            return True
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Failed to persist audio config: %s", e)
            return False

    def _set_config(self, **changes):
        """Swap in a re-validated copy of the (frozen) config with changes.

        Replacing the whole model keeps related fields (device index and name)
        consistent for readers on other threads. No runtime context: these
        values come from the device list itself, so the device hook is skipped.
        """
        self._config = replace_model(self._config, **changes)

    def _update_device_config(self, device_idx):
        """
        Update the runtime-resolved device index without changing preference.

        Args:
            device_idx: The device index to set, or None to clear
        """
        self._set_config(audio_device=device_idx)
        self._persist_config()

    def _persist_active_device_config(self):
        """Persist the active index, upgrading name-less legacy configs once."""
        with AudioInputSource._class_lock:
            current_name = AudioInputSource._last_device_name
            current_idx = AudioInputSource._last_active

        if not current_name or current_idx is None:
            return

        changes = {"audio_device": current_idx}
        if not self._config.audio_device_name:
            changes["audio_device_name"] = current_name

        if any(getattr(self._config, key) != value for key, value in changes.items()):
            self._set_config(**changes)
            if self._persist_config():
                _LOGGER.info(
                    "Persisted active audio index %s (device '%s')",
                    current_idx,
                    current_name,
                )

    def handle_device_list_change(self):
        """
        Handle audio device list changes with automatic stream recovery.

        This method encapsulates the full lifecycle:
        1. Stop active stream and refresh device list
        2. Find previously active device by name (indices may have shifted)
        3. Update config with new device index if changed
        4. Reactivate stream with correct device

        This keeps all audio recovery logic in one place rather than split
        across core.py and audio.py.
        """
        # Stop any active stream and refresh the device list
        was_active = self.refresh_device_list()

        # The preferred name wins over the last active name, which may belong
        # to a temporary fallback used while that preference was unavailable.
        with AudioInputSource._class_lock:
            last_device_name = AudioInputSource._last_device_name
            last_device_idx = AudioInputSource._last_active
        preferred_name = self._config.audio_device_name or last_device_name

        if not preferred_name:
            _LOGGER.warning(
                "Cannot recover audio stream: previous device name not tracked"
            )
            return

        _LOGGER.info(
            "Attempting to recover audio device '%s' (was at index %s)",
            preferred_name,
            last_device_idx,
        )
        found_idx = self.get_device_index_by_name(preferred_name)

        if found_idx == -1:
            # For Sendspin virtual devices, never silently switch to a real
            # audio device — they may simply be temporarily unreachable rather
            # than permanently removed.  Notify the frontend instead.
            if preferred_name.startswith("SENDSPIN:"):
                _LOGGER.warning(
                    "Sendspin audio device '%s' not found after device list "
                    "change. Not falling back to default audio device.",
                    preferred_name,
                )

                self._ledfx.events.fire_event(
                    AudioSourceErrorEvent(
                        error_type="sendspin_device_not_found",
                        message=(
                            f"Sendspin audio source "
                            f"'{preferred_name[len('SENDSPIN:') :].strip()}' "
                            "is no longer available. Check your Sendspin server "
                            "or select a different audio source."
                        ),
                        device_name=preferred_name,
                    )
                )
                return

            _LOGGER.warning(
                "Previously active device '%s' no longer available after device list change. "
                "Will use default device.",
                preferred_name,
            )
            # Use default device logic (prefers loopback of default output, then default input)
            fallback_idx = AudioInputSource.default_device_index()
            if fallback_idx is not None:
                _LOGGER.info("Using fallback device at index %s", fallback_idx)
                self._update_device_config(fallback_idx)
            else:
                # Keep the preferred name even when no device is currently usable.
                _LOGGER.warning("No fallback device available")
                self._update_device_config(None)
        else:
            current_config_idx = self._config.audio_device
            if found_idx != current_config_idx:
                _LOGGER.info(
                    "Device list changed: '%s' moved from index %s to %s",
                    preferred_name,
                    current_config_idx,
                    found_idx,
                )
            else:
                _LOGGER.info(
                    "Device list changed: '%s' still at index %s",
                    preferred_name,
                    found_idx,
                )

            self._update_device_config(found_idx)

        # Refresh closes an active stream; do not open a new one for an
        # inactive source. Its resolved index will be used on next activation.
        if was_active:
            try:
                _LOGGER.info("Reactivating audio stream after device list refresh")
                self.activate()
            except Exception as e:  # noqa: BLE001
                _LOGGER.error(
                    "Failed to reactivate audio stream after device change: %s", e
                )

    @staticmethod
    def device_index_validator(val):
        """
        Validates device index in case the saved setting is no longer valid.
        Accepts None (schema default) and resolves to the default device.
        """
        valid = AudioInputSource.valid_device_indexes()
        _LOGGER.debug(
            "device_index_validator: val=%s valid_indexes=%s",
            val,
            valid,
        )
        if val is not None and val in valid:
            _LOGGER.debug("device_index_validator: accepted %s as-is", val)
            return val
        else:
            default = AudioInputSource.default_device_index()
            _LOGGER.warning(
                "device_index_validator: val=%s not in valid indexes — "
                "falling back to default %s",
                val,
                default,
            )
            return default

    @staticmethod
    def valid_device_indexes():
        """
        A list of integers corresponding to valid input devices
        """
        return tuple(AudioInputSource.input_devices().keys())

    @staticmethod
    def audio_input_device_exists():
        """
        Returns True if there are valid input devices
        """
        return len(AudioInputSource.valid_device_indexes()) > 0

    @staticmethod
    def default_device_index():
        """
        Finds the WASAPI loopback device index of the default output device if it exists
        If it does not exist, return the default input device index
        Returns:
            integer: the sounddevice device index to use for audio input
        """
        device_list = sd.query_devices()
        default_output_device_idx = sd.default.device["output"]
        default_input_device_idx = sd.default.device["input"]
        if len(device_list) == 0 or default_output_device_idx == -1:
            _LOGGER.warning("No audio output devices found.")
        else:
            default_output_device_name = device_list[default_output_device_idx]["name"]

            # We need to run over the device list looking for the target devices name
            _LOGGER.debug(
                "Looking for audio loopback device for default output device at index %s: %s",
                default_output_device_idx,
                default_output_device_name,
            )
            for device_index, device in enumerate(device_list):
                # sometimes the audio device name string is truncated, so we need to match what we have and Loopback but otherwise be sloppy
                if (
                    default_output_device_name in device["name"]
                    and "[Loopback]" in device["name"]
                ):
                    # Return the loopback device index
                    _LOGGER.debug(
                        "Found audio loopback device for default output device at index %s: %s",
                        device_index,
                        device["name"],
                    )
                    return device_index

        # The default input device index is not always valid (i.e no default input devices)
        valid_device_indexes = AudioInputSource.valid_device_indexes()
        if len(valid_device_indexes) == 0:
            _LOGGER.warning(
                "No valid audio input devices found. Unable to use audio reactive effects."
            )
            return None
        else:
            if default_input_device_idx in valid_device_indexes:
                _LOGGER.debug(
                    "No audio loopback device found for default output device. Using default input device at index %s: %s",
                    default_input_device_idx,
                    device_list[default_input_device_idx]["name"],
                )
                return default_input_device_idx
            else:
                # Return the first valid input device index if we can't find a valid default input device
                if len(valid_device_indexes) > 0:
                    first_valid_idx = next(iter(valid_device_indexes))
                    _LOGGER.debug(
                        "No valid default audio input device found. Using first valid input device at index %s: %s",
                        first_valid_idx,
                        device_list[first_valid_idx]["name"],
                    )
                    return first_valid_idx

    @staticmethod
    def query_hostapis():
        apis = sd.query_hostapis() + ({"name": "WEB AUDIO"},)
        if SENDSPIN_AVAILABLE:
            apis = apis + ({"name": "SENDSPIN"},)
        return apis

    @staticmethod
    def query_devices():
        hostapis = AudioInputSource.query_hostapis()
        web_audio_idx = next(
            i for i, h in enumerate(hostapis) if h["name"] == "WEB AUDIO"
        )
        devices = sd.query_devices() + tuple(
            {
                "hostapi": web_audio_idx,
                "name": f"{client}",
                "max_input_channels": 1,
                "client": client,
            }
            for client in WEB_AUDIO_CLIENTS
        )
        if SENDSPIN_AVAILABLE:
            sendspin_idx = next(
                i for i, h in enumerate(hostapis) if h["name"] == "SENDSPIN"
            )
            sendspin_devices = tuple(
                {
                    "hostapi": sendspin_idx,
                    "name": name,
                    "max_input_channels": 1,
                    "sendspin_config": config,
                }
                for name, config in SENDSPIN_SERVERS.items()
            )
            devices = devices + sendspin_devices
        return devices

    @staticmethod
    def input_devices():
        hostapis = AudioInputSource.query_hostapis()
        devices = AudioInputSource.query_devices()
        return {
            idx: f"{hostapis[device['hostapi']]['name']}: {device['name']}"
            for idx, device in enumerate(devices)
            if (
                device["max_input_channels"] > 0
                and "asio" not in device["name"].lower()
            )
        }

    @staticmethod
    def get_index_name(index):
        devices = AudioInputSource.input_devices()
        return devices.get(index, "")

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self.lock = threading.Lock()
        # We must not inherit legacy _callbacks from prior instances
        self._callbacks = []
        self.update_config(config)

        def shutdown_event(e):
            # We give the rest of LedFx a second to shutdown before we deactivate the audio subsystem.
            # This is to prevent LedFx hanging on shutdown if the audio subsystem is still running while
            # effects are being unloaded. This is a bit hacky but it works.
            self._timer = threading.Timer(0.5, self.check_and_deactivate)
            self._timer.start()

        self._ledfx.events.add_listener(shutdown_event, Event.LEDFX_SHUTDOWN)

    def _resolve_device_from_name(self):
        """
        Resolve the audio device by name from config.
        Called at startup/config-update to handle index drift across restarts.

        Resolution order:
        1. Name match at saved index (fast path, no drift)
        2. Name match at different index (drift detected, update index)
        3. No name stored (legacy config) — use index as-is
        4. Name not found — fall through to existing index/default logic
        """
        saved_name = self._config.audio_device_name
        saved_idx = self._config.audio_device

        if not saved_name:
            # No name stored (legacy config or first run) — use index as-is
            return

        devices = self.input_devices()

        # Fast path: saved index exists and name matches
        if saved_idx in devices and devices[saved_idx] == saved_name:
            _LOGGER.debug(
                "Audio device '%s' confirmed at index %s",
                saved_name,
                saved_idx,
            )
            return

        # Name-based search (index has drifted)
        found_idx = self.get_device_index_by_name(saved_name)

        if found_idx != -1:
            _LOGGER.info(
                "Audio device '%s' moved from index %s to %s (enumeration changed)",
                saved_name,
                saved_idx,
                found_idx,
            )
            self._set_config(audio_device=found_idx)
            # Persist the corrected index
            self._persist_config()
            return

        # Device not found by name at all. Keep the preference and use a
        # temporary runtime index until it becomes available again.
        # For Sendspin virtual devices: do NOT fall back to a real audio device.
        # Silently switching to a microphone/loopback when the user intended
        # Sendspin is confusing and hard to diagnose.  Report the error and
        # leave the config unchanged so the user can fix it.
        if saved_name.startswith("SENDSPIN:"):
            _LOGGER.warning(
                "Sendspin audio device '%s' not found in current device list "
                "(server may be removed or SENDSPIN_SERVERS not yet loaded). "
                "Not falling back to default audio device.",
                saved_name,
            )

            self._ledfx.events.fire_event(
                AudioSourceErrorEvent(
                    error_type="sendspin_device_not_found",
                    message=(
                        f"Sendspin audio source '{saved_name[len('SENDSPIN:') :].strip()}' "
                        "not found. Check your Sendspin server configuration or "
                        "select a different audio source."
                    ),
                    device_name=saved_name,
                )
            )
            return

        # Do not discard the preferred name or persist the fallback as identity.
        default_idx = self.default_device_index()
        _LOGGER.warning(
            "Saved audio device '%s' not found in current device list. "
            "Using temporary default device (index %s).",
            saved_name,
            default_idx,
        )
        self._set_config(audio_device=default_idx)
        self._persist_config()

    def update_config(self, config):
        """Deactivate the audio, update the config, then reactivate"""
        explicit_index_change = (
            hasattr(self, "_config")
            and "audio_device" in config
            and "audio_device_name" not in config
            and config["audio_device"] != self._config.audio_device
        )
        # Merge the incoming (possibly partial) update over the existing config
        # before validation. Without this, a partial update such as
        # {"delay_ms": N} re-validates a bare dict and the schema injects
        # defaults for every absent key (audio_device -> the default device,
        # audio_device_name -> ""), silently resetting the active device. The
        # name-based restore below cannot recover it because the name has
        # already been cleared.
        if hasattr(self, "_config"):
            config = {**self._config.model_dump(), **config}
            if explicit_index_change:
                config["audio_device_name"] = self.input_devices().get(
                    config["audio_device"], ""
                )
        new_config = AudioConfig.model_validate(config, context=RUNTIME_CONTEXT)

        device_changing = False
        pipeline_changing = False
        # work out if it is new. during first start, there will be no self._config
        if hasattr(self, "_config"):
            old_config = self._config
            # Pipeline-affecting keys require rebuilding internal audio objects even when the audio stream should stay active.
            _PIPELINE_KEYS = ("delay_ms", "sample_rate", "fft_size", "separate_process")
            pipeline_changing = any(
                getattr(old_config, k) != getattr(new_config, k) for k in _PIPELINE_KEYS
            )

            if old_config.audio_device != new_config.audio_device:
                device_changing = True
        else:
            old_config = None

        if AudioInputSource._audio_stream_active and (
            device_changing or pipeline_changing
        ):
            self.deactivate()

        self._config = new_config
        # Resolve device by name if available (handles index drift across restarts)
        self._resolve_device_from_name()

        # cache up last active and lets see if it changes
        # Read _last_active with class lock protection
        with AudioInputSource._class_lock:
            last_active = AudioInputSource._last_active

        # Activate outside the lock to avoid deadlock
        if (
            len(self._callbacks) != 0 or self._should_always_keep_active()
        ) and not AudioInputSource._audio_stream_active:
            self.activate()

        # Check if device changed and fire event if needed
        with AudioInputSource._class_lock:
            if last_active != AudioInputSource._last_active:
                self._ledfx.events.fire_event(
                    AudioDeviceChangeEvent(
                        self.get_index_name(self._config.audio_device)
                    )
                )

        # Shared, not copied: AudioConfig is frozen.
        self._ledfx.config.audio = self._config

    def activate(self):
        # Re-entry guard - must be atomic with _class_lock so concurrent
        # callers cannot both pass the check before either sets the flag.
        with AudioInputSource._class_lock:
            if AudioInputSource._activating:
                _LOGGER.warning("activate() re-entry blocked")
                return
            AudioInputSource._activating = True
        try:
            self._activate_inner()
        finally:
            with AudioInputSource._class_lock:
                AudioInputSource._activating = False

    def _activate_inner(self):

        if self._audio is None:
            try:
                self._audio = sd
            except OSError as Error:
                _LOGGER.critical("Sounddevice error: %s. Shutting down.", Error)
                self._ledfx.stop()

        # Enumerate all of the input devices and find the one matching the
        # configured host api and device name
        input_devices = self.query_devices()

        hostapis = self.query_hostapis()
        valid_device_indexes = self.valid_device_indexes()
        if not valid_device_indexes:
            # There are no valid audio input devices, so we can't activate the audio source.
            # We should never get here, as we check for devices on start-up.
            # This likely just captures if a device is removed after start-up.
            _LOGGER.warning(
                "Audio input device not found. Unable to activate audio source. Deactivating."
            )
            self.deactivate()
            return
        _LOGGER.debug("********************************************")
        _LOGGER.debug("Valid audio input devices:")
        for index in valid_device_indexes:
            hostapi_name = hostapis[input_devices[index]["hostapi"]]["name"]
            device_name = input_devices[index]["name"]
            input_channels = input_devices[index]["max_input_channels"]
            _LOGGER.debug(
                "  [%s] %s: %s (channels: %s)",
                index,
                hostapi_name,
                device_name,
                input_channels,
            )
        _LOGGER.debug("********************************************")
        device_idx = self._config.audio_device
        _LOGGER.info(
            "_activate_inner: configured audio_device=%s "
            "audio_device_name=%r valid_indexes=%s",
            device_idx,
            self._config.audio_device_name,
            valid_device_indexes,
        )

        configured_name = self._config.audio_device_name
        if configured_name.startswith("SENDSPIN:"):
            sendspin_idx = self.get_device_index_by_name(configured_name)
            device_idx = sendspin_idx if sendspin_idx != -1 else None

        if device_idx not in valid_device_indexes:
            # For Sendspin virtual devices, never fall back to a real audio
            # device — notify the frontend so the user can take action.
            if configured_name.startswith("SENDSPIN:"):
                _LOGGER.warning(
                    "Sendspin audio device '%s' (index %s) is not available. "
                    "Not falling back to default audio device.",
                    configured_name,
                    device_idx,
                )

                self._ledfx.events.fire_event(
                    AudioSourceErrorEvent(
                        error_type="sendspin_device_unavailable",
                        message=(
                            f"Sendspin audio source '{configured_name[len('SENDSPIN:') :].strip()}' "
                            "is not available. Check your Sendspin server configuration "
                            "or select a different audio source."
                        ),
                        device_name=configured_name,
                    )
                )
                return

            # Configured device is invalid — resolve the default now
            default_device = self.default_device_index()
            if device_idx is not None and device_idx > max(valid_device_indexes):
                _LOGGER.warning(
                    "Audio device index %s out of range (max valid: %s). "
                    "Falling back to default device index %s",
                    device_idx,
                    max(valid_device_indexes),
                    default_device,
                )
            else:
                # Get device name safely (input_devices is a tuple, not dict)
                try:
                    device_name = input_devices[device_idx].get(
                        "name", f"index {device_idx}"
                    )
                except (IndexError, KeyError, TypeError):
                    device_name = f"index {device_idx}"
                _LOGGER.warning(
                    "Audio device [%s] '%s' not in valid devices. "
                    "Falling back to default device index %s",
                    device_idx,
                    device_name,
                    default_device,
                )
            device_idx = default_device

        # The per-block signal chain (resampler, delay line, pre-emphasis, phase
        # vocoder, melbanks, detectors) lives in AudioAnalyzer.
        self._analyzer = self._create_analyzer()
        self._remote = self._audio_process_client()
        if self._remote is not None:
            self._remote.configure(*self._analyzer_args())

        def update_device_tracking(device_idx):
            """
            Update class-level tracking of active device index and name.
            Thread-safe with class lock protection.
            """
            with AudioInputSource._class_lock:
                AudioInputSource._last_active = device_idx
                device_name = input_devices[device_idx].get("name", None)
                AudioInputSource._last_device_name = (
                    f"{hostapis[input_devices[device_idx]['hostapi']]['name']}: {device_name}"
                    if device_name
                    else None
                )

        def open_audio_stream(device_idx):
            """
            Opens an audio stream for the specified input device.
            Parameters:
            device_idx (int): The index of the input device to open the audio stream for.
            Behavior:
            - Detects if the device is a Windows WASAPI Loopback device and logs its name and channel count.
            - If the device is a WEB AUDIO device, initializes a WebAudioStream and sets it as the active audio stream.
            - For other devices, initializes an InputStream with the device's default sample rate and other parameters.
            - Initializes a resampler with the "sinc_fastest" algorithm that downmixes the source to a single-channel.
            - Logs the name of the opened audio source.
            - Starts the audio stream and sets the audio stream active flag to True.
            """

            device = input_devices[device_idx]
            channels = None
            if (
                hostapis[device["hostapi"]]["name"] == "Windows WASAPI"
                and "Loopback" in device["name"]
            ):
                _LOGGER.info(
                    "Loopback device detected: %s with %s channels",
                    device["name"],
                    device["max_input_channels"],
                )
            else:
                # if are not a windows loopback device, we will downmix to mono
                # issue seen with poor audio behaviour on Mac and Linux
                # this is similar to the long standing prior implementation
                channels = 1

            if hostapis[device["hostapi"]]["name"] == "WEB AUDIO":
                ledfx.api.websocket.ACTIVE_AUDIO_STREAM = AudioInputSource._stream = (
                    WebAudioStream(device["client"], self._audio_sample_callback)
                )
            elif (
                SENDSPIN_AVAILABLE and hostapis[device["hostapi"]]["name"] == "SENDSPIN"
            ):
                from ledfx.sendspin.stream import SendspinAudioStream

                _LOGGER.debug(
                    "Opening SendspinAudioStream for '%s'",
                    device["name"],
                )
                AudioInputSource._stream = SendspinAudioStream(
                    device["sendspin_config"],
                    self._audio_sample_callback,
                    instance_id=self._ledfx.config.instance_id,
                    ledfx=self._ledfx,
                )
            elif self._remote is not None:
                AudioInputSource._stream = RemoteAudioStream(
                    self._remote,
                    device=device_idx,
                    device_name=f"{hostapis[device['hostapi']]['name']}: {device['name']}",
                    samplerate=int(device["default_samplerate"]),
                    blocksize=int(
                        device["default_samplerate"] / self._config.sample_rate
                    ),
                    channels=channels,
                )
            else:
                AudioInputSource._stream = self._audio.InputStream(
                    samplerate=int(device["default_samplerate"]),
                    device=device_idx,
                    callback=self._audio_sample_callback,
                    dtype=np.float32,
                    latency="low",
                    blocksize=int(
                        device["default_samplerate"] / self._config.sample_rate
                    ),
                    # only pass channels if we set it to something other than None
                    **({"channels": channels} if channels is not None else {}),
                )

            _LOGGER.info(
                "Audio source opened: %s: %s",
                hostapis[device["hostapi"]]["name"],
                device.get("name", device.get("client")),
            )

            AudioInputSource._stream.start()
            with AudioInputSource._class_lock:
                AudioInputSource._audio_stream_active = True

        def try_open_device(dev_idx, reinit=False):
            """
            Attempt to open an audio device, optionally reinitializing
            PortAudio first (clears poisoned state from WDM-KS devices).
            Returns True on success, False on failure.
            """
            if reinit:
                self.deactivate()
                try:
                    sd._terminate()
                    sd._initialize()
                except Exception as reinit_err:  # noqa: BLE001
                    _LOGGER.warning("PortAudio reinit failed: %s", reinit_err)
                    return False
            try:
                open_audio_stream(dev_idx)
                update_device_tracking(dev_idx)
                return True
            except (sd.PortAudioError, OSError) as err:
                _LOGGER.warning("Audio device [%s] failed: %s", dev_idx, err)
                return False

        # Audio device startup sequence:
        # PortAudio's internal state may be poisoned at startup
        # (e.g. WDM-KS devices interfere during initial enumeration).
        # Recovery: try configured → reinit + retry configured → reinit + fallback
        if try_open_device(device_idx):
            self._persist_active_device_config()
            return

        _LOGGER.info("Reinitializing PortAudio and retrying device [%s]...", device_idx)
        if try_open_device(device_idx, reinit=True):
            _LOGGER.info(
                "Audio device [%s] opened successfully after PortAudio reinit.",
                device_idx,
            )
            self._persist_active_device_config()
            return

        fallback_device = self.default_device_index()
        _LOGGER.info("Falling back to default device [%s]...", fallback_device)
        if fallback_device is not None and try_open_device(
            fallback_device, reinit=True
        ):
            self._persist_active_device_config()
            return

        _LOGGER.warning(
            "All audio devices failed - please retry or select a different device."
        )
        self.deactivate()

    def deactivate(self):
        # Stop the stream outside the lock to avoid deadlock with audio callback
        # The audio callback thread may be waiting to complete, and if it needs
        # any locks, holding the lock while calling stop() creates a circular wait
        stream_to_close = None
        with AudioInputSource._class_lock:
            if AudioInputSource._stream:
                stream_to_close = AudioInputSource._stream
                AudioInputSource._stream = None
            AudioInputSource._audio_stream_active = False

        # Stop/close outside the lock
        if stream_to_close:
            stream_to_close.stop()
            stream_to_close.close()
            _LOGGER.info("Audio source closed.")

    def _should_always_keep_active(self):
        """Check if the current audio source should stay active regardless of subscribers."""
        sendspin_always_on = self._ledfx.config.sendspin_always_on
        if not sendspin_always_on:
            return False

        configured_name = (
            self._config.audio_device_name if hasattr(self, "_config") else ""
        )
        if isinstance(configured_name, str) and configured_name.startswith("SENDSPIN:"):
            return True

        device_idx = self._config.audio_device if hasattr(self, "_config") else None
        result = is_sendspin_always_on(
            device_idx,
            self.query_devices,
            self.query_hostapis,
        )
        return result

    def subscribe(self, callback):
        """Registers a callback with the input source"""
        self._callbacks.append(callback)
        if len(self._callbacks) > 0 and not AudioInputSource._audio_stream_active:
            self.activate()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def unsubscribe(self, callback):
        """Unregisters a callback with the input source"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
        if (
            len(self._callbacks) <= self._subscriber_threshold
            and AudioInputSource._audio_stream_active
        ):
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(5.0, self.check_and_deactivate)
            self._timer.start()

    def check_and_deactivate(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
        if self._should_always_keep_active():
            _LOGGER.debug("Sendspin always-on active, skipping deactivate")
            return
        if (
            len(self._callbacks) <= self._subscriber_threshold
            and AudioInputSource._audio_stream_active
        ):
            self.deactivate()

    def get_device_index_by_name(self, device_name: str):
        """
        Find device index by name string.
        Tries exact match first, then falls back to partial match since
        device names can be truncated.

        Uses careful partial matching to avoid false positives when device
        names are similar (e.g., "Microphone" vs "Microphone (Realtek)").
        """
        devices = self.input_devices()

        # First try exact match
        for key, value in devices.items():
            if device_name == value:
                return key

        # Fallback to partial match (device names can be truncated)
        # Only match if the stored name is contained in the current device name
        # (not the reverse, to avoid matching shorter names incorrectly)
        best_match_idx = -1
        best_match_len = 0

        for key, value in devices.items():
            # Case 1: Stored name is substring of current device name
            # This handles truncation where stored name is shorter
            if device_name in value and len(value) > best_match_len:
                # Prefer longer matches to find the most specific device
                best_match_idx = key
                best_match_len = len(value)

        if best_match_idx != -1:
            _LOGGER.debug(
                "Found device by partial match: '%s' in '%s' at index %s",
                device_name,
                devices[best_match_idx],
                best_match_idx,
            )
            return best_match_idx

        return -1

    def _audio_sample_callback(self, in_data, frame_count, time_info, status):
        """Callback for when a new audio sample is acquired"""
        remote = self._remote
        if remote is not None:
            # Browser or Sendspin audio arrives here; the audio process
            # analyses it like its own capture.
            if remote.alive:
                remote.push(in_data)
            return
        analyzer = self._analyzer
        if analyzer is None or not analyzer.process(in_data):
            return
        self._apply_results(analyzer)

    def _apply_results(self, results):
        """Make one block's analysis results current and notify subscribers.

        `results` is anything with AudioAnalyzer's result attributes: the
        analyzer itself when analysis runs in this process.
        """
        self._results = results
        silence_controller = getattr(self._ledfx, "silence_scene", None)
        if silence_controller is not None:
            silence_controller.report_volume(results.volume_filtered)
        self._invoke_callbacks()

    def _analyzer_args(self):
        raise NotImplementedError

    def _create_analyzer(self):
        return AudioAnalyzer(*self._analyzer_args())

    def _audio_process_client(self):
        """The running audio process client when this source should use one.

        Falls back to in-process analysis, with a warning, when the process
        cannot be started.
        """
        if not self._config.separate_process:
            return None
        client = AudioInputSource._audio_process
        if client is None or not client.alive:
            client = AudioProcessClient(self._apply_results)
            try:
                client.start()
            except OSError as e:
                _LOGGER.warning(
                    "Could not start the audio process (%s); analysing audio in-process.",
                    e,
                )
                return None
            AudioInputSource._audio_process = client
        client.on_results = self._apply_results
        return client

    def _invoke_callbacks(self):
        """Notifies all clients of the new data"""
        for callback in self._callbacks:
            callback()

    @property
    def _has_volume_measurement(self):
        results = self._results
        return results is not None and results.has_volume_measurement

    def audio_sample(self, raw=False):
        """Returns the raw audio sample"""
        results = self._results
        if results is None:
            return None
        if raw:
            return results.raw_sample
        return results.processed_sample

    def frequency_domain(self):
        results = self._results
        return results.frequency_domain if results is not None else None

    @property
    def _frequency_domain(self):
        return self.frequency_domain()

    def volume(self, filtered=True):
        results = self._results
        if results is None:
            return -90
        if filtered:
            return results.volume_filtered
        return results.volume_raw


class AudioAnalysisSource(AudioInputSource):
    # some frequency constants
    # beat, bass, mids, high
    freq_max_mels: ClassVar[list[int]] = list(FREQ_MAX_MELS)

    # ~4s at 60 blocks/s: an effect pausing between reads never sees a stale
    # group, and a deactivated effect stops costing anything quickly.
    DEMAND_TTL_BLOCKS = 240

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.initialise_analysis()

        # Publishes each block's results before any effect callback runs
        self.subscribe(self._publish_results)

        # ensure any new analysis callbacks are above this line
        self._subscriber_threshold = len(self._callbacks)

    def initialise_analysis(self):
        if not hasattr(self, "_demand"):
            # Demand tracking, see want().
            self._demand = {}
            self._demand_block = 0
            self._demand_sent = None
        if not hasattr(self, "melbanks"):
            self.melbanks = Melbanks(
                self._ledfx, self, self._ledfx.config.melbanks.model_dump()
            )

    def _analyzer_args(self):
        # A Sendspin source that is always on can activate from inside
        # AudioInputSource.__init__, before initialise_analysis has run.
        self.initialise_analysis()
        return (
            self._config.model_dump(),
            [entry["config"] for entry in self.melbanks.melbank_collection],
            self._ledfx.config.melbanks.coeffs_type,
        )

    def _rebuild_analyzer(self):
        """Pick up changed analysis or melbank settings without reopening the
        stream. Detector and filter state restart, as they always did."""
        if self._analyzer is not None:
            self._analyzer = self._create_analyzer()
            remote = self._remote
            if remote is not None and remote.alive:
                remote.configure(*self._analyzer_args())

    def update_config(self, config):
        super().update_config(config)
        self.initialise_analysis()
        self._rebuild_analyzer()

    def want(self, group):
        """Register that something is about to read this result group (a name
        from ANALYSIS_GROUPS). Called on every read path, so it is one dict
        store; groups nobody read for DEMAND_TTL_BLOCKS are no longer computed.
        """
        self._demand[group] = self._demand_block

    def _send_demand(self):
        """Tell the analysis, local or in the audio process, which groups were
        read recently. Sent only when that set or the analysis changes."""
        block = self._demand_block
        ttl = self.DEMAND_TTL_BLOCKS
        groups = frozenset(g for g, at in self._demand.items() if block - at <= ttl)
        remote = self._remote
        target = remote if remote is not None else self._analyzer
        if target is None or (target, groups) == self._demand_sent:
            return
        if remote is not None:
            if not remote.alive:
                return
            remote.want(groups)
        else:
            target.set_wanted(groups)
        self._demand_sent = (target, groups)

    def _publish_results(self):
        """Copy the block's melbanks into the arrays effects read, then send
        the graph updates, as Melbanks.__call__ did."""
        self._demand_block += 1
        self._send_demand()
        results = self._results
        melbanks = self.melbanks
        try:
            for target, source in zip(melbanks.melbanks, results.melbanks, strict=True):
                np.copyto(target, source)
            for target, source in zip(
                melbanks.melbanks_filtered, results.melbanks_filtered, strict=True
            ):
                np.copyto(target, source)
        except ValueError:
            # The melbank layout changed mid-block; the rebuilt analyzer's next
            # block has the new shape.
            return
        if melbanks.dev_enabled:
            graphed = range(len(melbanks.melbank_processors))
        else:
            graphed = (len(melbanks.melbank_processors) - 1,)
        # The graphs read their melbanks too, but only while a page shows them.
        graph_listened = self._ledfx.events.has_listeners(Event.GRAPH_UPDATE)
        for i in graphed:
            if graph_listened:
                self.want(f"melbank{i}")
            melbanks.send_melbank_event(i)

    def pitch(self):
        self.want("pitch")
        results = self._results
        return results.pitch if results is not None else 0

    def onset(self):
        results = self._results
        return results.onset if results is not None else False

    def bpm_beat_now(self):
        """
        Returns True if a beat is expected now based on BPM data
        """
        results = self._results
        return results.bpm_beat_now if results is not None else False

    def volume_beat_now(self):
        """
        Returns True if a beat is expected now based on volume of the beat freq region
        """
        self.want("volume_beat")
        results = self._results
        return results.volume_beat_now if results is not None else False

    @property
    def beat_counter(self):
        results = self._results
        return results.beat_counter if results is not None else 0

    @property
    def _tempo(self):
        """The tempo tracker, for its get_bpm()/get_confidence()/get_period_s()."""
        results = self._results
        return results.tempo if results is not None else _IDLE_TEMPO

    def get_freq_power(self, i, filtered=True):
        # Sole read path of every band power helper.
        self.want("freq_power")
        results = self._results
        if results is None:
            return 0.0
        if filtered:
            value = results.freq_power_filtered[i]
        else:
            value = results.freq_power_raw[i]

        return value if not np.isnan(value) else 0.0

    def beat_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the beat power
        """
        return self.get_freq_power(0, filtered)

    def bass_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the bass power
        """
        return self.get_freq_power(1, filtered)

    def lows_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the lows power.
        this is just the sum of bass and beat power.
        """
        return (
            self.get_freq_power(0, filtered) + self.get_freq_power(1, filtered)
        ) * 0.5

    def mids_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the mids power
        """
        return self.get_freq_power(2, filtered)

    def high_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the highs power
        """
        return self.get_freq_power(3, filtered)

    def bar_oscillator(self):
        """
        Returns a float (0<=x<4) corresponding to the position of the beat
        tracker in the musical bar (4 beats)
        This is synced and quantized to the bpm of whatever is playing.
        While the beat number might not necessarily be accurate, the
        relative position of the tracker between beats will be quite accurate.

        NOTE: currently this makes no attempt to guess which beat is the first
        in the bar. It simple counts to four with each beat that is detected.
        The actual value of the current beat in the bar is completely arbitrary,
        but in time with each beat.

        0           1           2           3
        {----------time for one bar---------}
               ^    -->      -->      -->
            value of
        beat grid pointer
        """
        results = self._results
        return results.bar_oscillator if results is not None else 0.0

    def beat_oscillator(self):
        """
        returns a float (0<=x<1) corresponding to the relative position of the
        bar oscillator in the current beat.

        0                0.5                 <1
        {----------time for one beat---------}
               ^    -->      -->      -->
            value of
           oscillator
        """
        return self.bar_oscillator() % 1


_EVENT_FLAGS = ("onset", "bpm_beat_now", "volume_beat_now")


class _WithMissedEvents:
    """The audio source as one effect's audio_data_updated sees it after it
    missed blocks: the newest results, plus any onset or beat among the
    missed ones, so a busy frame delays an event instead of losing it."""

    def __init__(self, source, missed):
        self._source = source
        self._missed = missed

    def __getattr__(self, name):
        return getattr(self._source, name)

    def onset(self):
        return "onset" in self._missed or self._source.onset()

    def bpm_beat_now(self):
        return "bpm_beat_now" in self._missed or self._source.bpm_beat_now()

    def volume_beat_now(self):
        return "volume_beat_now" in self._missed or self._source.volume_beat_now()


@Effect.no_registration
class AudioReactiveEffect(Effect):
    """
    Base for audio reactive effects. This really just subscribes
    to the melbank input source and forwards input along to the
    subclasses. This can be expanded to do the common r/g/b filters.
    """

    # this can be used by inheriting classes for power func selection in schema
    # see magnitude or scan effect for examples
    POWER_FUNCS_MAPPING: ClassVar[dict[str, str]] = {
        "Beat": "beat_power",
        "Bass": "bass_power",
        "Lows (beat+bass)": "lows_power",
        "Mids": "mids_power",
        "High": "high_power",
    }

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # protect against possible deactivate race condition
        self.audio = None
        self._audio_pending = False
        self._missed_events = set()
        self._pending_lock = threading.Lock()

    def activate(self, channel):
        _LOGGER.info("Activating AudioReactiveEffect.")
        super().activate(channel)

        if not self._ledfx.audio or id(AudioAnalysisSource) != id(
            self._ledfx.audio.__class__
        ):
            self._ledfx.audio = AudioAnalysisSource(
                self._ledfx, self._ledfx.config.audio.model_dump()
            )

        self.audio = self._ledfx.audio
        self._ledfx.audio.subscribe(self._audio_data_updated)

    def deactivate(self):
        _LOGGER.info("Deactivating AudioReactiveEffect.")

        self._active = False

        if self.audio:
            self.audio.unsubscribe(self._audio_data_updated)
        self.audio = None
        self.clear_melbank_freq_props()
        super().deactivate()

    def create_filter(self, alpha_decay, alpha_rise):
        # TODO: Since most effects reuse the same general filters it would be
        # nice for all that computation to be shared. This mean that shared
        # filters are needed, or if there is really just a small set of filters
        # that those get added to the Melbank input source instead.
        return ExpFilter(alpha_decay=alpha_decay, alpha_rise=alpha_rise)

    def _audio_data_updated(self):
        self.melbank.cache_clear()
        if self.lock.acquire(blocking=False):
            try:
                self._update_audio()
            finally:
                self.lock.release()
            return
        # The render thread holds the lock for a whole frame. Waiting for it
        # here would hold up every other effect's update behind this one, so
        # the render thread applies the newest results at the start of its
        # next frame instead, with the onsets and beats of the blocks between.
        audio = self.audio
        if audio is None:
            return
        with self._pending_lock:
            for name in _EVENT_FLAGS:
                if getattr(audio, name)():
                    self._missed_events.add(name)
            self._audio_pending = True

    def _update_audio(self):
        """Run audio_data_updated on the newest results; needs self.lock."""
        with self._pending_lock:
            missed, self._missed_events = self._missed_events, set()
            self._audio_pending = False
        if self.is_active:
            audio = self.audio
            self.audio_data_updated(
                _WithMissedEvents(audio, missed) if missed else audio
            )

    def _render(self):
        if self._audio_pending:
            with self.lock:
                if self._audio_pending:
                    self._update_audio()
        super()._render()

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updated. Should
        be implemented by subclasses
        """

    def clear_melbank_freq_props(self):
        """
        Clears the cached data for selecting and interpolating melbank.
        Almost all the properties used to build the melbank are cached
        to try and ease computational load.
        """

        for prop in [
            "_selected_melbank",
            "_melbank_min_idx",
            "_melbank_max_idx",
            "_input_mel_length",
        ]:
            if hasattr(self, prop):
                delattr(self, prop)

        self._melbank_interp_linspaces.cache_clear()

    @cached_property
    def _selected_melbank(self):
        return next(
            (
                i
                for i, x in enumerate(
                    self.audio.melbanks.melbanks_config.max_frequencies
                )
                if x >= self._virtual.frequency_range.max
            ),
            len(self.audio.melbanks.melbanks_config.max_frequencies),
        )

    @cached_property
    def _melbank_min_idx(self):
        return next(
            (
                idx
                for idx, freq in enumerate(
                    self.audio.melbanks.melbank_processors[
                        self._selected_melbank
                    ].melbank_frequencies
                )
                if freq >= self._virtual.frequency_range.min
            ),
            0,  # Default to 0 if no frequency >= min
        )

    @cached_property
    def _melbank_max_idx(self):
        max_idx = next(
            (
                idx
                for idx, freq in enumerate(
                    self.audio.melbanks.melbank_processors[
                        self._selected_melbank
                    ].melbank_frequencies
                )
                if freq >= self._virtual.frequency_range.max
            ),
            len(
                self.audio.melbanks.melbank_processors[
                    self._selected_melbank
                ].melbank_frequencies
            ),
        )
        # Ensure max_idx is always at least min_idx + 1 to prevent empty slices
        return max(max_idx, self._melbank_min_idx + 1)

    @cached_property
    def _input_mel_length(self):
        length = self._melbank_max_idx - self._melbank_min_idx
        # Ensure we have at least 1 frequency bin to avoid crashes
        if length < 1:
            _LOGGER.warning(
                "Frequency range %s-%sHz resulted in %s melbank bins. Adjusting to minimum of 1 bin. Consider using a wider frequency range.",
                self._virtual.frequency_range.min,
                self._virtual.frequency_range.max,
                length,
            )
            return 1
        return length

    @lru_cache(maxsize=16)  # noqa: B019
    def _melbank_interp_linspaces(self, size):
        old = np.linspace(0, 1, self._input_mel_length)
        new = np.linspace(0, 1, size)
        return (new, old)

    def melbank_no_nan(self, melbank):
        # Check for NaN values in the melbank array, replace with 0 in place
        # Difficult to determine why this happens, but it seems to be related to
        # the audio input device.
        # TODO: Investigate why NaNs are present in the melbank array for some people/devices
        if np.isnan(melbank).any():
            _LOGGER.warning(
                "NaN values detected in the melbank array and replaced with 0."
            )
            # Replace NaN values with 0
            np.nan_to_num(melbank, copy=False)

    @cache  # noqa: B019
    def melbank(self, filtered=False, size=0):
        """
        This little bit of code pulls together information from the effect's
        virtual (which controls the audio frequency range), and uses that
        to deliver the melbank, correctly selected and interpolated, to the effect

        size, int      : interpolate the melbank to the target size. value of 0 is no interpolation
        filtered, bool : melbank with smoothed attack and decay
        """
        self.audio.want(f"melbank{self._selected_melbank}")
        if filtered:
            melbank = self.audio.melbanks.melbanks_filtered[self._selected_melbank][
                self._melbank_min_idx : self._melbank_max_idx
            ]
        else:
            melbank = self.audio.melbanks.melbanks[self._selected_melbank][
                self._melbank_min_idx : self._melbank_max_idx
            ]

        self.melbank_no_nan(melbank)

        if size and (self._input_mel_length != size):
            return np.interp(*self._melbank_interp_linspaces(size), melbank)
        else:
            return melbank

    def melbank_thirds(self, **kwargs):
        """
        Returns the melbank split into three sections (unequal length)
        Useful for effects that use lows, mids, and highs

        Returns three arrays guaranteed to be safe for max/mean operations
        (empty arrays replaced with array containing 0.0)
        """
        melbank = self.melbank(**kwargs)
        mel_length = len(melbank)
        splits = tuple(int(i * mel_length) for i in [0.2, 0.5])

        thirds = np.split(melbank, splits)

        # Ensure each third has at least one element to prevent NaN from max/mean
        # on empty arrays (can happen with very narrow frequency ranges)
        return tuple(arr if len(arr) > 0 else np.array([0.0]) for arr in thirds)


register_enum_source(
    "audio_devices",
    # Lambdas look the methods up at call time, so tests that patch them still work.
    # {**...} widens dict[int, str] to the dict[object, str] the source declares.
    EnumSource(
        options=lambda: {**AudioInputSource.input_devices()},
        validate=lambda v: AudioInputSource.device_index_validator(v),
    ),
)
