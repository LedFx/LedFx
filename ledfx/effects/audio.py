import logging
import time
from collections import deque, namedtuple
from functools import cache, cached_property, lru_cache

import aubio
import numpy as np
import sounddevice as sd
import voluptuous as vol

from ledfx.effects import Effect
from ledfx.effects.math import ExpFilter
from ledfx.effects.melbank import Melbanks
from ledfx.events import GraphUpdateEvent

_LOGGER = logging.getLogger(__name__)

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


class AudioInputSource:

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
            vol.Optional("mic_rate", default=20000): int,
            vol.Optional("fft_size", default=2048): int,
            vol.Optional("device_index", default=0): int,
            vol.Optional("min_volume", default=0.2): float,
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
            try:
                self._audio = sd
            except OSError as Error:
                _LOGGER.critical(f"Error: {Error}. Shutting down.")
                self._ledfx.stop()

        # Setup a pre-emphasis filter to help balance the highs
        # Enumerate all of the input devices and find the one matching the
        # configured device index
        hostapis = self._audio.query_hostapis()
        default_api = self._audio.default.hostapi
        devices = self._audio.query_devices()
        default_device = self._audio.default.device[0]

        # Show device and api info in logger
        _LOGGER.info("Audio Input Devices:")
        for api_idx, api in enumerate(hostapis):
            _LOGGER.info(
                "Host API: {} {}".format(
                    api["name"],
                    "[DEFAULT] [SELECTED]" if api_idx == default_api else "",
                )
            )
            for device_idx in api["devices"]:
                device = devices[device_idx]
                if device["max_input_channels"] > 0:
                    _LOGGER.info(
                        "    [{}] {} ({} Hz) {} {}".format(
                            device_idx,
                            device["name"],
                            device["default_samplerate"],
                            "[DEFAULT]"
                            if device_idx == default_device
                            else "",
                            "[SELECTED]"
                            if device_idx == self._config["device_index"]
                            else "",
                        )
                    )
                    # automatically configure sample rate
                    if device_idx == self._config["device_index"]:
                        self._config["mic_rate"] = int(
                            device["default_samplerate"]
                        )

        # old, do not use
        # self.pre_emphasis.set_biquad(1., -self._config['pre_emphasis'], 0, 0, 0)

        # USE THESE FOR SCOTT_MEL OR OTHERS
        # self.pre_emphasis.set_biquad(1.3662, -1.9256, 0.5621, -1.9256, 0.9283)

        # USE THESE FOR MATT_MEl
        # weaker bass, good for vocals, highs
        # self.pre_emphasis.set_biquad(0.87492, -1.74984, 0.87492, -1.74799, 0.75169)
        # bass heavier overall more balanced
        # self.pre_emphasis.set_biquad(
        #     0.85870, -1.71740, 0.85870, -1.71605, 0.71874
        # )

        # Setup a pre-emphasis filter to balance the input volume of lows to highs
        # self.pre_emphasis = aubio.digital_filter(3)
        # self.pre_emphasis.set_biquad(0.8485, -1.6971, 0.8485, -1.6966, 0.6977)
        self.pre_emphasis = None

        freq_domain_length = (self._config["fft_size"] // 2) + 1

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
            freq_domain_length,
        )

        # # MFCC experiments #################

        # _vocal_low, _vocal_high = vocal_range
        # self._vocal_low_index = int(
        #     freq_domain_length * _vocal_low / self._config["mic_rate"]
        # )
        # self._vocal_high_index = int(
        #     freq_domain_length * _vocal_high / self._config["mic_rate"]
        # )
        # _vocal_domain_index = self._vocal_high_index - self._vocal_low_index
        # self._vocal_frequency_domain = aubio.cvec(_vocal_domain_index * 2 - 1)

        # # configure mfcc for science and harmonics
        # _mfcc_coeffs = 13
        # self._mfcc = aubio.mfcc(
        #     buf_size=_vocal_domain_index * 2 - 1,
        #     n_filters=100,
        #     n_coeffs=_mfcc_coeffs,
        #     samplerate=self._config["mic_rate"],
        # )
        # self._mfcc_x = np.arange(_mfcc_coeffs)
        # self._mfcing = ExpFilter(
        #     np.tile(1e-1, _mfcc_coeffs - 2),
        #     alpha_decay=0.2,
        #     alpha_rise=0.4,
        # )

        # # Pitch Experiments ###################
        # self._pitch = aubio.pitch(
        #     "schmitt",
        #     self._config["fft_size"],
        #     self._config["mic_rate"] // self._config["sample_rate"],
        #     self._config["mic_rate"],
        # )
        # self._pitch.set_unit("midi")

        # self._pitch_rolling = np.zeros(60, dtype=float)
        # self._pitch_x = np.arange(60)

        # self._pitcing = ExpFilter(
        #     0,
        #     alpha_decay=0.3,
        #     alpha_rise=0.3,
        # )
        # Open the audio stream and start processing the input
        try:
            self._stream = self._audio.InputStream(
                samplerate=self._config["mic_rate"],
                device=self._config["device_index"],
                channels=1,
                callback=self._audio_sample_callback,
                dtype=np.float32,
                blocksize=self._config["mic_rate"]
                // self._config["sample_rate"],
            )
            self._stream.start()
        except OSError as e:
            _LOGGER.critical(
                f"Unable to open Audio Device: {e} - please retry."
            )
            self.deactivate()
        _LOGGER.info("Audio source opened.")

    def deactivate(self):
        if self._stream:
            self._stream.stop()
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

        return self._raw_audio_sample

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
        self._volume = 1 + aubio.db_spl(self._raw_audio_sample) / 100
        self._volume = max(0, min(1, self._volume))
        print(self._volume)
        # Setting volume to 0 if volume <= 90 seems to work.
        # Might need to do some fiddling with different noise floors if there's any future issues
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


class AudioAnalysisSource(AudioInputSource):

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("pitch_method", default="default"): str,
            vol.Optional("tempo_method", default="default"): str,
            vol.Optional("onset_method", default="hfc"): str,
            vol.Optional("pitch_tolerance", default=0.8): float,
        },
        extra=vol.ALLOW_EXTRA,
    )

    # volume based beat detection constants
    beat_max_freq = 50
    beat_min_percent_diff = 0.7
    beat_min_detect_amplitude = 0.7
    beat_min_time_since = 0.2
    beat_channel_maxlen = 40

    def __init__(self, ledfx, config):
        config = self.CONFIG_SCHEMA(config)
        super().__init__(ledfx, config)
        self.initialise_analysis()

        # Subscribe functions to be run on every frame of audio
        self.subscribe(self.melbanks)
        self.subscribe(self.pitch)
        self.subscribe(self.onset)
        self.subscribe(self.oscillator)
        self.subscribe(self.volume_beat_now)

    def initialise_analysis(self):
        fft_params = (
            self._config["fft_size"],
            self._config["mic_rate"] // self._config["sample_rate"],
            self._config["mic_rate"],
        )

        # melbanks
        self.melbanks = Melbanks(
            self._ledfx, self, self._ledfx.config.get("melbanks", {})
        )

        # pitch, tempo, onset
        self._tempo = aubio.tempo(self._config["tempo_method"], *fft_params)
        self._onset = aubio.onset(self._config["onset_method"], *fft_params)
        self._pitch = aubio.pitch(self._config["pitch_method"], *fft_params)
        self._pitch.set_unit("midi")
        self._pitch.set_tolerance(self._config["pitch_tolerance"])

        # oscillator
        self.beat_timestamp = time.time()
        self.beat_period = 2

        # volume based beat detection
        assert (
            self.melbanks._config["max_frequencies"][0] >= self.beat_max_freq
        )

        self.beat_prev_time = time.time()
        self.beat_max_mel_index = next(
            i - 1
            for i, f in enumerate(
                self.melbanks.melbank_processors[0].melbank_frequencies
            )
            if f > self.beat_max_freq
        )

        self.beat_bass_channels = tuple(
            deque(maxlen=self.beat_channel_maxlen)
            for _ in range(self.beat_max_mel_index)
        )

        # bass power
        self.bass_power_filter = ExpFilter(0, alpha_decay=0.2, alpha_rise=0.95)

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
        self.oscillator.cache_clear()
        self.bass_power.cache_clear()

    # @lru_cache(maxsize=32)
    # def melbank(self):
    #     """Returns the raw melbank curve"""

    #     if self.volume() > self._config["min_volume"]:
    #         # Compute the filterbank from the frequency information
    #         raw_filter_banks = self.filterbank(self.frequency_domain())
    #         raw_filter_banks = raw_filter_banks ** 2.0

    #         self.mel_gain.update(np.ma(raw_filter_banks, sigma=1.0)))
    #         filter_banks = raw_filter_banks / self.mel_gain.value
    #         filter_banks = self.mel_smoothing.update(filter_banks)

    #     else:
    #         raw_filter_banks = np.zeros(self._config["samples"])
    #         filter_banks = raw_filter_banks

    #     if self._ledfx.dev_enabled():
    #         self._ledfx.events.fire_event(
    #             GraphUpdateEvent(
    #                 "raw",
    #                 raw_filter_banks,
    #                 np.array(self.melbank_frequencies),
    #             )
    #         )
    #         self._ledfx.events.fire_event(
    #             GraphUpdateEvent(
    #                 "melbank",
    #                 filter_banks,
    #                 np.array(self.melbank_frequencies),
    #             )
    #         )
    #     return filter_banks

    # def melbank_lows(self):
    #     return self.melbank()[: self.lows_index]

    # def melbank_mids(self):
    #     return self.melbank()[self.lows_index : self.mids_index]

    # def melbank_highs(self):
    #     return self.melbank()[self.mids_index :]

    # def sample_melbank(self, hz):
    #     """Samples the melbank curve at a given frequency"""
    #     return np.interp(hz, self.melbank_frequencies, self.melbank())

    @cache
    def pitch(self):
        # If our audio handler is returning null, then we just return 0 for midi_value and wait for the device starts sending audio.
        try:
            return self._pitch(self.audio_sample())[0]
        except ValueError:
            return 0

    @cache
    def onset(self):
        try:
            return bool(self._onset(self.audio_sample(raw=True))[0])
        except ValueError:
            return 0

    @cache
    def bpm_beat_now(self):
        """
        Returns True if a beat is expected now based on BPM data
        """
        try:
            return bool(self._tempo(self.audio_sample(raw=True))[0])
        except ValueError:
            return 0

    @cache
    def volume_beat_now(self):
        """
        Returns True if a beat is expected now based on volume of bass
        This algorithm is a bit weird, but works quite nicely.
        I've tried my best to optimise it from the original
        implementation in systematic_leds
        """

        time_now = time.time()

        for i in range(self.beat_max_mel_index):
            self.beat_bass_channels[i].appendleft(self.melbanks.melbanks[0][i])

            # calculates the % difference of the first value of the channel to the average for the channel
            difference = (
                self.beat_bass_channels[i][0]
                * self.beat_channel_maxlen
                / sum(self.beat_bass_channels[i])
                - 1
            )

            if (
                difference >= self.beat_min_percent_diff
                and self.beat_bass_channels[i][0]
                >= self.beat_min_detect_amplitude
                and time_now - self.beat_prev_time > self.beat_min_time_since
            ):
                self.beat_prev_time = time_now
                return True
        else:
            return False

    @cache
    def bass_power(self, filtered=True):
        """
        Returns a float (0<=x<=1) corresponding to the bass power
        """
        bass_power = np.average(
            self.melbanks.melbanks[0][: self.beat_max_mel_index]
        )
        bass_power = min(bass_power, 1)
        self.bass_power_filter.update(bass_power)

        if filtered:
            return self.bass_power_filter.value
        else:
            return bass_power

    @cache
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
        if self.bpm_beat_now:
            self.beat_period = self._tempo.get_period_s()
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
        return oscillator


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

    def clear_melbank_freq_props(self):
        """
        Clears the cached data for selecting and interpolating melbank.
        Almost all the properties used to build the melbank are cached
        to try and ease computational load.
        """
        self.melbank.cache_clear()

        for prop in [
            "_selected_melbank",
            "_melbank_min_idx",
            "_melbank_max_idx",
            "_input_mel_length",
            "_melbank_interp_linspaces",
        ]:
            if hasattr(self, prop):
                delattr(self, prop)

    @cached_property
    def _selected_melbank(self):
        return next(
            i
            for i, x in enumerate(
                self.audio.melbanks._config["max_frequencies"]
            )
            if x >= self._display.frequency_range.max
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
            if freq >= self._display.frequency_range.min
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
                if freq >= self._display.frequency_range.max
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

    @cache
    def melbank(self, filtered=False, size=0):
        """
        This little bit of code pulls together information from the effect's
        display (which controls the audio frequency range), and uses that
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
        # print(melbank)
        if size and (self._input_mel_length != size):
            return np.interp(*self._melbank_interp_linspaces(size), melbank)
        else:
            return melbank
