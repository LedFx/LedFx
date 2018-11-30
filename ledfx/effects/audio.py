import time
import logging
import pyaudio
from ledfx.effects import Effect
import voluptuous as vol
from ledfx.effects.math import ExpFilter
from ledfx.events import GraphUpdateEvent
import ledfx.effects.math as math
from functools import lru_cache
import numpy as np
import collections
import aubio
from aubio import fvec, cvec, filterbank, float_type

_LOGGER = logging.getLogger(__name__)

from collections import namedtuple
FrequencyRange = namedtuple('FrequencyRange','min,max')

FREQUENCY_RANGES = {
    'sub_bass': FrequencyRange(20, 60),
    'bass': FrequencyRange(60, 250),
    'low_midrange': FrequencyRange(250, 500),
    'midrange': FrequencyRange(500, 2000),
    'upper_midrange': FrequencyRange(2000, 4000),
    'presence': FrequencyRange(4000, 6000),
    'brilliance': FrequencyRange(6000, 20000),
}

FREQUENCY_RANGES_SIMPLE = {
    'low': FrequencyRange(20, 300),
    'mid': FrequencyRange(300, 4000),
    'high': FrequencyRange(4000, 24000),
}

MIN_MIDI = 21
MAX_MIDI = 108

class AudioInputSource(object):

    _audio = None
    _stream = None
    _callbacks = []
    _audioWindowSize = 4

    AUDIO_CONFIG_SCHEMA = vol.Schema({
        vol.Optional('sample_rate', default = 60): int,
        vol.Optional('mic_rate', default = 44100): int,
        vol.Optional('window_size', default = 4): int,
        vol.Optional('device_index', default = 0): int
    }, extra=vol.ALLOW_EXTRA)

    def __init__(self, ledfx, config):
        self._config = self.AUDIO_CONFIG_SCHEMA(config)
        self._ledfx = ledfx

        self._volume_filter = ExpFilter(np.zeros(1), alpha_decay=0.01, alpha_rise=0.1)

    def activate(self):

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        _LOGGER.info("Audio Input Devices:")
        info = self._audio.get_host_api_info_by_index(0)
        for i in range(0, info.get('deviceCount')):
            if (self._audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                _LOGGER.info("  [{}] {}".format(i, self._audio.get_device_info_by_host_api_device_index(0, i).get('name')))

        frames_per_buffer = int(self._config['mic_rate'] / self._config['sample_rate'])
        self._raw_audio_sample = np.zeros(frames_per_buffer, dtype = np.float32)

        self._stream = self._audio.open(
            input_device_index=self._config['device_index'],
            format=pyaudio.paFloat32,
            channels=1,
            rate=self._config['mic_rate'],
            input=True,
            frames_per_buffer = frames_per_buffer,
            stream_callback = self._audio_sample_callback)
        self._stream.start_stream()

        _LOGGER.info("Audio source opened.")

    def deactivate(self):
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
        self._callbacks.remove(callback)

        if len(self._callbacks) == 0:
            self.deactivate()

    def _audio_sample_callback(self, in_data, frame_count, time_info, status):
        """Callback for when a new audio sample is acquired"""
        self._raw_audio_sample = np.fromstring(in_data, dtype=np.float32)

        self._invalidate_caches()
        self._invoke_callbacks()

        return (self._raw_audio_sample, pyaudio.paContinue)

    def _invoke_callbacks(self):
        """Notifies all clients of the new data"""
        for callback in self._callbacks:
            callback()

    def _invalidate_caches(self):
        """Invalidates the necessary cache"""
        self.volume.cache_clear()

    def audio_sample(self, pre_emphasis = 0.97):
        """Returns the raw audio sample"""

        sample = self._raw_audio_sample

        # TODO: Added a pre-emphasis which seems to help amplify the higher
        # frequencies giving a more balanced melbank. Need to evaluate how
        # this fully impacts the effects.
        if pre_emphasis:
            sample = np.append(sample[0], sample[1:] - pre_emphasis * sample[:-1])

        return sample

    @lru_cache(maxsize=32)
    def volume(self, filtered = True):
        if filtered:
            return self._volume_filter.update(self.volume(filtered = False))
        return np.abs(np.max(self._rolling_window)-np.min(self._rolling_window))/2**16 

class MelbankInputSource(AudioInputSource):

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('sample_rate', default = 60): int,
        vol.Optional('mic_rate', default = 44100): int,
        vol.Optional('window_size', default = 4): int,
        vol.Optional('samples', default = 24): int,
        vol.Optional('fft_size', default = 1024): int,
        vol.Optional('min_frequency', default = 20): int,
        vol.Optional('max_frequency', default = 18000): int,
        vol.Optional('min_volume', default = -70.0): float,
        vol.Optional('min_volume_count', default = 20): int,
        vol.Optional('coeffs_type', default = "mel"): str,
        vol.Optional('power', default = 0): int
    }, extra=vol.ALLOW_EXTRA)

    def __init__(self, ledfx, config):
        config = self.CONFIG_SCHEMA(config)
        super().__init__(ledfx, config)

        # Setup the phase vocoder
        self.pv = aubio.pvoc(
            self._config['fft_size'], 
            self._config['mic_rate'] // self._config['sample_rate'])

        # Few difference coefficient types for experimentation
        if self._config['coeffs_type'] == 'triangle':
            #self.melbank_frequencies = np.array([60, 80, 200, 400, 800, 1600, 3200, 6400, 12800, 24000]).astype(np.float32)
            self.melbank_frequencies = np.array([20, 60, 80, 200, 400, 800, 1200, 1600, 3200, 6400, 10000, 15000, 24000]).astype(np.float32)
            # self.melbank_frequencies = np.linspace(
            #     self._config['min_frequency'],
            #     self._config['max_frequency'],
            #     self._config['samples']).astype(np.float32)
            # self.melbank_frequencies = np.geomspace(
            #     self._config['min_frequency'],
            #     self._config['max_frequency'],
            #     self._config['samples']).astype(np.float32)
            self._config['samples'] = len(self.melbank_frequencies) - 2
            self.filterbank = aubio.filterbank(
                self._config['samples'],
                self._config['fft_size'])
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies,
                self._config['mic_rate'])
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        # Slaney coefficients will produce a melbank filter spanning 100Hz to 2000Hz
        if self._config['coeffs_type'] == 'slaney':
            self.filterbank = aubio.filterbank(
                self._config['samples'],
                self._config['fft_size'])
            self.filterbank.set_mel_coeffs_slaney(
                self._config['mic_rate'])

            # Frequencies wil be linearly spaced in the mel scale
            melbank_mel = np.linspace(
                aubio.hztomel(100),
                aubio.hztomel(2000),
                self._config['samples'])
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel])

        # Standard mel coefficients 
        if self._config['coeffs_type'] == 'mel':
            self.filterbank = aubio.filterbank(
                self._config['samples'],
                self._config['fft_size'])
            self.filterbank.set_mel_coeffs(
                self._config['mic_rate'],
                self._config['min_frequency'],
                self._config['max_frequency'])
            
            # Frequencies wil be linearly spaced in the mel scale
            melbank_mel = np.linspace(
                aubio.hztomel(self._config['min_frequency']),
                aubio.hztomel(self._config['max_frequency']),
                self._config['samples'])
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel])

        # HTK mel coefficients
        if self._config['coeffs_type'] == 'htk':
            self.f = aubio.filterbank(
                self._config['samples'],
                self._config['fft_size'])
            self.filterbank.set_mel_coeffs_htk(
                self._config['mic_rate'],
                self._config['min_frequency'],
                self._config['max_frequency'])

            # Frequencies wil be linearly spaced in the mel scale
            melbank_mel = np.linspace(
                aubio.hztomel(self._config['min_frequency']),
                aubio.hztomel(self._config['max_frequency']),
                self._config['samples'])
            self.melbank_frequencies = np.array(
                [aubio.meltohz(mel) for mel in melbank_mel])

        self.melbank_frequencies = self.melbank_frequencies.astype(int)

        # Power scaling
        if self._config['power']:
            self.filterbank.set_power(self._config['power'])

        # # Apply a pre-filter on the coeffs based on a log scale of the
        # # frequency. This helps to raise the highes to the same level
        # coeffs = self.filterbank.get_coeffs()
        # for i in range(len(coeffs) - 1):
        #     coeffs[i] *= np.log10(self.melbank_frequencies[i])
        # self.filterbank.set_coeffs(coeffs)

        # Apply a A weighthing filter to balance out the mids
        # self.filter = aubio.digital_filter(7)
        # self.filter.set_a_weighting(samplerate)

        self.silence_count = self._config['min_volume_count']
        self._initialize_melbank()

    def _invalidate_caches(self):
        """Invalidates the cache for all melbank related data"""
        super()._invalidate_caches()
        self.melbank.cache_clear()
        self.melbank_filtered.cache_clear()
        self.interpolated_melbank.cache_clear()

    def _initialize_melbank(self):
        """Initialize all the melbank related variables"""

        
        self.db_spl_filter = ExpFilter(-90, alpha_decay=0.01, alpha_rise=0.99)
        self.mel_gain = ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.01, alpha_rise=0.99)
        self.mel_smoothing = ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.2, alpha_rise=0.99)
        self.common_filter = ExpFilter(alpha_decay = 0.99, alpha_rise = 0.01)

    @lru_cache(maxsize=32)
    def melbank(self):
        """Returns the raw melbank curve"""

        raw_sample = self.audio_sample()
        
        self.db_spl_filter.update(aubio.db_spl(raw_sample))
        if self.db_spl_filter.value > self._config['min_volume']:

            fftgrain = self.pv(raw_sample)
            filter_banks = self.filterbank(fftgrain)
            self._ledfx.events.fire_event(GraphUpdateEvent(
                'raw', filter_banks, np.array(self.melbank_frequencies)))

            # fftgrain = self.pv(self.audio_sample().astype(np.float32))
            # filter_banks = self.filterbank(fftgrain) / self.scale
            # self._ledfx.events.fire_event(GraphUpdateEvent(
            #     'melbankUnfiltered', filter_banks, np.array(self.melbank_frequencies)))

            self.mel_gain.update(np.mean(filter_banks))
            #filter_banks -= (np.mean(filter_banks, axis=0) + 1e-8)
            filter_banks /= self.mel_gain.value
            filter_banks = self.mel_smoothing.update(filter_banks)
        else:
            filter_banks = np.zeros(self._config['samples'])

        self._ledfx.events.fire_event(GraphUpdateEvent(
            'melbank', filter_banks, np.array(self.melbank_frequencies)))
        return filter_banks

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
    def interpolated_melbank(self, size, filtered = True):
        """Returns a melbank curve interpolated up to a given size"""
        if filtered is True:
            return math.interpolate(self.melbank_filtered(), size)
                
        return math.interpolate(self.melbank(), size)


# TODO: Rationalize
_melbank_source = None
def get_melbank_input_source(ledfx):
    global _melbank_source
    if _melbank_source is None:
        _melbank_source = MelbankInputSource(ledfx, ledfx.config.get('audio', {}))
    return _melbank_source

@Effect.no_registration
class AudioReactiveEffect(Effect):
    """
    Base for audio reactive effects. This really just subscribes
    to the melbank input source and forwards input along to the 
    subclasses. This can be expanded to do the common r/g/b filters.
    """

    def activate(self, channel):
        _LOGGER.info('Activating AudioReactiveEffect.')
        super().activate(channel)
        get_melbank_input_source(self._ledfx).subscribe(
            self._audio_data_updated)

    def deactivate(self):
        _LOGGER.info('Deactivating AudioReactiveEffect.')
        get_melbank_input_source(self._ledfx).unsubscribe(
            self._audio_data_updated)
        super().deactivate()

    def create_filter(self, alpha_decay, alpha_rise):
        # TODO: Since most effects reuse the same general filters it would be
        # nice for all that computation to be shared. This mean that shared
        # filters are needed, or if there is really just a small set of filters
        # that those get added to the Melbank input source instead.
        return ExpFilter(alpha_decay=alpha_decay, alpha_rise=alpha_rise)

    def _audio_data_updated(self):
        if self.is_active:
            self.audio_data_updated(get_melbank_input_source(self._ledfx))

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updated. Should
        be implemented by subclasses
        """
        pass
