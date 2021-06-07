import logging

# import time
from collections import namedtuple
from math import log

import aubio
import numpy as np

# import sounddevice as sd
import voluptuous as vol

import ledfx.effects.mel as mel
from ledfx.effects import smooth
from ledfx.effects.math import ExpFilter
from ledfx.events import GraphUpdateEvent

# GET RID OF THIS STUFF IT ISNT REALLY NECESSARY HERE

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

#

_LOGGER = logging.getLogger(__name__)

MELBANK_COEFFS_TYPES = (
    "triangle",
    "bark",
    "slaney",
    "mel",
    "htk",
    "scott",
    "scott_mel",
    "matt_mel",
    "fixed",
    "fixed_simple",
)

# this is really determined by the mic rate.
# I've forced fft to use mic rate of 20000Hz even if mic is actually ~40000Hz.
# This increases frequency resolution massively, especially noticable for bass
# where frequency differs by only 10s of Hz
MAX_FREQ = 10000
MIN_FREQ = 20


class Melbank:
    """A single melbank"""

    # This whole schema isn't really user accessible/editable. Might open it up in future.
    MELBANK_CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional("samples", default=24): vol.All(
                vol.Coerce(int), vol.Range(0, 100)
            ),
            vol.Optional("min_frequency", default=MIN_FREQ): vol.All(
                vol.Coerce(int), vol.Range(MIN_FREQ, MAX_FREQ)
            ),
            vol.Optional("max_frequency", default=MAX_FREQ): vol.All(
                vol.Coerce(int), vol.Range(MIN_FREQ, MAX_FREQ)
            ),
            vol.Optional("min_volume", default=-70.0): float,
            vol.Optional("peak_isolation", default=0.4): float,
            vol.Optional("coeffs_type", default="matt_mel"): vol.In(
                MELBANK_COEFFS_TYPES
            ),
            vol.Optional("pre_emphasis", default=1.5): float,
        },
        extra=vol.ALLOW_EXTRA,
    )

    def __init__(self, audio, config):
        """Initialize all the melbank related variables"""
        self._audio = audio
        self._config = self.MELBANK_CONFIG_SCHEMA(config)

        fft_size = self._audio._config["fft_size"]
        mic_rate = self._audio._config["mic_rate"]

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
                self._config["samples"], fft_size
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, mic_rate
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
                self._config["samples"], fft_size
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, mic_rate
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        # Slaney coefficients will always produce 40 samples spanning 133Hz to
        # 6000Hz
        if self._config["coeffs_type"] == "slaney":
            self.filterbank = aubio.filterbank(40, fft_size)
            self.filterbank.set_mel_coeffs_slaney(mic_rate)

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
                self._config["samples"], fft_size
            )
            self.filterbank.set_mel_coeffs(
                mic_rate,
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
                self._config["samples"], fft_size
            )
            self.filterbank.set_mel_coeffs_htk(
                mic_rate,
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
                num_fft_bands=int(fft_size // 2) + 1,
                sample_rate=mic_rate,
            )
            self.filterbank = aubio.filterbank(
                self._config["samples"], fft_size
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
                self._config["samples"], fft_size
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, mic_rate
            )
            self.melbank_frequencies = self.melbank_frequencies[1:-1]

        # Modified scott_mel, spreads out the low range and compresses the
        # highs
        if self._config["coeffs_type"] == "matt_mel":

            def hertz_to_matt(freq):
                return 3700.0 * log(1 + (freq / 200.0), 13)

            def matt_to_hertz(matt):
                return 200.0 * (13 ** (matt / 3700.0)) - 200.0

            melbank_matt = np.linspace(
                hertz_to_matt(self._config["min_frequency"]),
                hertz_to_matt(self._config["max_frequency"]),
                self._config["samples"] + 2,
            )
            self.melbank_frequencies = np.array(
                [matt_to_hertz(matt) for matt in melbank_matt]
            ).astype(np.float32)

            self.filterbank = aubio.filterbank(
                self._config["samples"], fft_size
            )
            self.filterbank.set_triangle_bands(
                self.melbank_frequencies, mic_rate
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
                num_fft_bands=int(fft_size // 2) + 1,
                sample_rate=mic_rate,
            )

            self._config["samples"] = len(center_frequencies_hz)
            self.filterbank = aubio.filterbank(
                self._config["samples"], fft_size
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
                num_fft_bands=int(fft_size // 2) + 1,
                sample_rate=mic_rate,
            )

            self._config["samples"] = len(center_frequencies_hz)
            self.filterbank = aubio.filterbank(
                self._config["samples"], fft_size
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
        self.mel_gain = ExpFilter(alpha_decay=0.05, alpha_rise=0.99)
        self.mel_smoothing = ExpFilter(alpha_decay=0.5, alpha_rise=0.99)
        self.common_filter = ExpFilter(alpha_decay=0.99, alpha_rise=0.01)
        self.diff_filter = ExpFilter(alpha_decay=0.02, alpha_rise=0.99)

        # the simplest pre emphasis. clean and fast.
        self.pre_emphasis = np.arange(fft_size // 2 + 1) + 1
        self.pre_emphasis = np.log(self.pre_emphasis) / np.log(1.1)

    def __call__(self, frequency_domain, filter_banks, filter_banks_filtered):
        """
        computes the melbank curve for frequency domain .
        this function has been modified a bit to make sure all operations
        are applied to filter_banks in place
        """

        # Compute the filterbank from the frequency information.
        frequency_domain.norm *= self.pre_emphasis
        filter_banks[:] = self.filterbank(frequency_domain)
        # adjustable power (peak isolation) based on parameter a (0-1)
        # a=0    -> linear response (filter bank value maps to itself)
        # a=0.4  -> roughly equivalent to filter_banks ** 2.0
        # a=0.6  -> roughly equivalent to filter_banks ** 3.0
        # a=1    -> no response (infinite power as filter bank value approaches 1)
        # https://www.desmos.com/calculator/xxa2l9radu
        np.power(
            filter_banks,
            np.tan(0.5 * np.pi * (self._config["peak_isolation"] + 1) / 2),
            out=filter_banks,
        )

        self.mel_gain.update(np.max(smooth(filter_banks, sigma=1.0)))
        filter_banks /= self.mel_gain.value
        filter_banks[:] = self.mel_smoothing.update(filter_banks)

        self.common_filter.update(filter_banks)
        filter_banks_filtered[:] = self.diff_filter.update(
            filter_banks - self.common_filter.value
        )


class Melbanks:
    """
    Creates a set of filterbanks to process FFT at different resolutions.
    A constant amount are used to ensure consistent performance.
    If each display had its own melbank, you could run into performance issues
    with a high number of displays.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            # "max_frequencies" specifies the number of melbanks, and the highest frequency they each go to.
            # eg. [100,1000,10000] will create:
            # Frequency: 1Hz          100Hz          1000Hz            10000Hz            20000Hz
            # melbank 1: [--------------]
            # melbank 2: [------------------------------]
            # melbank 3: [-------------------------------------------------]
            vol.Optional("max_frequencies", default=[350, 2000, 10000]): [
                vol.All(vol.Coerce(int), vol.Range(0, 10000))
            ],
            vol.Optional("min_frequency", default=MIN_FREQ): vol.All(
                vol.Coerce(int), vol.Range(0, MAX_FREQ)
            ),
        },
        extra=vol.ALLOW_EXTRA,
    )

    DEFAULT_MELBANK_CONFIG = Melbank.MELBANK_CONFIG_SCHEMA({})
    MELBANK_PRE_EMPHASIS = (1.1, 1.5, 2.0)

    def __init__(self, ledfx, audio, config):
        self._ledfx = ledfx
        self._audio = audio
        self.update_config(config)

    def update_config(self, config):
        # validate config
        self._config = self.CONFIG_SCHEMA(config)
        # set up the melbanks
        self.melbank_processors = tuple(
            Melbank(
                self._audio,
                self.DEFAULT_MELBANK_CONFIG
                | {
                    "max_frequency": freq,
                    "pre_emphasis": self.MELBANK_PRE_EMPHASIS[i],
                },
            )
            for i, freq in enumerate(self._config["max_frequencies"])
        )
        # some useful info that will be accessed faster as variables
        self.mel_count = len(self._config["max_frequencies"])
        self.mel_len = self.DEFAULT_MELBANK_CONFIG["samples"]
        # set up melbank data buffers.
        # these are stored as numpy arrays in a tuple to allow direct access to the buffers
        # should be a bit faster than a list!
        self.melbanks = tuple(
            np.zeros(self.mel_len) for _ in range(self.mel_count)
        )
        self.melbanks_filtered = tuple(
            np.zeros(self.mel_len) for _ in range(self.mel_count)
        )

    def __call__(self):
        # fastest way i could think of.
        # melbank function is directly referenced by the self.melbanks tuple.
        # melbank function is given the data buffer to operate directly on
        # rather than returning and assigning the data.
        frequency_domain = self._audio._frequency_domain
        volume = (
            self._audio.volume(filtered=True)
            < self._audio._config["min_volume"]
        )

        for i in range(self.mel_count):
            if volume:
                self.melbank_processors[i](
                    frequency_domain,
                    self.melbanks[i],
                    self.melbanks_filtered[i],
                )
            else:
                self.melbanks[i][:] = 0
                self.melbanks_filtered[i][:] = 0

            if self._ledfx.dev_enabled():
                self._ledfx.events.fire_event(
                    GraphUpdateEvent(
                        f"melbank_{i}",
                        self.melbanks[i],
                        np.array(
                            self.melbank_processors[i].melbank_frequencies
                        ),
                    )
                )
