import logging
import time
import warnings
from collections import namedtuple
from functools import lru_cache
from math import log

import aubio
import numpy as np
import pyaudio
import voluptuous as vol

import ledfx.effects.math as math
import ledfx.effects.mel as mel
from ledfx.effects import Effect, smooth
from ledfx.effects.math import ExpFilter
from ledfx.events import GraphUpdateEvent

_LOGGER = logging.getLogger(__name__)


"""

    ***THIS IS SUPER IMPORTANT***

    PYAUDIO BINDINGS ARE APPROACHING END OF LIFE
    FOR PYTHON 3.8/3.9 WE HAVE TO IGNORE ALL WARNINGS THROWN IN THIS FILE
    OTHERWISE WE GET A DEPRECIATIONWARNING *EVERY AUDIO SAMPLE*


"""
warnings.filterwarnings("ignore")


FrequencyRange = namedtuple("FrequencyRange", "min,max")

FREQUENCY_RANGES = {
    "Ultra Low (1-20Hz)": FrequencyRange(1, 20),
    "Sub Bass (20-60Hz)": FrequencyRange(20, 60),
    "Bass (60-250Hz)": FrequencyRange(60, 250),
    "Low Midrange (250-500Hz)": FrequencyRange(250, 500),
    "Midrange (500Hz-2kHz)": FrequencyRange(500, 2000),
    "Upper Midrange (2Khz-4kHz)": FrequencyRange(2000, 4000),
    "High Midrange (4kHz-6kHz)": FrequencyRange(4000, 6000),
    "High Frequency (6kHz-24kHz)": FrequencyRange(6000, 24000),
}

FREQUENCY_RANGES_SIMPLE = {
    "Low (1-250Hz)": FrequencyRange(1, 250),
    "Mid (250Hz-4kHz)": FrequencyRange(250, 4000),
    "High (4kHz-24kHz)": FrequencyRange(4000, 24000),
}

MIN_MIDI = 21
MAX_MIDI = 108


class AudioInputSource(object):

    _is_activated = False
    _audio = None
    _stream = None
    _callbacks = []
    _audioWindowSize = 4
    _processed_audio_sample = None
    _volume = -90
    _volume_filter = ExpFilter(-90, alpha_decay=0.99, alpha_rise=0.99)

    AUDIO_CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("sample_rate", default=60): int,
            vol.Optional("mic_rate", default=48000): int,
            vol.Optional("fft_size", default=1024): int,
            vol.Optional("device_index", default=0): int,
            vol.Optional("pre_emphasis", default=0.3): float,
            vol.Optional("min_volume", default=-70.0): float,
        },
        extra=vol.ALLOW_EXTRA,
    )

    def __init__(self, ledfx, config):
        self._ledfx = ledfx
        self.update_config(config)

    def update_config(self, config):
        """Deactivate the audio, update the config, the reactivate"""

        self.deactivate()
        self._config = self.AUDIO_CONFIG_SCHEMA(config)
        if len(self._callbacks) != 0:
            self.activate()

    def activate(self):

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        # Setup a pre-emphasis filter to help balance the highs
        self.pre_emphasis = None
        if self._config["pre_emphasis"]:
            self.pre_emphasis = aubio.digital_filter(3)
            #
            # old, do not use
            # self.pre_emphasis.set_biquad(1., -self._config['pre_emphasis'], 0, 0, 0)

            # USE THESE FOR SCOTT_MEL OR OTHERS
            # self.pre_emphasis.set_biquad(1.3662, -1.9256, 0.5621, -1.9256, 0.9283)

            # USE THESE FOR MATT_MEl
            # weaker bass, good for vocals, highs
            # self.pre_emphasis.set_biquad(0.87492, -1.74984, 0.87492, -1.74799, 0.75169)
            # bass heavier overall more balanced
            self.pre_emphasis.set_biquad(
                0.85870, -1.71740, 0.85870, -1.71605, 0.71874
            )

        # Setup the phase vocoder to perform a windowed FFT
        self._phase_vocoder = aubio.pvoc(
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
        )
        self._frequency_domain_null = aubio.cvec(self._config["fft_size"])
        self._frequency_domain = self._frequency_domain_null
        self._frequency_domain_x = np.linspace(
            0,
            self._config["mic_rate"],
            (self._config["fft_size"] // 2) + 1,
        )

        # Enumerate all of the input devices and find the one matching the
        # configured device index
        _LOGGER.info("Audio Input Devices:")
        info = self._audio.get_host_api_info_by_index(0)
        for i in range(0, info.get("deviceCount")):
            if (
                self._audio.get_device_info_by_host_api_device_index(0, i).get(
                    "maxInputChannels"
                )
            ) > 0:
                _LOGGER.info(
                    "  [{}] {}".format(
                        i,
                        self._audio.get_device_info_by_host_api_device_index(
                            0, i
                        ).get("name"),
                    )
                )

        # Open the audio stream and start processing the input
        try:
            self._stream = self._audio.open(
                input_device_index=self._config["device_index"],
                format=pyaudio.paFloat32,
                channels=1,
                rate=self._config["mic_rate"],
                input=True,
                frames_per_buffer=self._config["mic_rate"]
                // self._config["sample_rate"],
                stream_callback=self._audio_sample_callback,
            )
            self._stream.start_stream()
        except OSError:
            _LOGGER.critical("Unable to open Audio Device - please retry.")
            self.deactivate
        _LOGGER.info("Audio source opened.")

    def deactivate(self):
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        self._rolling_window = None
        _LOGGER.info("Audio source closed.")

    def subscribe(self, callback):
        """Registers a callback with the input source"""
        self._callbacks.append(callback)

        if len(self._callbacks) == 1:
            self.activate()

    def unsubscribe(self, callback):
        """Unregisters a callback with the input source"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

        if len(self._callbacks) == 0:
            self.deactivate()

    def _audio_sample_callback(self, in_data, frame_count, time_info, status):
        """Callback for when a new audio sample is acquired"""
        self._raw_audio_sample = np.frombuffer(in_data, dtype=np.float32)

        self.pre_process_audio()
        self._invalidate_caches()
        self._invoke_callbacks()

        return (self._raw_audio_sample, pyaudio.paContinue)

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

        # Calculate the current volume for silence detection
        self._volume = aubio.db_spl(self._raw_audio_sample)
        if np.isinf(self._volume):
            self._volume = 0.0
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

        # Light up some notifications for developer mode
        if self._ledfx.dev_enabled():
            self._ledfx.events.fire_event(
                GraphUpdateEvent(
                    "fft",
                    self._frequency_domain.norm,
                    self._frequency_domain_x,
                )
            )

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


class MelbankInputSource(AudioInputSource):

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("samples", default=48): int,
            vol.Optional("min_frequency", default=20): int,
            vol.Optional("max_frequency", default=18000): int,
            vol.Optional("min_volume", default=-70.0): float,
            vol.Optional("pitch_tolerance", default=0.8): float,
            vol.Optional("min_volume_count", default=20): int,
            vol.Optional("power", default=1.0): float,
            vol.Optional("coeffs_type", default="matt_mel"): str,
        },
        extra=vol.ALLOW_EXTRA,
    )

    def __init__(self, ledfx, config):
        config = self.CONFIG_SCHEMA(config)
        super().__init__(ledfx, config)

        self._initialize_melbank()
        self._initialize_pitch()
        self._initialize_tempo()
        self._initialize_onset()
        self._initialize_oscillator()

    def update_config(self, config):
        validated_config = self.CONFIG_SCHEMA(config)
        super().update_config(validated_config)

        self._initialize_melbank()
        self._initialize_pitch()
        self._initialize_tempo()
        self._initialize_onset()
        self._initialize_oscillator()

    def _invalidate_caches(self):
        """Invalidates the cache for all melbank related data"""
        super()._invalidate_caches()
        self.onset.cache_clear()
        self.oscillator.cache_clear()
        self.melbank.cache_clear()
        self.melbank_filtered.cache_clear()
        self.interpolated_melbank.cache_clear()
        self.midi_value.cache_clear()

    def _initialize_pitch(self):
        self.pitch_o = aubio.pitch(
            "schmitt",
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )
        self.pitch_o.set_unit("midi")
        self.pitch_o.set_tolerance(self._config["pitch_tolerance"])

    def _initialize_tempo(self):
        self.tempo_o = aubio.tempo(
            "default",
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )

    def _initialize_onset(self):
        self.onset_high = aubio.onset(
            "specflux",
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )
        self.onset_soft = aubio.onset(
            "phase",
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )
        self.onset_mids = aubio.onset(
            "specdiff",
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )

    def _initialize_oscillator(self):
        self.beat_timestamp = time.time()
        self.beat_period = 2

    def _initialize_melbank(self):
        """Initialize all the melbank related variables"""

        # Few difference coefficient types for experimentation
        if self._config["coeffs_type"] == "triangle":
            melbank_mel = np.linspace(
                aubio.hztomel(self._config["min_frequency"]),
                aubio.hztomel(self._config["max_frequency"]),
                self._config["samples"] + 2,
            )
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel]
            ).astype(np.float32)

            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, self._config["mic_rate"]
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        if self._config["coeffs_type"] == "bark":
            melbank_bark = np.linspace(
                6.0 * np.arcsinh(self._config["min_frequency"] / 600.0),
                6.0 * np.arcsinh(self._config["max_frequency"] / 600.0),
                self._config["samples"] + 2,
            )
            self.melbank_frequencies = (
                600.0 * np.sinh(melbank_bark / 6.0)
            ).astype(np.float32)

            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, self._config["mic_rate"]
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        # Slaney coefficients will always produce 40 samples spanning 133Hz to
        # 6000Hz
        if self._config["coeffs_type"] == "slaney":
            self.filterbank = aubio.filterbank(40, self._config["fft_size"])
            self.filterbank.set_mel_coeffs_slaney(self._config["mic_rate"])

            # Sanley frequencies are linear-log spaced where 133Hz to 1000Hz is linear
            # spaced and 1000Hz to 6000Hz is log spaced. It also produced a hardcoded
            # 40 samples.
            lowestFrequency = 133.3
            linearSpacing = 66.6666666
            logSpacing = 1.0711703
            linearFilters = 13
            logFilters = 27
            linearSpacedFreqs = (
                lowestFrequency + np.arange(0, linearFilters) * linearSpacing
            )
            logSpacedFreqs = linearSpacedFreqs[-1] * np.power(
                logSpacing, np.arange(1, logFilters + 1)
            )

            self._config["samples"] = 40
            self.melbank_frequencies = np.hstack(
                (linearSpacedFreqs, logSpacedFreqs)
            ).astype(np.float32)

        # Standard mel coefficients
        if self._config["coeffs_type"] == "mel":
            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_mel_coeffs(
                self._config["mic_rate"],
                self._config["min_frequency"],
                self._config["max_frequency"],
            )

            # Frequencies wil be linearly spaced in the mel scale
            melbank_mel = np.linspace(
                aubio.hztomel(self._config["min_frequency"]),
                aubio.hztomel(self._config["max_frequency"]),
                self._config["samples"],
            )
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel]
            )

        # HTK mel coefficients
        if self._config["coeffs_type"] == "htk":
            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_mel_coeffs_htk(
                self._config["mic_rate"],
                self._config["min_frequency"],
                self._config["max_frequency"],
            )

            # Frequencies wil be linearly spaced in the mel scale
            melbank_mel = np.linspace(
                aubio.hztomel(self._config["min_frequency"]),
                aubio.hztomel(self._config["max_frequency"]),
                self._config["samples"],
            )
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel]
            )

        # Coefficients based on Scott's audio reactive led project
        if self._config["coeffs_type"] == "scott":
            (melmat, center_frequencies_hz, freqs,) = mel.compute_melmat(
                num_mel_bands=self._config["samples"],
                freq_min=self._config["min_frequency"],
                freq_max=self._config["max_frequency"],
                num_fft_bands=int(self._config["fft_size"] // 2) + 1,
                sample_rate=self._config["mic_rate"],
            )
            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_coeffs(melmat.astype(np.float32))
            self.melbank_frequencies = center_frequencies_hz

        # "Mel"-spacing based on Scott's audio reactive led project. This
        # should in theory be the same as the above, but there seems to be
        # slight differences. Leaving both for science!
        if self._config["coeffs_type"] == "scott_mel":

            def hertz_to_scott(freq):
                return 3340.0 * log(1 + (freq / 250.0), 9)

            def scott_to_hertz(scott):
                return 250.0 * (9 ** (scott / 3340.0)) - 250.0

            melbank_scott = np.linspace(
                hertz_to_scott(self._config["min_frequency"]),
                hertz_to_scott(self._config["max_frequency"]),
                self._config["samples"] + 2,
            )
            self.melbank_frequencies = np.array(
                [scott_to_hertz(scott) for scott in melbank_scott]
            ).astype(np.float32)

            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, self._config["mic_rate"]
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        # Modified scott_mel, spreads out the low range and compresses the
        # highs
        if self._config["coeffs_type"] == "matt_mel":

            def hertz_to_matt(freq):
                return 3700.0 * log(1 + (freq / 200.0), 13)

            def matt_to_hertz(matt):
                return 200.0 * (10 ** (matt / 3700.0)) - 200.0

            melbank_matt = np.linspace(
                hertz_to_matt(self._config["min_frequency"]),
                hertz_to_matt(self._config["max_frequency"]),
                self._config["samples"] + 2,
            )
            self.melbank_frequencies = np.array(
                [matt_to_hertz(matt) for matt in melbank_matt]
            ).astype(np.float32)

            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, self._config["mic_rate"]
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        if self._config["coeffs_type"] == "fixed":
            ranges = FREQUENCY_RANGES.values()
            upper_edges_hz = np.zeros(len(ranges))
            lower_edges_hz = np.zeros(len(ranges))
            for idx, value in enumerate(ranges):
                lower_edges_hz[idx] = value.min
                upper_edges_hz[idx] = value.max

            (
                melmat,
                center_frequencies_hz,
                freqs,
            ) = mel.compute_melmat_from_range(
                lower_edges_hz=lower_edges_hz,
                upper_edges_hz=upper_edges_hz,
                num_fft_bands=int(self._config["fft_size"] // 2) + 1,
                sample_rate=self._config["mic_rate"],
            )

            self._config["samples"] = len(center_frequencies_hz)
            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_coeffs(melmat.astype(np.float32))
            self.melbank_frequencies = center_frequencies_hz

        if self._config["coeffs_type"] == "fixed_simple":
            ranges = FREQUENCY_RANGES_SIMPLE.values()
            upper_edges_hz = np.zeros(len(ranges))
            lower_edges_hz = np.zeros(len(ranges))
            for idx, value in enumerate(ranges):
                lower_edges_hz[idx] = value.min
                upper_edges_hz[idx] = value.max

            (
                melmat,
                center_frequencies_hz,
                freqs,
            ) = mel.compute_melmat_from_range(
                lower_edges_hz=lower_edges_hz,
                upper_edges_hz=upper_edges_hz,
                num_fft_bands=int(self._config["fft_size"] // 2) + 1,
                sample_rate=self._config["mic_rate"],
            )

            self._config["samples"] = len(center_frequencies_hz)
            self.filterbank = aubio.filterbank(
                self._config["samples"], self._config["fft_size"]
            )
            self.filterbank.set_coeffs(melmat.astype(np.float32))
            self.melbank_frequencies = center_frequencies_hz

        self.melbank_frequencies = self.melbank_frequencies.astype(int)

        # Normalize the filterbank triangles to a consistent height, the
        # default coeffs (for types other than legacy) will be normalized
        # by the triangles area which results in an uneven melbank
        if (
            self._config["coeffs_type"] != "scott"
            and self._config["coeffs_type"] == "scott_mel"
        ):
            coeffs = self.filterbank.get_coeffs()
            coeffs /= np.max(coeffs, axis=-1)[:, None]
            self.filterbank.set_coeffs(coeffs)

        # Find the indexes for each of the frequency ranges
        self.lows_index = self.mids_index = self.highs_index = 1
        for i in range(0, len(self.melbank_frequencies)):
            if (
                self.melbank_frequencies[i]
                < FREQUENCY_RANGES_SIMPLE["Low (1-250Hz)"].max
            ):
                self.lows_index = i + 1
            elif (
                self.melbank_frequencies[i]
                < FREQUENCY_RANGES_SIMPLE["Mid (250Hz-4kHz)"].max
            ):
                self.mids_index = i + 1
            elif (
                self.melbank_frequencies[i]
                < FREQUENCY_RANGES_SIMPLE["High (4kHz-24kHz)"].max
            ):
                self.highs_index = i + 1

        # Build up some of the common filters
        self.mel_gain = ExpFilter(
            np.tile(1e-1, self._config["samples"]),
            alpha_decay=0.01,
            alpha_rise=0.99,
        )
        self.mel_smoothing = ExpFilter(
            np.tile(1e-1, self._config["samples"]),
            alpha_decay=0.2,
            alpha_rise=0.99,
        )
        self.common_filter = ExpFilter(alpha_decay=0.99, alpha_rise=0.01)

    @lru_cache(maxsize=32)
    def melbank(self):
        """Returns the raw melbank curve"""

        if self.volume() > self._config["min_volume"]:
            # Compute the filterbank from the frequency information
            raw_filter_banks = self.filterbank(self.frequency_domain())
            raw_filter_banks = raw_filter_banks ** 2.0

            self.mel_gain.update(np.max(smooth(raw_filter_banks, sigma=1.0)))
            filter_banks = raw_filter_banks / self.mel_gain.value
            filter_banks = self.mel_smoothing.update(filter_banks)

        else:
            raw_filter_banks = np.zeros(self._config["samples"])
            filter_banks = raw_filter_banks

        if self._ledfx.dev_enabled():
            self._ledfx.events.fire_event(
                GraphUpdateEvent(
                    "raw",
                    raw_filter_banks,
                    np.array(self.melbank_frequencies),
                )
            )
            self._ledfx.events.fire_event(
                GraphUpdateEvent(
                    "melbank",
                    filter_banks,
                    np.array(self.melbank_frequencies),
                )
            )
        return filter_banks

    def melbank_lows(self):
        return self.melbank()[: self.lows_index]

    def melbank_mids(self):
        return self.melbank()[self.lows_index : self.mids_index]

    def melbank_highs(self):
        return self.melbank()[self.mids_index :]

    @lru_cache(maxsize=32)
    def melbank_filtered(self):
        # TODO: Should probably account for the filtered melbank not being
        # queried every frame which would result in a poor filter. Need a
        # good balance between wasting compute resources and quality filters.
        return self.common_filter.update(self.melbank())

    def sample_melbank(self, hz):
        """Samples the melbank curve at a given frequency"""
        return np.interp(hz, self.melbank_frequencies, self.melbank())

    @lru_cache(maxsize=32)
    def interpolated_melbank(self, size, filtered=True):
        """Returns a melbank curve interpolated up to a given size"""
        if filtered is True:
            return math.interpolate(self.melbank_filtered(), size)

        return math.interpolate(self.melbank(), size)

    @lru_cache(maxsize=32)
    def midi_value(self):
        # If pyaudio is returning null, then we just return 0 for midi_value and wait for the device starts sending audio.
        try:
            return self.pitch_o(self.audio_sample())[0]
        except ValueError:
            return 0

    @lru_cache(maxsize=32)
    def onset(self):
        return {
            "mids": bool(self.onset_mids(self.audio_sample(raw=True))[0]),
            "soft": bool(self.onset_soft(self.audio_sample(raw=True))[0]),
            "high": bool(self.onset_high(self.audio_sample(raw=True))[0]),
        }

    @lru_cache(maxsize=32)
    def oscillator(self):
        """
        returns a float (0<=x<1) corresponding to the current position of beat tracker.
        this is synced and quantized to the bpm of whatever is playing.

        0                0.5                 <1
        {----------time for one beat---------}
               ^    -->      -->      -->
            value of
           oscillator
        """
        # update tempo and oscillator
        is_beat = bool(self.tempo_o(self.audio_sample(raw=True))[0])
        if is_beat:
            self.beat_period = self.tempo_o.get_period_s()
            self.beat_timestamp = time.time()
            oscillator = 0
        else:
            time_since_beat = time.time() - self.beat_timestamp
            oscillator = (
                1 - (self.beat_period - time_since_beat) / self.beat_period
            )
            # ensure it's between 0 and 1. useful when audio cuts
            oscillator = min(1, oscillator)
            oscillator = max(0, oscillator)
        return oscillator, is_beat


@Effect.no_registration
class AudioReactiveEffect(Effect):
    """
    Base for audio reactive effects. This really just subscribes
    to the melbank input source and forwards input along to the
    subclasses. This can be expanded to do the common r/g/b filters.
    """

    def activate(self, channel):
        _LOGGER.info("Activating AudioReactiveEffect.")
        super().activate(channel)

        if not self._ledfx.audio or id(MelbankInputSource) != id(
            self._ledfx.audio.__class__
        ):
            self._ledfx.audio = MelbankInputSource(
                self._ledfx, self._ledfx.config.get("audio", {})
            )

        self.audio = self._ledfx.audio
        self._ledfx.audio.subscribe(self._audio_data_updated)

    def deactivate(self):
        _LOGGER.info("Deactivating AudioReactiveEffect.")
        self.audio.unsubscribe(self._audio_data_updated)
        super().deactivate()

    def create_filter(self, alpha_decay, alpha_rise):
        # TODO: Since most effects reuse the same general filters it would be
        # nice for all that computation to be shared. This mean that shared
        # filters are needed, or if there is really just a small set of filters
        # that those get added to the Melbank input source instead.
        return ExpFilter(alpha_decay=alpha_decay, alpha_rise=alpha_rise)

    def _audio_data_updated(self):
        if self.is_active:
            self.audio_data_updated(self.audio)

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updated. Should
        be implemented by subclasses
        """
        pass
