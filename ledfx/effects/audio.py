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

    def __init__(self, mic_rate, sample_rate):
        self._mic_rate = mic_rate
        self._sample_rate = sample_rate
        self._frames_per_buffer = int(self._mic_rate / self._sample_rate)

    def activate(self):

        if self._audio is None:
            self._audio = pyaudio.PyAudio()

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._mic_rate,
            input=True,
            frames_per_buffer = self._frames_per_buffer,
            stream_callback = self._audio_sample_callback)
        self._stream.start_stream()

        _LOGGER.info("Audio source opened.")

    def deactivate(self):
        self._stream.stop_stream()
        self._stream.close()
        self._stream = None
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
        self._audio_data = np.fromstring(in_data, dtype=np.int16)
        self._invalidate_caches()
        self._invoke_callbacks()

        return (self._audio_data, pyaudio.paContinue)

    def _invoke_callbacks(self):
        """Notifies all clients of the new data"""
        for callback in self._callbacks:
            callback()

    def _invalidate_caches(self):
        """Invalidates the necessary cache"""
        self.volume.cache_clear()

    def audio_sample(self):
        """Returns the raw audio sample"""
        return self._audio_data

    @lru_cache(maxsize=32)
    def volume(self):
        return np.max(np.abs(self.audio_sample()))

class MelbankInputSource(AudioInputSource):

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional('sample_rate', default = 60): int,
        vol.Optional('mic_rate', default = 44100): int,
        vol.Optional('window_size', default = 4): int,
        vol.Optional('samples', default = 24): int,
        vol.Optional('min_frequency', default = 0): int,
        vol.Optional('max_frequency', default = 22050): int,
    })

    def __init__(self, config):
        self._config = self.CONFIG_SCHEMA(config)
        super().__init__(
            sample_rate = self._config['sample_rate'],
            mic_rate = self._config['mic_rate'])

        self._initialize_melbank()

    def _invalidate_caches(self):
        """Invalidates the cache for all melbank related data"""
        super()._invalidate_caches()
        self.melbank.cache_clear()
        self.sample_melbank.cache_clear()
        self.interpolated_melbank.cache_clear()

    def _initialize_melbank(self):
        """Initialize all the melbank related variables"""

        self._init = True
        self._y_roll = np.random.rand(self._config['window_size'], int(self._config['mic_rate'] / self._config['sample_rate'])) / 1e16

        self._fft_window = np.hamming(int((self._config['window_size'] * self._config['mic_rate']) / self._config['sample_rate']))

        samples = int(self._config['mic_rate'] * self._config['window_size'] / (2.0 * self._config['sample_rate']))
        self.mel_y, (_, self.mel_x) = mel.compute_melmat(num_mel_bands=self._config['samples'],
                                            freq_min=self._config['min_frequency'],
                                            freq_max=self._config['max_frequency'],
                                            num_fft_bands=samples,
                                            sample_rate=self._config['mic_rate'])
        self.fft_plot_filter = ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.5, alpha_rise=0.99)
        self.mel_gain =        ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.01, alpha_rise=0.99)
        self.mel_smoothing =   ExpFilter(np.tile(1e-1, self._config['samples']), alpha_decay=0.5, alpha_rise=0.99)

    @lru_cache(maxsize=32)
    def melbank(self):
        """Returns the raw melbank curve"""
        # TODO: This code was pretty much taken as is without any
        # changes other than some minor cleanup. Need to eventually
        # work out the math and fix this up and ideally use some
        # seconday library for the heavy lifting.

        # Update the rolling window and sum up the samples
        self._y_roll[:-1] = self._y_roll[1:]
        self._y_roll[-1, :] = np.copy(self.audio_sample())
        y_data = np.concatenate(self._y_roll, axis=0).astype(np.float32)

        # Perform hamming function to reduce frequency bleeding
        y_data *= self._fft_window

        # Pad with zeros until the next power of two
        N = len(y_data)
        N_zeros = 2**int(np.ceil(np.log2(N))) - N
        y_padded = np.pad(y_data, (0, N_zeros), mode='constant')

        # Construct a Mel filterbank from the FFT data
        YS = np.abs(np.fft.rfft(y_padded)[:N // 2])
        mel = np.atleast_2d(YS).T * self.mel_y.T

        # Scale data to values more suitable for visualization
        mel = np.sum(mel, axis=0)
        mel = mel**2.0

        # Gain normalization
        self.mel_gain.update(np.max(gaussian_filter1d(mel, sigma=1.0)))
        mel /= self.mel_gain.value
        self.mel = self.mel_smoothing.update(mel)

        return self.mel

    @lru_cache(maxsize=32)
    def sample_melbank(self, hz):
        """Samples the melbank curve at a given frequency"""
        pass

    @lru_cache(maxsize=32)
    def interpolated_melbank(self, size, filtered = True):
        """Returns a melbank curve interpolated up to a given size"""
        if filtered is True:
            interpolated_y = self.interpolated_melbank(size, filtered=False)
            return self.get_filter(
                filter_key = "interpolated_melbank", 
                filter_size = size,
                alpha_decay = 0.99,
                alpha_rise = 0.01).update(interpolated_y)
        return math.interpolate(self.melbank(), size)

    @lru_cache(maxsize=None)
    def get_filter(self, filter_key, filter_size, alpha_decay, alpha_rise):
        """
        Gets a filter given a specific size and identifier. This 
        is implemented as a simply param cache and does not get reset
        when new audio data arrives.
        """
        _LOGGER.info("Initializing new melbank filter {}".format(filter_key))
        return ExpFilter(np.tile(0.01, filter_size), alpha_decay=alpha_decay, alpha_rise=alpha_rise)


# TODO: Rationalize
_melbank_source = None
def get_melbank_input_source():
    global _melbank_source
    if _melbank_source is None:
        _melbank_source = MelbankInputSource({})
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

    def _audio_data_updated(self):
        self.audio_data_updated(get_melbank_input_source())

    def audio_data_updated(self, data):
        """
        Callback for when the audio data is updatead. Should
        be implemented by subclasses
        """
        pass
