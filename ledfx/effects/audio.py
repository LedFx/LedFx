import time
import logging
import pyaudio
from ledfx.effects import Effect
import voluptuous as vol
from scipy.ndimage.filters import gaussian_filter1d
import ledfx.effects.mel as mel
from ledfx.effects.math import ExpFilter
import ledfx.effects.math as math
from functools import lru_cache
import numpy as np
import collections

_LOGGER = logging.getLogger(__name__)

class AudioInputSource(object):

    _audio = None
    _stream = None
    _callbacks = []
    _audioWindowSize = 4

    AUDIO_CONFIG_SCHEMA = vol.Schema({
        vol.Optional('sample_rate', default = 60): int,
        vol.Optional('mic_rate', default = 44100): int,
        vol.Optional('window_size', default = 4): int
    })

    def __init__(self, ledfx, config):
        self.config = self.AUDIO_CONFIG_SCHEMA(config)
        self.ledfx = ledfx

        self._volume_filter = ExpFilter(np.zeros(1), alpha_decay=0.01, alpha_rise=0.1)

    def activate(self):

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        frames_per_buffer = int(self.config['mic_rate'] / self.config['sample_rate'])
        self._rolling_window = np.random.rand(self.config['window_size'], frames_per_buffer) / 1e16
        self._hamming_window = np.hamming(frames_per_buffer)

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.config['mic_rate'],
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
        """Unregisters a callback with the input srouce"""
        self._callbacks.remove(callback)

        if len(self._callbacks) == 0:
            self.deactivate()

    def _audio_sample_callback(self, in_data, frame_count, time_info, status):
        """Callback for when a new audio sample is acquired"""
        self._rolling_window[:-1] = self._rolling_window[1:]
        self._rolling_window[-1, :] = np.fromstring(in_data, dtype=np.int16)

        self._invalidate_caches()
        self._invoke_callbacks()

        return (self._rolling_window[:-1], pyaudio.paContinue)

    def _invoke_callbacks(self):
        """Notifies all clients of the new data"""
        for callback in self._callbacks:
            callback()

    def _invalidate_caches(self):
        """Invalidates the necessary cache"""
        self.volume.cache_clear()

    def audio_sample(self, rolling_window = True, apply_hamming = True, pre_emphasis = 0.97):
        """Returns the raw audio sample"""

        sample = self._rolling_window
        if not rolling_window:
            sample = self._rolling_window[-1, :]

        # TODO: This was updated to perform the hamming window frame by frame.
        # need to evaluate how this impacts the melbank.
        if apply_hamming:
            sample = sample * self._hamming_window

        # TODO: Added a pre-emphasis which seems to help amplify the higher
        # frequencies giving a more balanaced melbank. Need to evaluate how
        # this fully impacts the effects.
        if pre_emphasis:
            sample = np.append(np.atleast_2d(sample[0]), sample[1:] - 0.97 * sample[:-1], axis = 0)

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
        vol.Optional('samples', default = 22): int,
        vol.Optional('nfft', default = 512): int,
        vol.Optional('min_frequency', default = 0): int,
        vol.Optional('max_frequency', default = 22050): int,
    })

    def __init__(self, ledfx, config):
        self._config = self.CONFIG_SCHEMA(config)
        super().__init__(ledfx, config)

        self._initialize_melbank()

    def _invalidate_caches(self):
        """Invalidates the cache for all melbank related data"""
        super()._invalidate_caches()
        self.melbank.cache_clear()
        self.interpolated_melbank.cache_clear()

    def _initialize_melbank(self):
        """Initialize all the melbank related variables"""

        (self.mel_y, _, _) = self.compute_melmat()
        self.mel_gain = ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.01, alpha_rise=0.99)
        self.mel_smoothing = ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.5, alpha_rise=0.99)
        self.common_filter = ExpFilter(alpha_decay = 0.99, alpha_rise = 0.01)

    def compute_melmat(self):
        return mel.compute_melmat(
            num_mel_bands=self._config['samples'],
            freq_min=self._config['min_frequency'],
            freq_max=self._config['max_frequency'],
            num_fft_bands=int(self._config['nfft'] // 2) + 1,
            sample_rate=self._config['mic_rate'])

    def melbank_frequencies(self):
        """Returns the corresponding frequencies for the melbank"""

        return np.linspace(
            self._config['min_frequency'],
            self._config['max_frequency'],
            self._config['samples'])

    @lru_cache(maxsize=32)
    def melbank(self):
        """Returns the raw melbank curve"""

        # Validate there is a substantial enough volume for processing
        if self.volume() < 0.001:
            filter_banks = np.zeros(self._config['samples'])
            filter_banks = self.mel_smoothing.update(filter_banks)
            return filter_banks

        # Compress the audio data and convert it to a float        
        y_data = np.concatenate(self.audio_sample(), axis=0).astype(np.float32)

        # Pad with zeros until the next power of two
        N = len(y_data)
        N_zeros = 2**int(np.ceil(np.log2(N))) - N
        y_padded = np.pad(y_data, (0, N_zeros), mode='constant')

        # Perform the FFT to get the magnitudes
        magnitude = np.abs(np.fft.rfft(y_padded, self._config['nfft']))
        #power = ((1.0 / self._config['nfft']) * ((magnitude) ** 2))
        
        # Compute the Mel filterbanks from the FFT data and scale
        filter_banks = np.atleast_2d(magnitude).T * self.mel_y.T
        filter_banks = np.sum(filter_banks, axis=0)
        filter_banks = filter_banks**2.0

        # Gain normalization
        self.mel_gain.update(np.max(gaussian_filter1d(filter_banks, sigma=1.0)))
        filter_banks /= self.mel_gain.value
        filter_banks = self.mel_smoothing.update(filter_banks)

        # TODO: Look into some better gain normalization as there seems to be some
        # issues with variable volume.
        #self.mel_gain.update(np.mean(gaussian_filter1d(filter_banks, sigma=1.0)))
        #filter_banks -= (np.mean(filter_banks, axis=0) + 1e-8)

        return filter_banks

    def sample_melbank(self, hz):
        """Samples the melbank curve at a given frequency"""
        return np.interp(hz, self.melbank_frequencies(), self.melbank())

    @lru_cache(maxsize=32)
    def interpolated_melbank(self, size, filtered = True):
        """Returns a melbank curve interpolated up to a given size"""
        if filtered is True:
            interpolated_y = self.interpolated_melbank(size, filtered=False)
            return self.common_filter.update(interpolated_y)
                
        return math.interpolate(self.melbank(), size)


# TODO: Rationalize
_melbank_source = None
def get_melbank_input_source():
    global _melbank_source
    if _melbank_source is None:
        _melbank_source = MelbankInputSource(None, {})
    return _melbank_source

@Effect.no_registration
class AudioReactiveEffect(Effect):
    """
    Base for audio reactive effects. This really just subscribes
    to the melbank input source and forwards input along to the 
    subclasses. This can be expaneded to do the common r/g/b filters.
    """

    def activate(self, channel):
        super().activate(channel)
        get_melbank_input_source().subscribe(
            self._audio_data_updated)

    def deactivate(self):
        get_melbank_input_source().unsubscribe(
            self._audio_data_updated)
        super().deactivate()

    def create_filter(self, alpha_decay, alpha_rise):
        # TODO: Since most effects reuse the same general filters it would be
        # nice for all that computation to be shared. This mean that shared
        # filters are needed, or if there is really just a small set of filters
        # that those get added to the Melbank input source instead.
        return ExpFilter(alpha_decay=alpha_decay, alpha_rise=alpha_rise)

    def _audio_data_updated(self):
        self.audio_data_updated(get_melbank_input_source())

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updatead. Should
        be implemented by subclasses
        """
        pass
