"""Per-block audio analysis, independent of the LedFx core.

AudioAnalyzer holds the whole signal chain that used to live inside
AudioInputSource/AudioAnalysisSource: resampling, the optional delay line,
pre-emphasis, the phase vocoder, the melbanks and the aubio detectors. It needs
no LedFx instance, no event bus and no config persistence, only plain config
values, so the same object can run inside the LedFx process or in a separate
audio process (see ledfx.audio_process) without a second implementation.

Every block runs the same steps, in the same order, that AudioAnalysisSource
ran through its subscribed callbacks: melbanks, pitch, onset, bar oscillator
(which drives the tempo tracker), volume beat, frequency power.

Steps nothing reads can be skipped: see set_wanted() and ANALYSIS_GROUPS.
"""

import logging
import queue
import time
from collections import deque

import aubio
import numpy as np
import samplerate

from ledfx.effects.math import ExpFilter
from ledfx.effects.melbank import MIC_RATE, Melbank

_LOGGER = logging.getLogger(__name__)

# Upper edges of the beat, bass, mids and high bands, in Hz.
FREQ_MAX_MELS = (100, 250, 3000, 10000)

PRE_EMPHASIS_COEFFS = {
    "matt_mel": (0.8268, -1.6536, 0.8268, -1.6536, 0.6536),
    "scott_mel": (1.3662, -1.9256, 0.5621, -1.9256, 0.9283),
}
PRE_EMPHASIS_DEFAULT = (0.85870, -1.71740, 0.85870, -1.71605, 0.71874)

# What set_wanted() can switch off, one name per result group a reader asks
# for. Onset and the tempo tracker always run: they drive events.
ANALYSIS_GROUPS = (
    "melbank0",
    "melbank1",
    "melbank2",
    "pitch",
    "volume_beat",
    "freq_power",
)


class AudioAnalyzer:
    """Analyses one audio block at a time and keeps the results.

    Args:
        audio_config: the audio section of the LedFx config (AudioConfig dump).
        melbank_configs: one fully merged config dict per melbank processor,
            as Melbanks builds them (global settings already applied).
        coeffs_type: the melbanks coeffs_type, which picks the pre-emphasis.
    """

    def __init__(self, audio_config, melbank_configs, coeffs_type):
        self.sample_rate = audio_config["sample_rate"]
        self.fft_size = audio_config["fft_size"]
        self.min_volume = audio_config["min_volume"]
        self.hop = MIC_RATE // self.sample_rate

        self.resampler = samplerate.Resampler("sinc_fastest", channels=1)

        samples_to_delay = int(0.001 * audio_config["delay_ms"] * self.sample_rate)
        self.delay_queue = (
            queue.Queue(maxsize=samples_to_delay) if samples_to_delay else None
        )

        self.pre_emphasis = aubio.digital_filter(3)
        self.pre_emphasis.set_biquad(
            *PRE_EMPHASIS_COEFFS.get(coeffs_type, PRE_EMPHASIS_DEFAULT)
        )
        self.phase_vocoder = aubio.pvoc(self.fft_size, self.hop)
        self.frequency_domain_null = aubio.cvec(self.fft_size)
        self.frequency_domain = self.frequency_domain_null

        self.raw_sample = np.zeros(self.hop, dtype=np.float32)
        self.processed_sample = None
        self.volume_raw = -90
        self.volume_filter = ExpFilter(-90, alpha_decay=0.99, alpha_rise=0.99)
        self.has_volume_measurement = False

        self.melbank_processors = [Melbank(None, cfg) for cfg in melbank_configs]
        mel_len = self.melbank_processors[0]._config.samples
        self.melbanks = tuple(np.zeros(mel_len) for _ in self.melbank_processors)
        self.melbanks_filtered = tuple(
            np.zeros(mel_len) for _ in self.melbank_processors
        )

        fft_params = (self.fft_size, self.hop, MIC_RATE)
        self.tempo = aubio.tempo(audio_config["tempo_method"], *fft_params)
        self.onset_detector = aubio.onset(audio_config["onset_method"], *fft_params)
        self.pitch_detector = aubio.pitch(audio_config["pitch_method"], *fft_params)
        self.pitch_detector.set_unit("midi")
        self.pitch_detector.set_tolerance(audio_config["pitch_tolerance"])

        self.pitch = 0
        self.onset = False
        self.bpm_beat_now = False
        self.volume_beat_now = False
        self.bar_oscillator = 0.0

        self.beat_counter = 0
        self.beat_timestamp = time.time()
        self.beat_period = 2

        self.freq_power_raw = np.zeros(len(FREQ_MAX_MELS))
        self.freq_power_filter = ExpFilter(
            np.zeros(len(FREQ_MAX_MELS)), alpha_decay=0.2, alpha_rise=0.97
        )
        mid_freqs = self.melbank_processors[2].melbank_frequencies
        self.freq_mel_indexes = [
            next((i for i, f in enumerate(mid_freqs) if f > freq), len(mid_freqs))
            for freq in FREQ_MAX_MELS
        ]

        low_freqs = self.melbank_processors[0].melbank_frequencies
        self.beat_max_mel_index = next(
            (i - 1 for i, f in enumerate(low_freqs) if f > FREQ_MAX_MELS[0]),
            low_freqs[-1],
        )
        self.beat_min_percent_diff = 0.5
        self.beat_min_time_since = 0.1
        self.beat_min_amplitude = 0.5
        self.beat_power_history_len = int(self.sample_rate * 0.2)
        self.beat_prev_time = time.time()
        self.beat_power_history = deque(maxlen=self.beat_power_history_len)

        self._wanted = None
        self._melbanks_needed = None

    def set_wanted(self, groups):
        """Compute only the result groups something reads.

        groups: names from ANALYSIS_GROUPS, or None to compute everything (the
        default). A skipped group keeps its last values, except volume_beat_now,
        which reads False so a skipped beat never fires as an event. The volume
        beat needs melbank 0 and freq_power needs melbank 2, so those melbanks
        are computed whenever their consumer is wanted.
        """
        if groups is None:
            self._melbanks_needed = None
            self._wanted = None
            return
        groups = frozenset(groups)
        if (
            self._wanted is not None
            and "volume_beat" not in self._wanted
            and "volume_beat" in groups
        ):
            # Powers from before the gap say nothing about the music now.
            self.beat_power_history.clear()
        needed = {
            i for i in range(len(self.melbank_processors)) if f"melbank{i}" in groups
        }
        if "volume_beat" in groups:
            needed.add(0)
        if "freq_power" in groups:
            needed.add(2)
        self._melbanks_needed = frozenset(needed)
        self._wanted = groups

    def _wants(self, group):
        wanted = self._wanted
        return wanted is None or group in wanted

    @property
    def volume_filtered(self):
        return self.volume_filter.value

    @property
    def freq_power_filtered(self):
        return self.freq_power_filter.value

    def process(self, in_data):
        """Analyse one block of float32 mono samples at any input rate.

        Returns False when the block was discarded (wrong length after
        resampling) or only went into the delay line, True when a new set of
        results is available.
        """
        raw = np.frombuffer(in_data, dtype=np.float32)
        if len(raw) != self.hop:
            sample = self.resampler.process(raw, self.hop / len(raw))
        else:
            sample = raw
        if len(sample) != self.hop:
            return False

        if self.delay_queue is not None:
            try:
                self.delay_queue.put_nowait(sample)
                return False
            except queue.Full:
                self.raw_sample = self.delay_queue.get_nowait()
                self.delay_queue.put_nowait(sample)
        else:
            self.raw_sample = sample

        self._pre_process()
        self._melbanks()
        if self._wants("pitch"):
            self.pitch = self._detect(self.pitch_detector, 0)
        self.onset = bool(self._detect(self.onset_detector, False))
        self._bar_oscillator()
        if self._wants("volume_beat"):
            self._volume_beat()
        else:
            self.volume_beat_now = False
        if self._wants("freq_power"):
            self._freq_power()
        return True

    def _pre_process(self):
        self.raw_sample[np.isnan(self.raw_sample)] = 0
        volume = 1 + aubio.db_spl(self.raw_sample) / 100
        self.volume_raw = max(0, min(1, volume))
        self.volume_filter.update(self.volume_raw)
        self.has_volume_measurement = True

        if self.volume_filter.value > self.min_volume:
            self.processed_sample = self.pre_emphasis(self.raw_sample)
            self.frequency_domain = self.phase_vocoder(self.processed_sample)
        else:
            self.frequency_domain = self.frequency_domain_null

    def _melbanks(self):
        if self.volume_filter.value > self.min_volume:
            needed = self._melbanks_needed
            for i, proc in enumerate(self.melbank_processors):
                if needed is None or i in needed:
                    proc(
                        self.frequency_domain,
                        self.melbanks[i],
                        self.melbanks_filtered[i],
                    )
        else:
            for melbank in self.melbanks:
                melbank[:] = 0
            for melbank in self.melbanks_filtered:
                melbank[:] = 0

    def _detect(self, detector, fallback):
        try:
            return detector(self.raw_sample)[0]
        except ValueError as e:
            _LOGGER.warning("%s", e)
            return fallback

    def _bar_oscillator(self):
        self.bpm_beat_now = bool(self._detect(self.tempo, False))
        if self.bpm_beat_now:
            self.beat_counter = (self.beat_counter + 1) % 4
            self.beat_period = self.tempo.get_period_s()
            self.beat_timestamp = time.time()
            self.bar_oscillator = self.beat_counter
        else:
            time_since_beat = time.time() - self.beat_timestamp
            oscillator = (
                1 - (self.beat_period - time_since_beat) / self.beat_period
            ) + self.beat_counter
            self.bar_oscillator = oscillator % 4

    def _volume_beat(self):
        time_now = time.time()
        melbank = self.melbanks[0][: self.beat_max_mel_index]
        beat_power = np.sum(melbank)
        melbank_max = np.max(melbank)
        if sum(self.beat_power_history) > 0:
            difference = (
                beat_power * self.beat_power_history_len / sum(self.beat_power_history)
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
            self.volume_beat_now = True
        else:
            self.volume_beat_now = False

    def _freq_power(self):
        melbank = self.melbanks[2]
        idx = self.freq_mel_indexes
        self.freq_power_raw[0] = np.average(melbank[: idx[0]])
        self.freq_power_raw[1] = np.average(melbank[idx[0] : idx[1]])
        self.freq_power_raw[2] = np.average(melbank[idx[1] : idx[2]])
        self.freq_power_raw[3] = np.average(melbank[idx[2] : idx[3]])
        np.minimum(self.freq_power_raw, 1, out=self.freq_power_raw)
        self.freq_power_filter.update(self.freq_power_raw)

    def snapshot(self):
        """The results of the latest block as plain values, for sending to
        another process. SnapshotView turns them back into the attributes
        this class has, so readers cannot tell the two apart."""
        return {
            "volume_raw": float(self.volume_raw),
            "volume_filtered": float(self.volume_filter.value),
            "has_volume_measurement": self.has_volume_measurement,
            "melbanks": [m.tobytes() for m in self.melbanks],
            "melbanks_filtered": [m.tobytes() for m in self.melbanks_filtered],
            "melbank_dtype": self.melbanks[0].dtype.str,
            "pitch": float(self.pitch),
            "onset": bool(self.onset),
            "bpm_beat_now": bool(self.bpm_beat_now),
            "volume_beat_now": bool(self.volume_beat_now),
            "bar_oscillator": float(self.bar_oscillator),
            "beat_counter": int(self.beat_counter),
            "tempo_bpm": float(self.tempo.get_bpm()),
            "tempo_confidence": float(self.tempo.get_confidence()),
            "tempo_period_s": float(self.tempo.get_period_s()),
            "freq_power_raw": np.asarray(
                self.freq_power_raw, dtype=np.float64
            ).tobytes(),
            "freq_power_filtered": np.asarray(
                self.freq_power_filter.value, dtype=np.float64
            ).tobytes(),
        }


class _SnapshotTempo:
    """The read side of aubio's tempo tracker, from a snapshot."""

    def __init__(self, bpm, confidence, period_s):
        self._bpm = bpm
        self._confidence = confidence
        self._period_s = period_s

    def get_bpm(self):
        return self._bpm

    def get_confidence(self):
        return self._confidence

    def get_period_s(self):
        return self._period_s


class SnapshotView:
    """A received snapshot with AudioAnalyzer's result attributes.

    The signal itself (raw/processed sample, frequency domain) stays in the
    process that analysed it, so those read as None.
    """

    raw_sample = None
    processed_sample = None
    frequency_domain = None

    def __init__(self, snapshot):
        dtype = np.dtype(snapshot["melbank_dtype"])
        self.volume_raw = snapshot["volume_raw"]
        self.volume_filtered = snapshot["volume_filtered"]
        self.has_volume_measurement = snapshot["has_volume_measurement"]
        self.melbanks = tuple(
            np.frombuffer(b, dtype=dtype) for b in snapshot["melbanks"]
        )
        self.melbanks_filtered = tuple(
            np.frombuffer(b, dtype=dtype) for b in snapshot["melbanks_filtered"]
        )
        self.pitch = snapshot["pitch"]
        self.onset = snapshot["onset"]
        self.bpm_beat_now = snapshot["bpm_beat_now"]
        self.volume_beat_now = snapshot["volume_beat_now"]
        self.bar_oscillator = snapshot["bar_oscillator"]
        self.beat_counter = snapshot["beat_counter"]
        self.tempo = _SnapshotTempo(
            snapshot["tempo_bpm"],
            snapshot["tempo_confidence"],
            snapshot["tempo_period_s"],
        )
        self.freq_power_raw = np.frombuffer(
            snapshot["freq_power_raw"], dtype=np.float64
        )
        self.freq_power_filtered = np.frombuffer(
            snapshot["freq_power_filtered"], dtype=np.float64
        )
