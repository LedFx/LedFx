import logging
import queue
import threading
import time
from collections import defaultdict, deque
from functools import cached_property, lru_cache
from time import perf_counter

import aubio
import numpy as np
import samplerate
import sounddevice as sd
import voluptuous as vol

import ledfx.api.websocket
from ledfx.api.websocket import WEB_AUDIO_CLIENTS, WebAudioStream
from ledfx.effects import Effect
from ledfx.effects.math import ExpFilter
from ledfx.effects.melbank import (
    DEFAULT_INPUT_SAMPLE_RATE,
    Melbanks,
)
from ledfx.events import AudioDeviceChangeEvent, Event

_LOGGER = logging.getLogger(__name__)

MIN_MIDI = 21
MAX_MIDI = 108

# Multi-FFT Analysis Presets
# Each preset defines (fft_size, hop_size) tuples for different analysis types
# Format: {preset_name: {analysis_type: (fft_size, hop_size)}}
FFT_PRESETS = {
    "balanced": {
        "onset": (1024, 256),
        "tempo": (2048, 367),
        "pitch": (4096, 367),
        "melbanks": [(1024, 256), (2048, 367), (4096, 367)],
    },
    "low_latency": {
        "onset": (512, 128),
        "tempo": (1024, 183),
        "pitch": (2048, 183),
        "melbanks": [(512, 128), (1024, 183), (2048, 183)],
    },
    "high_precision": {
        "onset": (2048, 512),
        "tempo": (4096, 734),
        "pitch": (8192, 734),
        "melbanks": [(2048, 512), (4096, 734), (8192, 734)],
    },
}


def _validate_fft_hop_pair(fft_size, hop_size, name="FFT config"):
    """
    Validate FFT size and hop size parameters.

    Args:
        fft_size: FFT window size, must be a positive power of 2
        hop_size: Hop size (samples per frame), must be positive and <= fft_size
        name: Name of the configuration for error messages

    Returns:
        tuple: (fft_size, hop_size) if valid

    Raises:
        vol.Invalid: If validation fails
    """
    if fft_size <= 0 or (fft_size & (fft_size - 1)) != 0:
        raise vol.Invalid(
            f"{name}: fft_size must be a positive power of 2, got {fft_size}"
        )
    if hop_size <= 0:
        raise vol.Invalid(f"{name}: hop_size must be positive, got {hop_size}")
    if hop_size > fft_size:
        raise vol.Invalid(
            f"{name}: hop_size ({hop_size}) must be <= fft_size ({fft_size})"
        )
    return (fft_size, hop_size)


# Validate all presets on module load
for preset_name, preset_config in FFT_PRESETS.items():
    for analysis_type, config in preset_config.items():
        if analysis_type == "melbanks":
            for i, (fft, hop) in enumerate(config):
                _validate_fft_hop_pair(
                    fft, hop, f"Preset '{preset_name}' melbank {i}"
                )
        else:
            fft, hop = config
            _validate_fft_hop_pair(
                fft, hop, f"Preset '{preset_name}' {analysis_type}"
            )


class AudioInputSource:
    _audio_stream_active = False
    _audio = None
    _stream = None
    _callbacks = []
    _audioWindowSize = 4
    _volume = -90
    _volume_filter = ExpFilter(-90, alpha_decay=0.99, alpha_rise=0.99)
    _subscriber_threshold = 0
    _timer = None
    _last_active = None
    _last_callback_time = None
    _callback_idle_logged = False

    @staticmethod
    def device_index_validator(val):
        """
        Validates device index in case the saved setting is no longer valid
        """
        if val in AudioInputSource.valid_device_indexes():
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
                f"Looking for audio loopback device for default output device at index {default_output_device_idx}: {default_output_device_name}"
            )
            for device_index, device in enumerate(device_list):
                # sometimes the audio device name string is truncated, so we need to match what we have and Loopback but otherwise be sloppy
                if (
                    default_output_device_name in device["name"]
                    and "[Loopback]" in device["name"]
                ):
                    # Return the loopback device index
                    _LOGGER.debug(
                        f"Found audio loopback device for default output device at index {device_index}: {device['name']}"
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
                    f"No audio loopback device found for default output device. Using default input device at index {default_input_device_idx}: {device_list[default_input_device_idx]['name']}"
                )
                return default_input_device_idx
            else:
                # Return the first valid input device index if we can't find a valid default input device
                if len(valid_device_indexes) > 0:
                    first_valid_idx = next(iter(valid_device_indexes))
                    _LOGGER.debug(
                        f"No valid default audio input device found. Using first valid input device at index {first_valid_idx}: {device_list[first_valid_idx]['name']}"
                    )
                    return first_valid_idx

    @staticmethod
    def query_hostapis():
        return sd.query_hostapis() + ({"name": "WEB AUDIO"},)

    @staticmethod
    def query_devices():
        return sd.query_devices() + tuple(
            {
                "hostapi": len(AudioInputSource.query_hostapis()) - 1,
                "name": f"{client}",
                "max_input_channels": 1,
                "client": client,
            }
            for client in WEB_AUDIO_CLIENTS
        )

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
        default_device_index = AudioInputSource.default_device_index()
        AudioInputSource.valid_device_indexes()
        AudioInputSource.input_devices()

        # Simple list schema for JSON schema conversion
        # Actual validation happens in update_config via _validate_fft_override
        fft_override_schema = vol.All([int, int], vol.Length(min=2, max=2))

        return vol.Schema(
            {
                vol.Optional("analysis_fps", default=120): int,
                vol.Optional(
                    "input_sample_rate", default=DEFAULT_INPUT_SAMPLE_RATE
                ): int,
                vol.Optional("min_volume", default=0.2): vol.All(
                    vol.Coerce(float), vol.Range(min=0.0, max=1.0)
                ),
                vol.Optional(
                    "audio_device", default=default_device_index
                ): AudioInputSource.device_index_validator,
                vol.Optional(
                    "delay_ms",
                    default=0,
                    description="Add a delay to LedFx's output to sync with your audio. Useful for Bluetooth devices which typically have a short audio lag.",
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5000)),
                # Multi-FFT configuration
                vol.Optional(
                    "fft_preset",
                    default="balanced",
                    description="Preset configuration for FFT sizes across analysis types. Options: balanced (default), low_latency, high_precision.",
                ): vol.In(list(FFT_PRESETS.keys())),
                vol.Optional(
                    "fft_tempo_override",
                    description="Override tempo analysis FFT config as [fft_size, hop_size]. Example: [2048, 367]",
                ): fft_override_schema,
                vol.Optional(
                    "fft_onset_override",
                    description="Override onset detection FFT config as [fft_size, hop_size]. Example: [1024, 256]",
                ): fft_override_schema,
                vol.Optional(
                    "fft_pitch_override",
                    description="Override pitch detection FFT config as [fft_size, hop_size]. Example: [4096, 367]",
                ): fft_override_schema,
                vol.Optional(
                    "melbank_fft_mode",
                    default="tiered",
                    description="Method for assigning FFT sizes to melbanks. 'tiered' uses preset configs, 'formula' calculates based on max frequency.",
                ): vol.In(["tiered", "formula"]),
            },
            extra=vol.ALLOW_EXTRA,
        )

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self.lock = threading.Lock()
        # We must not inherit legacy _callbacks from prior instances
        self._callbacks = []
        self.stream_sample_rate = None
        self.hop_size = None
        self._analysis_fps = None
        self.update_config(config)

        def shutdown_event(e):
            # We give the rest of LedFx a second to shutdown before we deactivate the audio subsystem.
            # This is to prevent LedFx hanging on shutdown if the audio subsystem is still running while
            # effects are being unloaded. This is a bit hacky but it works.
            self._timer = threading.Timer(0.5, self.check_and_deactivate)
            self._timer.start()

        self._ledfx.events.add_listener(shutdown_event, Event.LEDFX_SHUTDOWN)

    def update_config(self, config):
        """Deactivate the audio, update the config, the reactivate"""
        if self._audio_stream_active:
            self.deactivate()

        self._config = self.AUDIO_CONFIG_SCHEMA.fget()(config)
        self._validate_audio_config()

        # Use the configured input sample rate until the device reports a real value
        self._rebuild_analysis_graph(self._config["input_sample_rate"])

        # cache up last active and lets see if it changes
        # Read _last_active with lock protection
        with self.lock:
            last_active = self._last_active

        # Activate outside the lock to avoid deadlock
        if len(self._callbacks) != 0:
            self.activate()

        # Check if device changed and fire event if needed
        with self.lock:
            if last_active != self._last_active:
                self._ledfx.events.fire_event(
                    AudioDeviceChangeEvent(
                        self.input_devices()[self._config["audio_device"]]
                    )
                )

        self._ledfx.config["audio"] = self._config

    # TODO: Add to config migrator
    def _validate_audio_config(self):
        analysis_fps_setting = self._config["analysis_fps"]
        input_sample_rate = self._config["input_sample_rate"]

        if analysis_fps_setting <= 0:
            raise vol.Invalid("audio.analysis_fps must be greater than zero")
        if input_sample_rate <= 0:
            raise vol.Invalid(
                "audio.input_sample_rate must be greater than zero"
            )

        # Validate FFT overrides if provided
        for override_key in [
            "fft_tempo_override",
            "fft_onset_override",
            "fft_pitch_override",
        ]:
            if (
                override_key in self._config
                and self._config[override_key] is not None
            ):
                override_value = self._config[override_key]
                if (
                    not isinstance(override_value, (list, tuple))
                    or len(override_value) != 2
                ):
                    raise vol.Invalid(
                        f"{override_key} must be a list/tuple of [fft_size, hop_size]"
                    )
                try:
                    fft_size, hop_size = int(override_value[0]), int(
                        override_value[1]
                    )
                    # This will raise vol.Invalid if the pair is invalid
                    _validate_fft_hop_pair(fft_size, hop_size, override_key)
                    # Store as tuple for consistency
                    self._config[override_key] = (fft_size, hop_size)
                except (ValueError, TypeError) as e:
                    raise vol.Invalid(
                        f"{override_key} must contain valid integers: {e}"
                    )

    def _rebuild_analysis_graph(self, stream_sample_rate):
        stream_sample_rate = int(stream_sample_rate)
        if stream_sample_rate <= 0:
            return

        self.stream_sample_rate = stream_sample_rate
        self.fft_size = self._config["fft_size"]
        self._analysis_fps = self._config["analysis_fps"]

        # hop size equals samples per analysis frame (frames per second).
        base_hop = max(
            1, int(round(self.stream_sample_rate / self._analysis_fps))
        )
        if base_hop > self.fft_size:
            _LOGGER.warning(
                "Configured hop size (%s) exceeds fft_size (%s); clamping to fft_size",
                base_hop,
                self.fft_size,
            )
            base_hop = self.fft_size

    def _rebuild_analysis_graph(self, stream_sample_rate):
        """
        Build multi-FFT analysis infrastructure with independent resamplers.

        Resampling Strategy:
        - Each unique hop size gets its own dedicated samplerate.Resampler instance
        - Resamplers maintain continuous state across frames for clean streaming audio
        - Input audio is resampled once per hop size, then used for all FFTs with that hop size
        - This avoids zero-padding artifacts while allowing optimal analysis rates
        - Synchronization is maintained via consistent resampling ratios calculated from stream rate

        Multi-FFT Architecture:
        - Different analyses can use different hop sizes for optimal performance:
          * Onset detection: Small hop (e.g., 256) for low latency
          * Tempo tracking: Medium hop (e.g., 367) for stability
          * Pitch detection: Larger FFT window, medium hop for precision
        - All analyses using the same hop size share the resampled audio buffer
        - No cross-frame caching - FFTs recomputed fresh each frame

        Note: This method only updates internal state based on stream parameters.
        It does NOT trigger analysis reinitialization - that's handled separately
        by __init__ and update_config.
        """
        stream_sample_rate = int(stream_sample_rate)
        if stream_sample_rate <= 0:
            return

        self.stream_sample_rate = stream_sample_rate
        self._analysis_fps = self._config["analysis_fps"]

        # Calculate base hop size for reference (samples per frame at stream rate)
        # This is the input buffer size we'll receive from the audio callback
        self.input_hop_size = max(
            1, int(round(self.stream_sample_rate / self._analysis_fps))
        )

        # Multi-FFT infrastructure
        # Dictionary of phase vocoders keyed by (fft_size, hop_size) tuple
        self._phase_vocoders = {}

        # Dictionary of frequency domain results keyed by (fft_size, hop_size) tuple
        self._frequency_domains = {}

        # Dictionary of null (zero) frequency domains for silence
        self._frequency_domain_nulls = {}

        # Independent resamplers - one per unique hop size
        # Key: hop_size, Value: samplerate.Resampler instance
        self._resamplers = {}

        # Resampled audio buffers - one per unique hop size
        # Key: hop_size, Value: np.array of resampled audio
        self._resampled_audio = {}

        # Set of required FFT configurations, populated during initialise_analysis
        # Each entry is a (fft_size, hop_size) tuple
        # Only initialize if it doesn't exist - don't reset it during stream changes
        if not hasattr(self, "_required_fft_configs"):
            self._required_fft_configs = set()

        # Track which FFTs have been computed this frame (reset each frame)
        self._fft_computed = {}

        _LOGGER.info(
            f"Rebuilding audio analysis graph: stream_rate={self.stream_sample_rate} Hz, "
            f"input_hop={self.input_hop_size} samples, analysis_fps={self._analysis_fps}"
        )

        # Initialize raw audio sample buffer (input from audio callback)
        self._raw_audio_sample = np.zeros(
            self.input_hop_size, dtype=np.float32
        )

        # If analysis has already been initialized, rebuild FFT resources with new stream parameters
        # This happens when the audio stream opens and we get the actual sample rate
        if self._required_fft_configs:
            _LOGGER.debug(
                "Rebuilding FFT resources and resamplers for current stream rate"
            )
            self._preallocate_fft_resources()

    def on_analysis_parameters_changed(self):
        """Hook for subclasses to rebuild aubio objects when rates change."""
        return

    def _preallocate_fft_resources(self):
        """
        Pre-allocate all FFT resources based on required configurations.
        Called after _required_fft_configs is populated by AudioAnalysisSource.

        Creates:
        - Independent resamplers for each unique hop size
        - Phase vocoders for each (fft_size, hop_size) configuration
        - Frequency domain buffers for results
        - Resampled audio buffers
        """
        if not hasattr(self, "_required_fft_configs"):
            return

        # Extract unique hop sizes from all configurations
        hop_sizes = sorted({hop for (fft, hop) in self._required_fft_configs})

        # Pre-allocate independent resamplers for each hop size
        for hop_size in hop_sizes:
            if hop_size not in self._resamplers:
                # Calculate resampling ratio for this hop size
                # ratio = output_rate / input_rate = target_hop / input_hop
                ratio = hop_size / self.input_hop_size

                # Identify which analyses will use this hop size
                analysis_uses = []
                fft_configs_for_hop = []
                for fft, hop in self._required_fft_configs:
                    if hop == hop_size:
                        fft_configs_for_hop.append(fft)
                        if (
                            hasattr(self, "_onset_fft_config")
                            and (fft, hop) == self._onset_fft_config
                        ):
                            analysis_uses.append("onset")
                        if (
                            hasattr(self, "_tempo_fft_config")
                            and (fft, hop) == self._tempo_fft_config
                        ):
                            analysis_uses.append("tempo")
                        if (
                            hasattr(self, "_pitch_fft_config")
                            and (fft, hop) == self._pitch_fft_config
                        ):
                            analysis_uses.append("pitch")

                # Create independent resampler with continuous state
                # Using "sinc_fastest" for good quality with low latency
                self._resamplers[hop_size] = samplerate.Resampler(
                    "sinc_fastest", channels=1
                )

                # Pre-allocate buffer for resampled audio
                self._resampled_audio[hop_size] = np.zeros(
                    hop_size, dtype=np.float32
                )

                _LOGGER.info(
                    f"Resampler pipeline: hop={hop_size} samples (ratio={ratio:.4f}) → "
                    f"analyses=[{', '.join(analysis_uses) if analysis_uses else 'melbanks'}] → "
                    f"FFT sizes={sorted(set(fft_configs_for_hop))}"
                )

        # Pre-allocate phase vocoders and frequency domains for each config
        for fft_size, hop_size in self._required_fft_configs:
            if (fft_size, hop_size) not in self._phase_vocoders:
                self._phase_vocoders[(fft_size, hop_size)] = aubio.pvoc(
                    fft_size, hop_size
                )
                self._frequency_domain_nulls[(fft_size, hop_size)] = (
                    aubio.cvec(fft_size)
                )
                # Initialize to null/zero
                self._frequency_domains[(fft_size, hop_size)] = (
                    self._frequency_domain_nulls[(fft_size, hop_size)]
                )
                _LOGGER.debug(
                    f"Pre-allocated phase vocoder for FFT config ({fft_size}, {hop_size})"
                )

    def activate(self):
        if self._audio is None:
            try:
                self._audio = sd
            except OSError as Error:
                _LOGGER.critical(f"Sounddevice error: {Error}. Shutting down.")
                self._ledfx.stop()

        # Enumerate all of the input devices and find the one matching the
        # configured host api and device name
        input_devices = self.query_devices()

        hostapis = self.query_hostapis()
        default_device = self.default_device_index()
        if default_device is None:
            # There are no valid audio input devices, so we can't activate the audio source.
            # We should never get here, as we check for devices on start-up.
            # This likely just captures if a device is removed after start-up.
            _LOGGER.warning(
                "Audio input device not found. Unable to activate audio source. Deactivating."
            )
            self.deactivate()
            return
        valid_device_indexes = self.valid_device_indexes()
        _LOGGER.debug("********************************************")
        _LOGGER.debug("Valid audio input devices:")
        for index in valid_device_indexes:
            hostapi_name = hostapis[input_devices[index]["hostapi"]]["name"]
            device_name = input_devices[index]["name"]
            input_channels = input_devices[index]["max_input_channels"]
            _LOGGER.debug(
                f"Audio Device {index}\t{hostapi_name}\t{device_name}\tinput_channels: {input_channels}"
            )
        _LOGGER.debug("********************************************")
        device_idx = self._config["audio_device"]
        _LOGGER.debug(
            f"default_device: {default_device} config_device: {device_idx}"
        )

        if device_idx > max(valid_device_indexes):
            _LOGGER.warning(
                f"Audio device out of range: {device_idx}. Reverting to default input device: {default_device}"
            )
            device_idx = default_device

        elif device_idx not in valid_device_indexes:
            _LOGGER.warning(
                f"Audio device {input_devices[device_idx]['name']} not in valid_device_indexes. Reverting to default input device: {default_device}"
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

        samples_to_delay = int(
            0.001 * self._config["delay_ms"] * self._config["analysis_fps"]
        )
        if samples_to_delay:
            self.delay_queue = queue.Queue(maxsize=samples_to_delay)
        else:
            self.delay_queue = None

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
                    f"Loopback device detected: {device['name']} with {device['max_input_channels']} channels"
                )
            else:
                # if are not a windows loopback device, we will downmix to mono
                # issue seen with poor audio behaviour on Mac and Linux
                # this is similar to the long standing prior implementation
                channels = 1

            if hostapis[device["hostapi"]]["name"] == "WEB AUDIO":
                ledfx.api.websocket.ACTIVE_AUDIO_STREAM = self._stream = (
                    WebAudioStream(
                        device["client"], self._audio_sample_callback
                    )
                )
            else:
                self._stream = self._audio.InputStream(
                    samplerate=int(device["default_samplerate"]),
                    device=device_idx,
                    callback=self._audio_sample_callback,
                    dtype=np.float32,
                    latency="low",
                    blocksize=int(
                        device["default_samplerate"]
                        / self._config["analysis_fps"]
                    ),
                    # only pass channels if we set it to something other than None
                    **({"channels": channels} if channels is not None else {}),
                )

            _LOGGER.info(
                f"Audio source opened: {hostapis[device['hostapi']]['name']}: {device.get('name', device.get('client'))}"
            )

            stream_rate = getattr(
                self._stream, "samplerate", self._config["input_sample_rate"]
            )
            self._rebuild_analysis_graph(stream_rate)
            self._stream.start()
            self._audio_stream_active = True

        try:
            open_audio_stream(device_idx)
            # Protect concurrent access to _last_active with lock
            with self.lock:
                self._last_active = device_idx
        except OSError as e:
            _LOGGER.critical(
                f"Unable to open Audio Device: {e} - please retry."
            )
            self.deactivate()
        except sd.PortAudioError as e:
            _LOGGER.error(f"{e}, Reverting to default input device")
            open_audio_stream(default_device)

    def deactivate(self):
        # Stop the stream outside the lock to avoid deadlock with audio callback
        # The audio callback thread may be waiting to complete, and if it needs
        # any locks, holding self.lock while calling stop() creates a circular wait
        stream_to_close = None
        with self.lock:
            if self._stream:
                stream_to_close = self._stream
                self._stream = None
            self._audio_stream_active = False

        # Stop/close outside the lock
        if stream_to_close:
            stream_to_close.stop()
            stream_to_close.close()
            _LOGGER.info("Audio source closed.")

    def subscribe(self, callback):
        """Registers a callback with the input source"""
        self._callbacks.append(callback)
        if len(self._callbacks) > 0 and not self._audio_stream_active:
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
            and self._audio_stream_active
        ):
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(5.0, self.check_and_deactivate)
            self._timer.start()

    def check_and_deactivate(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
        if (
            len(self._callbacks) <= self._subscriber_threshold
            and self._audio_stream_active
        ):
            self.deactivate()

    def get_device_index_by_name(self, device_name: str):
        for key, value in self.input_devices().items():
            if device_name == value:
                return key
        return -1

    def _audio_sample_callback(self, in_data, frame_count, time_info, status):
        """
        Callback for when a new audio sample is acquired.

        Handles any input sample rate by resampling to the target input_hop_size.
        The resampled audio is then distributed to independent per-hop-size resamplers
        in pre_process_audio for optimal analysis rates.
        """
        raw_sample = np.frombuffer(in_data, dtype=np.float32)

        # Track when we last received audio data
        self._last_callback_time = time.time()
        self._callback_idle_logged = False

        in_sample_len = len(raw_sample)
        out_sample_len = self.input_hop_size

        if in_sample_len != out_sample_len:
            # Resample input to target hop size
            # This handles any input sample rate (e.g., 192kHz microphones)
            # The resampler maintains state for smooth streaming
            if not hasattr(self, "_input_resampler"):
                self._input_resampler = samplerate.Resampler(
                    "sinc_fastest", channels=1
                )

            ratio = out_sample_len / in_sample_len
            processed_audio_sample = self._input_resampler.process(
                raw_sample, ratio, end_of_input=False  # Streaming mode
            )
        else:
            processed_audio_sample = raw_sample

        # Allow small variations in resampler output due to driver behavior
        # The resampler maintains state and will compensate across frames
        sample_len_diff = abs(len(processed_audio_sample) - out_sample_len)
        if sample_len_diff > out_sample_len * 0.15:  # More than 15% off
            _LOGGER.debug(
                f"Discarded malformed audio frame - {len(processed_audio_sample)} samples, expected {out_sample_len} (diff: {sample_len_diff})"
            )
            return

        # If slightly off, pad or trim to exact size for downstream processing
        if len(processed_audio_sample) < out_sample_len:
            # Pad with zeros if too short
            processed_audio_sample = np.pad(
                processed_audio_sample,
                (0, out_sample_len - len(processed_audio_sample)),
                mode="constant",
            )
        elif len(processed_audio_sample) > out_sample_len:
            # Trim if too long
            processed_audio_sample = processed_audio_sample[:out_sample_len]

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

        Multi-FFT Mode:
        - Computes FFTs for all required analysis types based on _required_fft_configs
        - Deduplicates shared FFT configs to avoid redundant computation
        - Resample audio once per unique hop size for efficiency
        - All FFTs are recomputed fresh each frame (no cross-frame caching)
        """
        # clean up nans that have been mysteriously appearing..
        self._raw_audio_sample[np.isnan(self._raw_audio_sample)] = 0

        # Calculate the current volume for silence detection
        self._volume = 1 + aubio.db_spl(self._raw_audio_sample) / 100
        self._volume = max(0, min(1, self._volume))
        self._volume_filter.update(self._volume)

        # Reset FFT computation tracking for this frame
        self._fft_computed.clear()

        # Check volume threshold
        volume_above_threshold = (
            self._volume_filter.value > self._config["min_volume"]
        )

        # Multi-FFT processing
        if (
            hasattr(self, "_required_fft_configs")
            and self._required_fft_configs
        ):
            self._process_multi_fft(volume_above_threshold)

    def _process_multi_fft(self, volume_above_threshold):
        """
        Process all required FFT configurations using independent resamplers.

        Strategy:
        1. Group FFT configs by hop size
        2. Resample input audio once per unique hop size using stateful resamplers
        3. Compute FFTs for all configs sharing the same hop size
        4. Resamplers maintain state across frames for clean, artifact-free audio

        Includes dev-mode timing instrumentation for performance monitoring.
        """
        # Check if dev mode is enabled for profiling
        dev_enabled = (
            hasattr(self._ledfx, "dev_enabled") and self._ledfx.dev_enabled()
        )

        if not volume_above_threshold:
            # Set all frequency domains to null when below threshold
            for config in self._required_fft_configs:
                self._frequency_domains[config] = self._frequency_domain_nulls[
                    config
                ]
                self._fft_computed[config] = True
            return

        # Group configs by hop size for efficient resampling
        hop_size_groups = {}
        for fft_size, hop_size in self._required_fft_configs:
            if hop_size not in hop_size_groups:
                hop_size_groups[hop_size] = []
            hop_size_groups[hop_size].append((fft_size, hop_size))

        # Process each hop size group
        for hop_size, configs in hop_size_groups.items():
            # Resample input audio to this hop size using independent resampler
            if hop_size in self._resamplers:
                # Calculate resampling ratio
                ratio = hop_size / self.input_hop_size

                # Resample using stateful resampler
                # The resampler maintains internal state for smooth streaming
                resampled = self._resamplers[hop_size].process(
                    self._raw_audio_sample,
                    ratio,
                    end_of_input=False,  # Streaming mode - maintains state
                )

                # Validate output length with tolerance
                sample_diff = abs(len(resampled) - hop_size)
                tolerance = max(
                    1, int(hop_size * 0.05)
                )  # 5% tolerance, minimum 1 sample

                if sample_diff > tolerance:
                    # Identify which analyses use this hop size
                    analysis_names = []
                    for fft, hop in configs:
                        if (
                            hasattr(self, "_onset_fft_config")
                            and (fft, hop) == self._onset_fft_config
                        ):
                            analysis_names.append("onset")
                        if (
                            hasattr(self, "_tempo_fft_config")
                            and (fft, hop) == self._tempo_fft_config
                        ):
                            analysis_names.append("tempo")
                        if (
                            hasattr(self, "_pitch_fft_config")
                            and (fft, hop) == self._pitch_fft_config
                        ):
                            analysis_names.append("pitch")

                    _LOGGER.warning(
                        f"[hop={hop_size}] Resampling produced {len(resampled)} samples, expected {hop_size} (diff: {sample_diff}, tolerance: {tolerance}). "
                        f"Input: {len(self._raw_audio_sample)}, ratio: {ratio:.4f}, "
                        f"analyses affected: {', '.join(analysis_names) if analysis_names else 'melbanks'}, "
                        f"configs: {configs}"
                    )
                    # Use null frequency domains for this hop size group
                    for config in configs:
                        self._frequency_domains[config] = (
                            self._frequency_domain_nulls[config]
                        )
                        self._fft_computed[config] = True
                    continue

                # Pad or trim to exact size if within tolerance
                if len(resampled) < hop_size:
                    resampled = np.pad(
                        resampled,
                        (0, hop_size - len(resampled)),
                        mode="edge",  # Repeat last value
                    )
                elif len(resampled) > hop_size:
                    resampled = resampled[:hop_size]

                # Store resampled audio for this hop size
                self._resampled_audio[hop_size] = resampled
            else:
                _LOGGER.error(
                    f"No resampler found for hop_size={hop_size}. This should not happen."
                )
                # Use null frequency domains
                for config in configs:
                    self._frequency_domains[config] = (
                        self._frequency_domain_nulls[config]
                    )
                    self._fft_computed[config] = True
                continue

            # Compute FFTs for all configs using this hop size
            audio_sample = self._resampled_audio[hop_size]

            for config in configs:
                if (
                    config not in self._fft_computed
                    or not self._fft_computed[config]
                ):
                    fft_size, hop_size = config

                    # Compute FFT using the appropriate phase vocoder
                    if config in self._phase_vocoders:
                        if dev_enabled:
                            t0 = perf_counter()
                            self._frequency_domains[config] = (
                                self._phase_vocoders[config](audio_sample)
                            )
                            elapsed_us = (perf_counter() - t0) * 1_000_000
                            self._fft_timings[config].append(elapsed_us)
                        else:
                            self._frequency_domains[config] = (
                                self._phase_vocoders[config](audio_sample)
                            )
                        self._fft_computed[config] = True
                    else:
                        # Phase vocoder not found, use null
                        self._frequency_domains[config] = (
                            self._frequency_domain_nulls[config]
                        )
                        self._fft_computed[config] = True

        # Log FFT performance stats periodically in dev mode
        if dev_enabled and hasattr(self, "_fft_frame_counter"):
            self._fft_frame_counter += 1
            # Log every 120 frames (1 second at 120 FPS)
            if self._fft_frame_counter >= 120:
                self._log_fft_performance_stats()
                self._fft_frame_counter = 0

    def audio_sample(self, hop_size=None):
        """
        Returns audio sample at the requested hop size.

        Args:
            hop_size: Desired hop size in samples. If None, returns raw input audio.
                     If specified, returns resampled audio for that hop size.

        Returns:
            np.array: Audio samples
        """
        if hop_size is None:
            return self._raw_audio_sample

        if hop_size in self._resampled_audio:
            return self._resampled_audio[hop_size]

        # Fallback to raw audio if hop size not found
        _LOGGER.warning(
            f"Requested hop_size={hop_size} not found in resampled audio buffers. "
            f"Returning raw audio (length={len(self._raw_audio_sample)})"
        )
        return self._raw_audio_sample

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
        self._suspend_param_callbacks = True
        self._analysis_initialized = (
            False  # Guard against duplicate initialization
        )
        super().__init__(ledfx, config)

        # Initialize analysis after parent class setup
        # This is the primary initialization point during construction
        self.initialise_analysis()

        # Now safe to enable parameter callbacks
        self._suspend_param_callbacks = False

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
        """
        Initialize all audio analysis components with per-analysis FFT configurations.
        Reads preset and applies user overrides for tempo, onset, and pitch analysis.
        Each analysis type can use different hop sizes optimized for its specific needs.
        """
        # Log call stack to identify duplicate initialization
        import traceback

        stack_summary = traceback.extract_stack()
        caller_info = stack_summary[-2] if len(stack_summary) >= 2 else None
        caller_str = (
            f"{caller_info.filename}:{caller_info.lineno} in {caller_info.name}"
            if caller_info
            else "unknown"
        )

        # Skip duplicate initializations
        if getattr(self, "_analysis_initialized", False):
            _LOGGER.debug(
                f"Skipping duplicate initialise_analysis() call from {caller_str}"
            )
            return

        _LOGGER.debug(f"initialise_analysis() called from {caller_str}")

        # Get current stream parameters
        stream_sample_rate = getattr(
            self,
            "stream_sample_rate",
            self._config["input_sample_rate"],
        )

        # Get the selected preset
        preset_name = self._config.get("fft_preset", "balanced")
        preset = FFT_PRESETS[preset_name]

        # Extract analysis-specific FFT configs from preset
        # These include both FFT size AND hop size optimized for each analysis type
        # Apply user overrides if present
        self._onset_fft_config = self._config.get(
            "fft_onset_override", preset["onset"]
        )
        self._tempo_fft_config = self._config.get(
            "fft_tempo_override", preset["tempo"]
        )
        self._pitch_fft_config = self._config.get(
            "fft_pitch_override", preset["pitch"]
        )

        # Extract individual parameters for aubio initialization
        onset_fft, onset_hop = self._onset_fft_config
        tempo_fft, tempo_hop = self._tempo_fft_config
        pitch_fft, pitch_hop = self._pitch_fft_config

        # Create analysis-specific parameter tuples
        onset_params = (onset_fft, onset_hop, stream_sample_rate)
        tempo_params = (tempo_fft, tempo_hop, stream_sample_rate)
        pitch_params = (pitch_fft, pitch_hop, stream_sample_rate)

        # Initialize melbanks
        if not hasattr(self, "melbanks"):
            self.melbanks = Melbanks(
                self._ledfx,
                self,
                self._ledfx.config.get("melbanks", {}),
                sample_rate=stream_sample_rate,
            )
        else:
            # Force rebuild of melbanks by updating config
            # This ensures filterbanks are recreated with the current FFT size
            self.melbanks.sample_rate = stream_sample_rate
            self.melbanks.update_config(
                self._ledfx.config.get("melbanks", {}), persist=False
            )

        # Initialize tempo, onset, and pitch with their specific FFT configs
        self._tempo = aubio.tempo(self._config["tempo_method"], *tempo_params)

        # Enable various tempo features
        # TODO: Make these configurable options
        self._enable_tempo_feature(
            "multi-octave autocorrelation",
            lambda: self._tempo.set_multi_octave(1),
        )
        self._enable_tempo_feature(
            "onset enhancement", lambda: self._tempo.set_onset_enhancement(1)
        )
        self._enable_tempo_feature(
            "FFT-based autocorrelation",
            lambda: self._tempo.set_fft_autocorr(1),
        )
        self._enable_tempo_feature(
            "dynamic tempo tracking", lambda: self._tempo.set_dynamic_tempo(1)
        )
        self._enable_tempo_feature(
            "adaptive window length",
            lambda: self._tempo.set_adaptive_winlen(1),
        )
        self._enable_tempo_feature(
            "tempogram (single scale)",
            lambda: self._tempo.set_use_tempogram(1),
        )

        self._onset = aubio.onset(self._config["onset_method"], *onset_params)
        self._pitch = aubio.pitch(self._config["pitch_method"], *pitch_params)
        self._pitch.set_unit("midi")
        self._pitch.set_tolerance(self._config["pitch_tolerance"])

        # Populate required FFT configs
        self._required_fft_configs = set()
        self._required_fft_configs.add(self._onset_fft_config)
        self._required_fft_configs.add(self._tempo_fft_config)
        self._required_fft_configs.add(self._pitch_fft_config)

        # Get melbank FFT requirements if melbanks support it
        if hasattr(self.melbanks, "get_required_fft_configs"):
            melbank_configs = self.melbanks.get_required_fft_configs()
            self._required_fft_configs.update(melbank_configs)

        # Pre-allocate FFT resources based on requirements
        self._preallocate_fft_resources()

        # Log the configuration
        _LOGGER.info(
            "Audio analysis initialized with preset '%s': "
            "onset=%s, tempo=%s, pitch=%s",
            preset_name,
            self._onset_fft_config,
            self._tempo_fft_config,
            self._pitch_fft_config,
        )

        # Log FFT sharing in dev mode
        if hasattr(self._ledfx, "dev_enabled") and self._ledfx.dev_enabled():
            self._log_fft_sharing()

        # bar oscillator
        self.beat_counter = 0

        # beat oscillator
        self.beat_timestamp = time.time()
        self.beat_period = 2

        # Beat stability tracking - tracks beat detection stability over time
        # to achieve a reliable tempo lock that persists through music variations

        # Rolling history of the last 4 beat periods (in seconds) for stability analysis
        self.beat_periods_history = deque(maxlen=4)

        # Flag indicating whether a stable tempo lock has been achieved
        # Lock is achieved when 4 consecutive beats have <10% deviation and confidence >= beat_lock_confidence_min
        self.beat_lock_achieved = False

        # Time (in seconds) it took to achieve the beat lock, measured from first_beat_time
        # Used for debugging and logging tempo lock performance
        self.beat_lock_time = None

        # Timestamp of the first detected beat, used as reference point for measuring lock time
        self.first_beat_time = None

        # Timestamp when beat lock was achieved, used to enforce grace period before allowing unlock
        self.beat_lock_timestamp = None

        # Counter tracking consecutive frames with poor confidence/drift
        # Incremented when confidence drops or beat drifts too much while locked
        self.beat_unlock_counter = 0

        # Number of consecutive poor frames required before releasing the tempo lock
        # Prevents spurious unlocks from brief audio anomalies
        self.beat_unlock_required = 2

        # Minimum aubio tempo confidence threshold for maintaining lock (0.0-1.0)
        # If confidence drops below this while locked, beat_unlock_counter increments
        self.beat_unlock_confidence = 0.10

        # Minimum aubio tempo confidence required to achieve initial lock (0.0-1.0)
        # Must be sustained alongside 4 stable beats to achieve lock
        # Set lower than typical aubio values since confidence is often low even with good detection
        self.beat_lock_confidence_min = 0.05  # Lowered for faster lock

        # Maximum allowable deviation ratio for locked beats (0.0-1.0)
        # If beat period drifts more than this percentage from stable period, unlock counter increments
        # 0.18 = 18% maximum drift tolerance
        self.beat_unlock_deviation = 0.20  # Increased for more tolerance

        # Multiplier for beat period to determine "missed beat" timeout (in beat periods)
        # If no beat detected for (beat_period * beat_miss_unlock_factor) seconds, lock is released
        # 4.0 means ~2.3 seconds at 103 BPM, tolerant of brief gaps in music or tempo variations
        self.beat_miss_unlock_factor = 4.0

        # Grace period (in seconds) after achieving lock before unlock conditions are evaluated
        # Prevents immediate unlock right after lock achievement during brief audio gaps
        # Gives the lock time to stabilize before being tested for release
        self.beat_lock_grace_period = 2.0

        # Most recent confidence value from aubio tempo tracker (0.0-1.0)
        # Cached for debugging and display purposes
        self.latest_tempo_confidence = 0.0

        # Track last time we logged status to avoid spamming logs
        # Used for periodic status updates when beat locked but no beats detected
        self.last_status_log_time = time.time()

        # Track number of consecutive frames without beat detection
        # Used to debounce transition logging (only log after sustained silence)
        self.frames_without_beat = 0

        # Number of consecutive frames without beats before we log the transition
        # At 120 FPS, 10 frames = ~83ms of silence
        self.frames_without_beat_threshold = 10

        # Audio callback watchdog - monitors if callbacks stop completely
        self.audio_callback_watchdog_interval = 2.0  # Check every 2 seconds
        self.audio_callback_idle_timeout = (
            1.0  # Idle if no callbacks for 1 second
        )
        self._watchdog_thread = None
        self._watchdog_stop_event = threading.Event()
        self._start_audio_watchdog()

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
        self.beat_power_history_len = int(self._config["analysis_fps"] * 0.2)

        self.beat_prev_time = time.time()
        self.beat_power_history = deque(maxlen=self.beat_power_history_len)

        # Dev-mode FFT profiling infrastructure
        self._fft_timings = defaultdict(lambda: deque(maxlen=120))
        self._fft_frame_counter = 0
        self._last_fft_stats_log_time = time.time()

        # Mark initialization complete
        self._analysis_initialized = True

    def update_config(self, config):
        validated_config = self.CONFIG_SCHEMA(config)
        # Reset initialization flag to allow re-initialization with new config
        self._analysis_initialized = False
        super().update_config(validated_config)
        self.initialise_analysis()

    def _enable_tempo_feature(self, feature_name, setter):
        """Attempt to enable an aubio tempo feature, logging on failure."""
        try:
            setter()
            _LOGGER.debug(f"Enabled {feature_name} tempo feature.")
            return True
        except (ValueError, RuntimeError) as exc:
            _LOGGER.warning(
                "Disabling %s tempo feature: %s",
                feature_name,
                exc,
            )
            return False

    def _reset_tempo_lock(self, reason=None):
        """Drop the current tempo lock so the tracker can adapt quickly."""
        if reason and self.beat_lock_achieved:
            _LOGGER.info("Tempo lock released (%s)", reason)
        self.beat_lock_achieved = False
        self.beat_lock_time = None
        self.beat_lock_timestamp = None
        self.first_beat_time = None
        self.beat_unlock_counter = 0
        self.beat_periods_history.clear()

    def _start_audio_watchdog(self):
        """Start the audio callback watchdog thread."""
        if (
            self._watchdog_thread is None
            or not self._watchdog_thread.is_alive()
        ):
            self._watchdog_stop_event.clear()
            self._watchdog_thread = threading.Thread(
                target=self._audio_watchdog_loop,
                name="AudioWatchdog",
                daemon=True,
            )
            self._watchdog_thread.start()
            _LOGGER.debug("Audio callback watchdog started")

    def _stop_audio_watchdog(self):
        """Stop the audio callback watchdog thread."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_stop_event.set()
            self._watchdog_thread.join(timeout=3.0)
            _LOGGER.debug("Audio callback watchdog stopped")

    def _audio_watchdog_loop(self):
        """Background thread that monitors audio callback health."""
        while not self._watchdog_stop_event.wait(
            self.audio_callback_watchdog_interval
        ):
            now = time.time()

            # Check if audio callbacks have stopped
            if (
                self._last_callback_time is not None
                and not self._callback_idle_logged
                and now - self._last_callback_time
                > self.audio_callback_idle_timeout
            ):

                if self.beat_lock_achieved:
                    locked_bpm = (
                        60.0 / self.beat_period
                        if self.beat_period > 0
                        else 0.0
                    )
                    _LOGGER.info(
                        "Beat tracker idle - no audio data for %.2fs (was locked at %.1f BPM)",
                        now - self._last_callback_time,
                        locked_bpm,
                    )
                else:
                    _LOGGER.debug(
                        "Beat tracker idle - no audio data for %.2fs (no lock achieved)",
                        now - self._last_callback_time,
                    )
                self._callback_idle_logged = True

    def _update_tempo_lock_state(self, detected_period, confidence):
        """Evaluate whether the tempo lock should be maintained or released."""
        if detected_period <= 0:
            return

        if self.beat_period and self.beat_period > 0:
            drift = abs(detected_period - self.beat_period) / max(
                self.beat_period, 1e-6
            )
        else:
            drift = 0.0

        reason = None
        if self.beat_lock_achieved:
            # Require either good confidence OR very stable period to maintain lock
            # This prevents unlock for simple audio sources (metronomes) with perfect timing but low confidence
            if confidence < self.beat_unlock_confidence and drift > 0.05:
                # Both confidence AND stability are poor
                self.beat_unlock_counter += 1
                reason = (
                    f"confidence {confidence:.2f} and drift {drift * 100:.1f}%"
                )
            elif drift > self.beat_unlock_deviation:
                # Drift alone is too high
                self.beat_unlock_counter += 1
                reason = f"drift {drift * 100:.1f}%"
            else:
                # Either good confidence OR good stability - maintain lock
                self.beat_unlock_counter = 0
                return

            if self.beat_unlock_counter >= self.beat_unlock_required:
                self._reset_tempo_lock(reason)
        else:
            self.beat_unlock_counter = 0

    def _log_fft_sharing(self):
        """Log which analyses share which FFT configurations (dev mode only)."""
        # Build a map of FFT configs to the analyses that use them
        config_map = {}

        if hasattr(self, "_onset_fft_config"):
            config = self._onset_fft_config
            if config not in config_map:
                config_map[config] = []
            config_map[config].append("onset")

        if hasattr(self, "_tempo_fft_config"):
            config = self._tempo_fft_config
            if config not in config_map:
                config_map[config] = []
            config_map[config].append("tempo")

        if hasattr(self, "_pitch_fft_config"):
            config = self._pitch_fft_config
            if config not in config_map:
                config_map[config] = []
            config_map[config].append("pitch")

        # Add melbank configs if available
        if hasattr(self.melbanks, "get_required_fft_configs"):
            melbank_configs = self.melbanks.get_required_fft_configs()
            for i, config in enumerate(melbank_configs):
                if config not in config_map:
                    config_map[config] = []
                config_map[config].append(f"melbank_{i}")

        # Log sharing information
        for config, analyses in config_map.items():
            fft_size, hop_size = config
            if len(analyses) > 1:
                _LOGGER.debug(
                    f"FFT config ({fft_size}, {hop_size}) shared by: {', '.join(analyses)}"
                )
            else:
                _LOGGER.debug(
                    f"FFT config ({fft_size}, {hop_size}) used by: {analyses[0]}"
                )

    def _log_fft_performance_stats(self):
        """
        Log FFT performance statistics (dev mode only).
        Called every 120 frames (~1 second at 120 FPS).
        """
        if not hasattr(self, "_fft_timings") or not self._fft_timings:
            return

        # Build map of which analyses use which FFT configs
        config_usage_map = {}

        if hasattr(self, "_onset_fft_config"):
            config = self._onset_fft_config
            if config not in config_usage_map:
                config_usage_map[config] = []
            config_usage_map[config].append("onset")

        if hasattr(self, "_tempo_fft_config"):
            config = self._tempo_fft_config
            if config not in config_usage_map:
                config_usage_map[config] = []
            config_usage_map[config].append("tempo")

        if hasattr(self, "_pitch_fft_config"):
            config = self._pitch_fft_config
            if config not in config_usage_map:
                config_usage_map[config] = []
            config_usage_map[config].append("pitch")

        # Add melbank configs
        if hasattr(self.melbanks, "get_required_fft_configs"):
            melbank_configs = list(self.melbanks.get_required_fft_configs())
            for i, config in enumerate(melbank_configs):
                if config not in config_usage_map:
                    config_usage_map[config] = []
                config_usage_map[config].append(f"melbank_{i}")

        # Calculate and log stats for each FFT config
        total_time_us = 0
        stats_lines = []

        for config, timings in sorted(self._fft_timings.items()):
            if len(timings) == 0:
                continue

            fft_size, hop_size = config
            timings_array = np.array(timings)

            mean_us = np.mean(timings_array)
            p95_us = np.percentile(timings_array, 95)
            max_us = np.max(timings_array)

            # Get usage info
            usage = config_usage_map.get(config, ["unknown"])

            stats_lines.append(
                f"  ({fft_size},{hop_size}): mean={mean_us:.1f}µs p95={p95_us:.1f}µs max={max_us:.1f}µs "
                f"shared_by=[{','.join(usage)}]"
            )

            total_time_us += mean_us

        # Calculate frame budget percentage (at 120 FPS, frame budget is ~8.3ms)
        frame_budget_ms = (
            1000.0 / self._analysis_fps
            if hasattr(self, "_analysis_fps")
            else 8.33
        )
        total_time_ms = total_time_us / 1000.0
        budget_pct = (total_time_ms / frame_budget_ms) * 100.0

        # Log performance summary
        _LOGGER.info(
            "FFT performance (last 120 frames):\n%s\n  Total: %.2fms (%.1f%% of %.2fms frame budget at %d FPS)",
            "\n".join(stats_lines),
            total_time_ms,
            budget_pct,
            frame_budget_ms,
            self._analysis_fps if hasattr(self, "_analysis_fps") else 120,
        )

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
        """
        Returns the MIDI pitch value detected in the current audio frame.
        Uses pitch-specific hop size for optimal frequency resolution.
        """
        # If our audio handler is returning null, then we just return 0 for midi_value and wait for the device starts sending audio.
        try:
            # Get resampled audio at pitch detection's hop size
            _, pitch_hop = self._pitch_fft_config
            audio = self.audio_sample(pitch_hop)
            # Aubio pitch expects audio samples, not frequency domain
            return self._pitch(audio)[0]
        except ValueError as e:
            _LOGGER.warning(e)
            return 0

    @lru_cache(maxsize=None)
    def onset(self):
        """
        Returns True if an onset (transient/attack) is detected in the current frame.
        Uses onset-specific hop size for low latency detection.
        """
        try:
            # Get resampled audio at onset detection's hop size
            _, onset_hop = self._onset_fft_config
            audio = self.audio_sample(onset_hop)
            # Aubio onset expects audio samples, not frequency domain
            return bool(self._onset(audio)[0])
        except ValueError as e:
            _LOGGER.warning(e)
            return 0

    @lru_cache(maxsize=None)
    def bpm_beat_now(self):
        """
        Returns True if a beat is expected now based on BPM/tempo tracking.
        Uses tempo-specific hop size for stable beat tracking.
        """
        try:
            # Get resampled audio at tempo detection's hop size
            _, tempo_hop = self._tempo_fft_config
            audio = self.audio_sample(tempo_hop)
            # Aubio tempo expects audio samples, not frequency domain
            return bool(self._tempo(audio)[0])
        except ValueError as e:
            _LOGGER.warning(e)
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
        now = time.time()

        # Check for beat detection on this frame
        beat_detected = self.bpm_beat_now()

        # Update beat tracking and stability analysis when a beat is detected
        if beat_detected:
            if self.first_beat_time is None:
                self.first_beat_time = now
                _LOGGER.debug(
                    "First beat detected - starting stability tracking"
                )

            self.beat_counter = (self.beat_counter + 1) % 4
            raw_period = max(self._tempo.get_period_s(), 1e-3)
            confidence = float(self._tempo.get_confidence() or 0.0)
            self.latest_tempo_confidence = confidence

            # Guard against octave errors by snapping to integer multiples of the last stable period
            if self.beat_period:
                ratio = raw_period / self.beat_period
                if 0.45 <= ratio <= 0.55:
                    # Aubio reporting double the tempo (half the period) - double the period
                    raw_period = self.beat_period * 2
                elif 1.9 <= ratio <= 2.1:
                    # Aubio reporting half the tempo (double the period) - halve the period
                    raw_period = self.beat_period / 2

            # Update lock state based on confidence and drift
            self._update_tempo_lock_state(raw_period, confidence)

            # Update period history and calculate stable period
            self.beat_periods_history.append(raw_period)
            periods_array = np.array(self.beat_periods_history)
            stable_period = float(np.median(periods_array))
            self.beat_period = stable_period
            deviation = (
                np.max(np.abs(periods_array - stable_period)) / stable_period
                if len(periods_array) > 1
                else 0.0
            )
            locked_bpm = 60.0 / stable_period

            # Check if we should achieve lock
            # For simple audio sources (like metronomes), aubio confidence may be very low or zero
            # So we primarily rely on period stability, with confidence as a secondary indicator
            if (
                not self.beat_lock_achieved
                and len(self.beat_periods_history)
                == self.beat_periods_history.maxlen
                and deviation <= 0.15  # Increased tolerance for achieving lock
                and (
                    confidence >= self.beat_lock_confidence_min
                    or deviation <= 0.05
                )  # Lock with low deviation even if low confidence
            ):
                self.beat_lock_achieved = True
                self.beat_lock_time = now - self.first_beat_time
                self.beat_lock_timestamp = now
                _LOGGER.info(
                    "Beat lock achieved! Locked in %.2fs at %.1f BPM (median period: %.3fs, max deviation: %.1f%%)",
                    self.beat_lock_time,
                    locked_bpm,
                    stable_period,
                    deviation * 100,
                )
            elif not self.beat_lock_achieved:
                _LOGGER.debug(
                    "Beat periods unstable - deviation: %.1f%%, confidence: %.2f (need %.2f) (periods: %s)",
                    deviation * 100,
                    confidence,
                    self.beat_lock_confidence_min,
                    [f"{p:.3f}" for p in self.beat_periods_history],
                )
            else:
                _LOGGER.debug(
                    "Beat locked at %.1f BPM (confidence: %.2f, raw: %.1f BPM, deviation: %.1f%%)",
                    locked_bpm,
                    confidence,
                    60.0 / raw_period,
                    deviation * 100,
                )

            self.beat_timestamp = now
            oscillator = self.beat_counter
            self.frames_without_beat = 0  # Reset counter when beat detected
        else:
            # No beat detected this frame - calculate oscillator position based on time
            effective_period = (
                self.beat_period
                if (self.beat_period and self.beat_period > 0)
                else 1.0
            )
            time_since_beat = now - self.beat_timestamp

            # Increment counter for frames without beats
            self.frames_without_beat += 1

            # Log immediately when transitioning from beats to sustained silence
            # Only log once after threshold frames without beats to avoid spam
            if self.frames_without_beat == self.frames_without_beat_threshold:
                if self.beat_lock_achieved:
                    locked_bpm = (
                        60.0 / self.beat_period
                        if self.beat_period > 0
                        else 0.0
                    )
                    _LOGGER.info(
                        "Beat detection stopped - maintaining lock at %.1f BPM (time since last beat: %.3fs)",
                        locked_bpm,
                        time_since_beat,
                    )
                else:
                    # Log at debug level when not locked
                    _LOGGER.debug(
                        "Beat detection stopped (no lock achieved, time since last beat: %.3fs)",
                        time_since_beat,
                    )
                self.last_status_log_time = (
                    now  # Reset to avoid immediate duplicate log
                )

            oscillator = (
                1 - (effective_period - time_since_beat) / effective_period
            ) + self.beat_counter
            # ensure it's between [0 and 4). useful when audio cuts
            oscillator = oscillator % 4

            # Periodic status logging when locked but no beats detected
            # Log every 2 seconds to show we're still tracking
            if (
                self.beat_lock_achieved
                and (now - self.last_status_log_time) > 2.0
            ):
                locked_bpm = (
                    60.0 / self.beat_period if self.beat_period > 0 else 0.0
                )
                _LOGGER.debug(
                    "Beat locked at %.1f BPM (no beats for %.2fs, oscillator: %.2f)",
                    locked_bpm,
                    time_since_beat,
                    oscillator,
                )
                self.last_status_log_time = now

        # Check for missed beats timeout (runs every frame, not just on beats)
        # This allows us to detect when beats stop coming and unlock accordingly
        if self.beat_lock_achieved:
            effective_period = (
                self.beat_period
                if (self.beat_period and self.beat_period > 0)
                else 1.0
            )
            time_since_beat = now - self.beat_timestamp
            time_since_lock = now - self.beat_lock_timestamp

            # Only check for missed beats if we're past the grace period
            if time_since_lock > self.beat_lock_grace_period:
                if (
                    time_since_beat
                    > effective_period * self.beat_miss_unlock_factor
                ):
                    _LOGGER.debug(
                        "Checking missed beats: time_since_beat=%.2fs, threshold=%.2fs (period=%.3fs * factor=%.1f)",
                        time_since_beat,
                        effective_period * self.beat_miss_unlock_factor,
                        effective_period,
                        self.beat_miss_unlock_factor,
                    )
                    self._reset_tempo_lock(
                        f"missed beats for {time_since_beat:.2f}s"
                    )

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

    def on_analysis_parameters_changed(self):
        """
        Called when analysis parameters change that require reinitialization.
        This is triggered by config updates, not by internal stream state changes.
        """
        if getattr(self, "_suspend_param_callbacks", False):
            return
        # Stop watchdog before reinitializing
        if hasattr(self, "_watchdog_thread"):
            self._stop_audio_watchdog()
        super().on_analysis_parameters_changed()
        self.initialise_analysis()


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
        if self.audio:
            self.audio.unsubscribe(self._audio_data_updated)
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
            idx
            for idx, freq in enumerate(
                self.audio.melbanks.melbank_processors[
                    self._selected_melbank
                ].melbank_frequencies
            )
            if freq >= self._virtual.frequency_range.min
        )

    @cached_property
    def _melbank_max_idx(self):
        return next(
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

    @cached_property
    def _input_mel_length(self):
        return self._melbank_max_idx - self._melbank_min_idx

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
        """
        melbank = self.melbank(**kwargs)
        mel_length = len(melbank)
        splits = tuple(map(lambda i: int(i * mel_length), [0.2, 0.5]))

        return np.split(melbank, splits)
