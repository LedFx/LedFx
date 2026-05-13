import logging
import queue
import threading
import time
from collections import deque
from functools import cached_property, lru_cache

import aubio
import numpy as np
import samplerate
import sounddevice as sd
import voluptuous as vol

import ledfx.api.websocket
from ledfx.api.websocket import WEB_AUDIO_CLIENTS, WebAudioStream
from ledfx.config import save_config
from ledfx.effects import Effect
from ledfx.effects.math import ExpFilter
from ledfx.effects.melbank import FFT_SIZE, MIC_RATE, Melbanks
from ledfx.events import AudioDeviceChangeEvent, Event
from ledfx.sendspin import SENDSPIN_AVAILABLE
from ledfx.sendspin.config import is_always_on as is_sendspin_always_on

# Sendspin server configurations discovered or configured
SENDSPIN_SERVERS = {}

_LOGGER = logging.getLogger(__name__)

MIN_MIDI = 21
MAX_MIDI = 108


class AudioInputSource:
    _audio_stream_active = False
    _audio = None
    _stream = None
    _callbacks = []
    _audioWindowSize = 4
    _processed_audio_sample = None
    _volume = -90
    _volume_filter = ExpFilter(-90, alpha_decay=0.99, alpha_rise=0.99)
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
                    _LOGGER.info(
                        "Stopping audio stream before device list refresh..."
                    )
                    # Cache and clear inside lock (atomic operation)
                    stream_to_close = AudioInputSource._stream
                    AudioInputSource._stream = None
                    AudioInputSource._audio_stream_active = False

            # Close outside lock to avoid deadlock with audio callbacks
            if stream_to_close:
                try:
                    stream_to_close.stop()
                    stream_to_close.close()
                except Exception as e:
                    _LOGGER.warning(
                        "Error closing stream during refresh: %s", e
                    )

            try:
                # Force PortAudio to rescan devices by terminating and reinitializing
                sd._terminate()
                sd._initialize()
                # Clear the device list cache
                AudioInputSource._device_list_cache = None
                _LOGGER.info("Audio device list refreshed")
            except Exception as e:
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
        self._ledfx.config["audio"] = self._config
        try:
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
            return True
        except Exception as e:
            _LOGGER.warning("Failed to persist audio config: %s", e)
            return False

    def _update_device_config(self, device_idx):
        """
        Update device index and name in both local and central configs.

        Args:
            device_idx: The device index to set, or None to clear
        """
        self._config["audio_device"] = device_idx
        # Also persist the device name for cross-session recovery
        devices = self.input_devices()
        if device_idx is not None and device_idx in devices:
            self._config["audio_device_name"] = devices[device_idx]
        else:
            self._config["audio_device_name"] = ""
        # Persist to disk so recovered device survives restarts
        self._persist_config()

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

        # If no stream was active, nothing to recover
        if not was_active:
            _LOGGER.debug(
                "Device list changed but no audio stream was active - no recovery needed"
            )
            return

        # Try to find the previously active device by name
        # (device indices may have shifted after plug/unplug)
        with AudioInputSource._class_lock:
            last_device_name = AudioInputSource._last_device_name
            last_device_idx = AudioInputSource._last_active

        if not last_device_name:
            _LOGGER.warning(
                "Cannot recover audio stream: previous device name not tracked"
            )
            # Try to reactivate with current config anyway
            try:
                self.activate()
            except Exception as e:
                _LOGGER.error(
                    "Failed to reactivate audio stream after device change: %s",
                    e,
                )
            return

        # Find device at its new index
        _LOGGER.info(
            "Attempting to recover audio device '%s' (was at index %s)",
            last_device_name,
            last_device_idx,
        )
        found_idx = self.get_device_index_by_name(last_device_name)

        if found_idx == -1:
            _LOGGER.warning(
                "Previously active device '%s' no longer available after device list change. "
                "Will use default device.",
                last_device_name,
            )
            # Clear the stored device info since it's gone
            with AudioInputSource._class_lock:
                AudioInputSource._last_device_name = None
                AudioInputSource._last_active = None

            # Use default device logic (prefers loopback of default output, then default input)
            fallback_idx = AudioInputSource.default_device_index()
            if fallback_idx is not None:
                _LOGGER.info("Using fallback device at index %s", fallback_idx)
                self._update_device_config(fallback_idx)
            else:
                # No valid devices at all - clear config to trigger validator
                _LOGGER.warning("No fallback device available")
                self._update_device_config(None)
        else:
            current_config_idx = self._config.get("audio_device", -1)
            if found_idx != current_config_idx:
                _LOGGER.info(
                    "Device list changed: '%s' moved from index %s to %s",
                    last_device_name,
                    current_config_idx,
                    found_idx,
                )
            else:
                _LOGGER.info(
                    "Device list changed: '%s' still at index %s",
                    last_device_name,
                    found_idx,
                )

            # Always update config with found index to ensure consistency
            self._update_device_config(found_idx)

        # Reactivate the stream with the updated configuration
        try:
            _LOGGER.info("Reactivating audio stream after device list refresh")
            self.activate()
        except Exception as e:
            _LOGGER.error(
                "Failed to reactivate audio stream after device change: %s", e
            )

    @staticmethod
    def device_index_validator(val):
        """
        Validates device index in case the saved setting is no longer valid.
        Accepts None (schema default) and resolves to the default device.
        """
        if val is not None and val in AudioInputSource.valid_device_indexes():
            return val
        else:
            return AudioInputSource.default_device_index()

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
            default_output_device_name = device_list[
                default_output_device_idx
            ]["name"]

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
    @property
    def AUDIO_CONFIG_SCHEMA():
        AudioInputSource.valid_device_indexes()
        AudioInputSource.input_devices()
        return vol.Schema(
            {
                vol.Optional("sample_rate", default=60): int,
                vol.Optional("mic_rate", default=44100): int,
                vol.Optional("fft_size", default=FFT_SIZE): int,
                vol.Optional("min_volume", default=0.2): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                ),
                vol.Optional(
                    "audio_device", default=None
                ): AudioInputSource.device_index_validator,
                vol.Optional("audio_device_name", default=""): str,
                vol.Optional(
                    "delay_ms",
                    default=0,
                    description="Add a delay to LedFx's output to sync with your audio. Useful for Bluetooth devices which typically have a short audio lag.",
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5000)),
            },
            extra=vol.ALLOW_EXTRA,
        )

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
        saved_name = self._config.get("audio_device_name", "")
        saved_idx = self._config.get("audio_device")

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
            self._config["audio_device"] = found_idx
            # Persist the corrected index
            self._persist_config()
            return

        # Device not found by name at all — reset to default so we don't
        # silently open a different device that now occupies the stale index.
        default_idx = self.default_device_index()
        _LOGGER.warning(
            "Saved audio device '%s' not found in current device list. "
            "Resetting to default device (index %s).",
            saved_name,
            default_idx,
        )
        self._config["audio_device"] = default_idx
        self._config["audio_device_name"] = ""
        # Clear runtime tracking so hotplug won't try to recover the old device
        with AudioInputSource._class_lock:
            AudioInputSource._last_device_name = None
            AudioInputSource._last_active = None
        self._persist_config()

    def update_config(self, config):
        """Deactivate the audio, update the config, the reactivate"""
        new_config = self.AUDIO_CONFIG_SCHEMA.fget()(config)

        # Determine if the audio device is actually changing.  For Sendspin
        # always-on, avoid a destructive deactivate/reactivate cycle when
        # only non-pipeline settings changed (e.g. min_volume).
        has_old_config = hasattr(self, "_config")
        old_device = (
            self._config.get("audio_device") if has_old_config else None
        )
        new_device = new_config.get("audio_device")
        device_changing = old_device != new_device

        # Pipeline-affecting keys require rebuilding internal audio objects
        # (delay_queue, _raw_audio_sample, _phase_vocoder, etc.) even when
        # the audio stream should stay active.
        _PIPELINE_KEYS = ("delay_ms", "sample_rate", "fft_size")
        pipeline_changing = has_old_config and any(
            self._config.get(k) != new_config.get(k) for k in _PIPELINE_KEYS
        )

        if AudioInputSource._audio_stream_active:
            if (
                device_changing
                or pipeline_changing
                or not self._should_always_keep_active()
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
        should_always_on = self._should_always_keep_active()
        if len(self._callbacks) != 0 or should_always_on:
            if not AudioInputSource._audio_stream_active:
                self.activate()

        # Check if device changed and fire event if needed
        with AudioInputSource._class_lock:
            if last_active != AudioInputSource._last_active:
                self._ledfx.events.fire_event(
                    AudioDeviceChangeEvent(
                        self.input_devices()[self._config["audio_device"]]
                    )
                )

        self._ledfx.config["audio"] = self._config

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
                _LOGGER.critical(
                    "Sounddevice error: %s. Shutting down.", Error
                )
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
        device_idx = self._config["audio_device"]

        if device_idx not in valid_device_indexes:
            # Configured device is invalid — resolve the default now
            default_device = self.default_device_index()
            if device_idx is not None and device_idx > max(
                valid_device_indexes
            ):
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

        # Setup a pre-emphasis filter to balance the input volume of lows to highs
        self.pre_emphasis = aubio.digital_filter(3)
        # depending on the coeffs type, we need to use different pre_emphasis values to make em work better. allegedly.
        selected_coeff = self._ledfx.config["melbanks"]["coeffs_type"]
        if selected_coeff == "matt_mel":
            _LOGGER.debug("Using matt_mel settings for pre-emphasis.")
            self.pre_emphasis.set_biquad(
                0.8268, -1.6536, 0.8268, -1.6536, 0.6536
            )
        elif selected_coeff == "scott_mel":
            _LOGGER.debug("Using scott_mel settings for pre-emphasis.")
            self.pre_emphasis.set_biquad(
                1.3662, -1.9256, 0.5621, -1.9256, 0.9283
            )
        else:
            _LOGGER.debug("Using generic settings for pre-emphasis")
            self.pre_emphasis.set_biquad(
                0.85870, -1.71740, 0.85870, -1.71605, 0.71874
            )

        freq_domain_length = (self._config["fft_size"] // 2) + 1

        self._raw_audio_sample = np.zeros(
            MIC_RATE // self._config["sample_rate"],
            dtype=np.float32,
        )

        # Setup the phase vocoder to perform a windowed FFT
        self._phase_vocoder = aubio.pvoc(
            self._config["fft_size"],
            MIC_RATE // self._config["sample_rate"],
        )
        self._frequency_domain_null = aubio.cvec(self._config["fft_size"])
        self._frequency_domain = self._frequency_domain_null
        self._frequency_domain_x = np.linspace(
            0,
            MIC_RATE,
            freq_domain_length,
        )

        samples_to_delay = int(
            0.001 * self._config["delay_ms"] * self._config["sample_rate"]
        )
        if samples_to_delay:
            self.delay_queue = queue.Queue(maxsize=samples_to_delay)
        else:
            self.delay_queue = None

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
                ledfx.api.websocket.ACTIVE_AUDIO_STREAM = (
                    AudioInputSource._stream
                ) = WebAudioStream(
                    device["client"], self._audio_sample_callback
                )
            elif (
                SENDSPIN_AVAILABLE
                and hostapis[device["hostapi"]]["name"] == "SENDSPIN"
            ):
                from ledfx.sendspin.stream import SendspinAudioStream

                _LOGGER.debug(
                    "Opening SendspinAudioStream for '%s'",
                    device["name"],
                )
                AudioInputSource._stream = SendspinAudioStream(
                    device["sendspin_config"],
                    self._audio_sample_callback,
                    instance_id=self._ledfx.config.get("instance_id", ""),
                )
            else:
                AudioInputSource._stream = self._audio.InputStream(
                    samplerate=int(device["default_samplerate"]),
                    device=device_idx,
                    callback=self._audio_sample_callback,
                    dtype=np.float32,
                    latency="low",
                    blocksize=int(
                        device["default_samplerate"]
                        / self._config["sample_rate"]
                    ),
                    # only pass channels if we set it to something other than None
                    **({"channels": channels} if channels is not None else {}),
                )

            self.resampler = samplerate.Resampler("sinc_fastest", channels=1)

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
                except Exception as reinit_err:
                    _LOGGER.warning("PortAudio reinit failed: %s", reinit_err)
                    return False
            try:
                open_audio_stream(dev_idx)
                update_device_tracking(dev_idx)
                return True
            except (sd.PortAudioError, OSError) as err:
                _LOGGER.warning("Audio device [%s] failed: %s", dev_idx, err)
                return False

        def persist_device_name_if_needed():
            """
            Ensure device index and name are persisted for cross-session
            recovery.  Also handles seamless upgrade from legacy configs
            (index-only) and fallback-open scenarios where the actual
            device differs from the configured one.
            """
            with AudioInputSource._class_lock:
                current_name = AudioInputSource._last_device_name
                current_idx = AudioInputSource._last_active

            if not current_name or current_idx is None:
                return

            name_changed = (
                self._config.get("audio_device_name", "") != current_name
            )
            idx_changed = self._config.get("audio_device") != current_idx

            if name_changed or idx_changed:
                self._config["audio_device"] = current_idx
                self._config["audio_device_name"] = current_name
                if self._persist_config():
                    _LOGGER.info(
                        "Persisted audio device '%s' (index %s) for cross-session recovery",
                        current_name,
                        current_idx,
                    )

        # Audio device startup sequence:
        # PortAudio's internal state may be poisoned at startup
        # (e.g. WDM-KS devices interfere during initial enumeration).
        # Recovery: try configured → reinit + retry configured → reinit + fallback
        if try_open_device(device_idx):
            persist_device_name_if_needed()
            return

        _LOGGER.info(
            "Reinitializing PortAudio and retrying device [%s]...", device_idx
        )
        if try_open_device(device_idx, reinit=True):
            _LOGGER.info(
                "Audio device [%s] opened successfully after PortAudio reinit.",
                device_idx,
            )
            persist_device_name_if_needed()
            return

        fallback_device = self.default_device_index()
        _LOGGER.info("Falling back to default device [%s]...", fallback_device)
        if fallback_device is not None and try_open_device(
            fallback_device, reinit=True
        ):
            persist_device_name_if_needed()
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
        sendspin_always_on = self._ledfx.config.get(
            "sendspin_always_on", False
        )
        if not sendspin_always_on:
            return False
        device_idx = (
            self._config.get("audio_device")
            if hasattr(self, "_config")
            else None
        )
        result = is_sendspin_always_on(
            device_idx,
            self.query_devices,
            self.query_hostapis,
        )
        return result

    def subscribe(self, callback):
        """Registers a callback with the input source"""
        self._callbacks.append(callback)
        if (
            len(self._callbacks) > 0
            and not AudioInputSource._audio_stream_active
        ):
            self.activate()
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def unsubscribe(self, callback):
        """Unregisters a callback with the input source"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
        if self._should_always_keep_active():
            _LOGGER.debug(
                "Sendspin always-on active, skipping deactivate timer"
            )
            return
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
            if device_name in value:
                # Prefer longer matches to find the most specific device
                if len(value) > best_match_len:
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
        # time_start = time.time()
        # self._raw_audio_sample = np.frombuffer(in_data, dtype=np.float32)
        raw_sample = np.frombuffer(in_data, dtype=np.float32)

        in_sample_len = len(raw_sample)
        out_sample_len = MIC_RATE // self._config["sample_rate"]

        if in_sample_len != out_sample_len:
            # Simple resampling
            processed_audio_sample = self.resampler.process(
                raw_sample,
                # MIC_RATE / self._stream.samplerate
                out_sample_len / in_sample_len,
                # end_of_input=True
            )
        else:
            processed_audio_sample = raw_sample

        if len(processed_audio_sample) != out_sample_len:
            _LOGGER.debug(
                "Discarded malformed audio frame - %s samples, expected %s",
                len(processed_audio_sample),
                out_sample_len,
            )
            return

        # handle delaying the audio with the queue
        if self.delay_queue:
            try:
                self.delay_queue.put_nowait(processed_audio_sample)
            except queue.Full:
                self._raw_audio_sample = self.delay_queue.get_nowait()
                self.delay_queue.put_nowait(processed_audio_sample)
                self.pre_process_audio()
                self._invalidate_caches()
                self._invoke_callbacks()
        else:
            self._raw_audio_sample = processed_audio_sample
            self.pre_process_audio()
            self._invalidate_caches()
            self._invoke_callbacks()

        # print(f"Core Audio Processing Latency {round(time.time()-time_start, 3)} s")
        # return self._raw_audio_sample

    def _invoke_callbacks(self):
        """Notifies all clients of the new data"""
        for callback in self._callbacks:
            callback()

    def _invalidate_caches(self):
        """Invalidates the necessary cache"""
        pass

    def pre_process_audio(self):
        """
        Pre-processing stage that will run on every sample, only
        core functionality that will be used for every audio effect
        should be done here. Everything else should be deferred until
        queried by an effect.
        """
        # clean up nans that have been mysteriously appearing..
        self._raw_audio_sample[np.isnan(self._raw_audio_sample)] = 0

        # Calculate the current volume for silence detection
        self._volume = 1 + aubio.db_spl(self._raw_audio_sample) / 100
        self._volume = max(0, min(1, self._volume))
        self._volume_filter.update(self._volume)

        # Calculate the frequency domain from the filtered data and
        # force all zeros when below the volume threshold
        if self._volume_filter.value > self._config["min_volume"]:
            self._processed_audio_sample = self._raw_audio_sample

            # Perform a pre-emphasis to balance the highs and lows
            if self.pre_emphasis:
                self._processed_audio_sample = self.pre_emphasis(
                    self._raw_audio_sample
                )

            # Pass into the phase vocoder to get a windowed FFT
            self._frequency_domain = self._phase_vocoder(
                self._processed_audio_sample
            )
        else:
            self._frequency_domain = self._frequency_domain_null

    def audio_sample(self, raw=False):
        """Returns the raw audio sample"""

        if raw:
            return self._raw_audio_sample
        return self._processed_audio_sample

    def frequency_domain(self):
        return self._frequency_domain

    def volume(self, filtered=True):
        if filtered:
            return self._volume_filter.value
        return self._volume


class AudioAnalysisSource(AudioInputSource):
    # https://aubio.org/doc/latest/pitch_8h.html
    PITCH_METHODS = [
        "yinfft",
        "yin",
        "yinfast",
        # mcomb and fcomb appears to just explode something deeep in the aubio code, no logs, no errors, it just dies.
        # "mcomb",
        # "fcomb",
        "schmitt",
        "specacf",
    ]
    # https://aubio.org/doc/latest/specdesc_8h.html
    ONSET_METHODS = [
        "energy",
        "hfc",
        "complex",
        "phase",
        "wphase",
        "specdiff",
        "kl",
        "mkl",
        "specflux",
    ]
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "pitch_method",
                default="yinfft",
                description="Method to detect pitch",
            ): vol.In(PITCH_METHODS),
            vol.Optional("tempo_method", default="default"): str,
            vol.Optional(
                "onset_method",
                default="hfc",
                description="Method used to detect onsets",
            ): vol.In(ONSET_METHODS),
            vol.Optional(
                "pitch_tolerance",
                default=0.8,
                description="Pitch detection tolerance",
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2)),
        },
        extra=vol.ALLOW_EXTRA,
    )

    # some frequency constants
    # beat, bass, mids, high
    freq_max_mels = [
        100,
        250,
        3000,
        10000,
    ]

    def __init__(self, ledfx, config):
        config = self.CONFIG_SCHEMA(config)
        super().__init__(ledfx, config)
        self.initialise_analysis()

        # Subscribe functions to be run on every frame of audio
        self.subscribe(self.melbanks)
        self.subscribe(self.pitch)
        self.subscribe(self.onset)
        self.subscribe(self.bar_oscillator)
        self.subscribe(self.volume_beat_now)
        self.subscribe(self.freq_power)

        # ensure any new analysis callbacks are above this line
        self._subscriber_threshold = len(self._callbacks)

    def initialise_analysis(self):
        # melbanks
        if not hasattr(self, "melbanks"):
            self.melbanks = Melbanks(
                self._ledfx, self, self._ledfx.config.get("melbanks", {})
            )

        fft_params = (
            self._config["fft_size"],
            MIC_RATE // self._config["sample_rate"],
            MIC_RATE,
        )

        # pitch, tempo, onset
        self._tempo = aubio.tempo(self._config["tempo_method"], *fft_params)
        self._onset = aubio.onset(self._config["onset_method"], *fft_params)
        self._pitch = aubio.pitch(self._config["pitch_method"], *fft_params)
        self._pitch.set_unit("midi")
        self._pitch.set_tolerance(self._config["pitch_tolerance"])

        # bar oscillator
        self.beat_counter = 0

        # beat oscillator
        self.beat_timestamp = time.time()
        self.beat_period = 2

        # freq power
        self.freq_power_raw = np.zeros(len(self.freq_max_mels))
        self.freq_power_filter = ExpFilter(
            np.zeros(len(self.freq_max_mels)), alpha_decay=0.2, alpha_rise=0.97
        )
        self.freq_mel_indexes = []

        for freq in self.freq_max_mels:
            assert self.melbanks.melbanks_config["max_frequencies"][2] >= freq

            self.freq_mel_indexes.append(
                next(
                    (
                        i
                        for i, f in enumerate(
                            self.melbanks.melbank_processors[
                                2
                            ].melbank_frequencies
                        )
                        if f > freq
                    ),
                    len(
                        self.melbanks.melbank_processors[2].melbank_frequencies
                    ),
                )
            )

        # volume based beat detection
        self.beat_max_mel_index = next(
            (
                i - 1
                for i, f in enumerate(
                    self.melbanks.melbank_processors[0].melbank_frequencies
                )
                if f > self.freq_max_mels[0]
            ),
            self.melbanks.melbank_processors[0].melbank_frequencies[-1],
        )

        self.beat_min_percent_diff = 0.5
        self.beat_min_time_since = 0.1
        self.beat_min_amplitude = 0.5
        self.beat_power_history_len = int(self._config["sample_rate"] * 0.2)

        self.beat_prev_time = time.time()
        self.beat_power_history = deque(maxlen=self.beat_power_history_len)

    def update_config(self, config):
        validated_config = self.CONFIG_SCHEMA(config)
        super().update_config(validated_config)
        self.initialise_analysis()

    def _invalidate_caches(self):
        """Invalidates the cache for all melbank related data"""
        super()._invalidate_caches()

        self.pitch.cache_clear()
        self.onset.cache_clear()
        self.bpm_beat_now.cache_clear()
        self.volume_beat_now.cache_clear()
        self.bar_oscillator.cache_clear()

    @lru_cache(maxsize=None)
    def pitch(self):
        # If our audio handler is returning null, then we just return 0 for midi_value and wait for the device starts sending audio.
        try:
            return self._pitch(self.audio_sample(raw=True))[0]
        except ValueError as e:
            _LOGGER.warning("%s", e)
            return 0

    @lru_cache(maxsize=None)
    def onset(self):
        try:
            return bool(self._onset(self.audio_sample(raw=True))[0])
        except ValueError as e:
            _LOGGER.warning("%s", e)
            return 0

    @lru_cache(maxsize=None)
    def bpm_beat_now(self):
        """
        Returns True if a beat is expected now based on BPM data
        """
        try:
            return bool(self._tempo(self.audio_sample(raw=True))[0])
        except ValueError as e:
            _LOGGER.warning("%s", e)
            return False

    @lru_cache(maxsize=None)
    def volume_beat_now(self):
        """
        Returns True if a beat is expected now based on volume of the beat freq region
        This algorithm is a bit weird, but works quite nicely.
        I've tried my best to optimise it from the original
        implementation in systematic_leds
        """

        time_now = time.time()
        melbank = self.melbanks.melbanks[0][: self.beat_max_mel_index]
        beat_power = np.sum(melbank)
        melbank_max = np.max(melbank)

        # calculates the % difference of the first value of the channel to the average for the channel
        if sum(self.beat_power_history) > 0:
            difference = (
                beat_power
                * self.beat_power_history_len
                / sum(self.beat_power_history)
                - 1
            )
        else:
            difference = 0

        self.beat_power_history.appendleft(beat_power)

        if (
            difference >= self.beat_min_percent_diff
            and melbank_max >= self.beat_min_amplitude
            and time_now - self.beat_prev_time > self.beat_min_time_since
        ):
            self.beat_prev_time = time_now
            return True
        else:
            return False

    def freq_power(self):
        # hard coded this bc i'm tired and it'll run faster

        melbank = self.melbanks.melbanks[2]

        self.freq_power_raw[0] = np.average(
            melbank[: self.freq_mel_indexes[0]]
        )
        self.freq_power_raw[1] = np.average(
            melbank[self.freq_mel_indexes[0] : self.freq_mel_indexes[1]]
        )
        self.freq_power_raw[2] = np.average(
            melbank[self.freq_mel_indexes[1] : self.freq_mel_indexes[2]]
        )
        self.freq_power_raw[3] = np.average(
            melbank[self.freq_mel_indexes[2] : self.freq_mel_indexes[3]]
        )
        np.minimum(self.freq_power_raw, 1, out=self.freq_power_raw)
        self.freq_power_filter.update(self.freq_power_raw)

    def get_freq_power(self, i, filtered=True):
        if filtered:
            value = self.freq_power_filter.value[i]
        else:
            value = self.freq_power_raw[i]

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

    @lru_cache(maxsize=None)
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
        # update tempo and oscillator
        # print(self._tempo.get_delay_s())
        if self.bpm_beat_now():
            self.beat_counter = (self.beat_counter + 1) % 4
            self.beat_period = self._tempo.get_period_s()
            # print("beat at:", self._tempo.get_delay_s())
            self.beat_timestamp = time.time()
            oscillator = self.beat_counter
        else:
            time_since_beat = time.time() - self.beat_timestamp
            oscillator = (
                1 - (self.beat_period - time_since_beat) / self.beat_period
            ) + self.beat_counter
            # ensure it's between [0 and 4). useful when audio cuts
            oscillator = oscillator % 4
        return oscillator

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


@Effect.no_registration
class AudioReactiveEffect(Effect):
    """
    Base for audio reactive effects. This really just subscribes
    to the melbank input source and forwards input along to the
    subclasses. This can be expanded to do the common r/g/b filters.
    """

    # this can be used by inheriting classes for power func selection in schema
    # see magnitude or scan effect for examples
    POWER_FUNCS_MAPPING = {
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

    def activate(self, channel):
        _LOGGER.info("Activating AudioReactiveEffect.")
        super().activate(channel)

        if not self._ledfx.audio or id(AudioAnalysisSource) != id(
            self._ledfx.audio.__class__
        ):
            self._ledfx.audio = AudioAnalysisSource(
                self._ledfx, self._ledfx.config.get("audio", {})
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
        with self.lock:
            if self.is_active:
                self.audio_data_updated(self.audio)

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updated. Should
        be implemented by subclasses
        """
        pass

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
                    self.audio.melbanks.melbanks_config["max_frequencies"]
                )
                if x >= self._virtual.frequency_range.max
            ),
            len(self.audio.melbanks.melbanks_config["max_frequencies"]),
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

    @lru_cache(maxsize=16)
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

    @lru_cache(maxsize=None)
    def melbank(self, filtered=False, size=0):
        """
        This little bit of code pulls together information from the effect's
        virtual (which controls the audio frequency range), and uses that
        to deliver the melbank, correctly selected and interpolated, to the effect

        size, int      : interpolate the melbank to the target size. value of 0 is no interpolation
        filtered, bool : melbank with smoothed attack and decay
        """
        if filtered:
            melbank = self.audio.melbanks.melbanks_filtered[
                self._selected_melbank
            ][self._melbank_min_idx : self._melbank_max_idx]
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
        splits = tuple(map(lambda i: int(i * mel_length), [0.2, 0.5]))

        thirds = np.split(melbank, splits)

        # Ensure each third has at least one element to prevent NaN from max/mean
        # on empty arrays (can happen with very narrow frequency ranges)
        return tuple(
            arr if len(arr) > 0 else np.array([0.0]) for arr in thirds
        )
