"""This module implements a Mel Filter Bank.
In other words it is a filter bank with triangular shaped bands
arnged on the mel frequency scale.
An example ist shown in the following figure:
.. plot::
    from pylab import plt
    import melbank
    f1, f2 = 1000, 8000
    melmat, (melfreq, fftfreq) = melbank.compute_melmat(6, f1, f2, num_fft_bands=4097)
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(fftfreq, melmat.T)
    ax.grid(True)
    ax.set_ylabel('Weight')
    ax.set_xlabel('Frequency / Hz')
    ax.set_xlim((f1, f2))
    ax2 = ax.twiny()
    ax2.xaxis.set_ticks_position('top')
    ax2.set_xlim((f1, f2))
    ax2.xaxis.set_ticks(melbank.mel_to_hertz(melfreq))
    ax2.xaxis.set_ticklabels(['{:.0f}'.format(mf) for mf in melfreq])
    ax2.set_xlabel('Frequency / mel')
    plt.tight_layout()
    fig, ax = plt.subplots()
    ax.matshow(melmat)
    plt.axis('equal')
    plt.axis('tight')
    plt.title('Mel Matrix')
    plt.tight_layout()
Functions
---------
"""

import numpy as np


def hertz_to_mel(freq):
    """
    Converts frequency values in Hz to Mel-frequency values.

    Parameter
    ---------
    freq : scalar or ndarray
        Frequency value or array in Hz.

    Returns
    -------
    mel : scalar or ndarray
        Mel-frequency value or ndarray in the Mel scale.
    """

    # Convert frequency values in Hz to Mel-frequency values
    return 3340.0 * np.log(1 + (freq / 250.0), 9)


def mel_to_hertz(mel):
    """
    Converts Mel-frequency values to frequency values in Hz.

    Parameter
    ---------
    mel : scalar or ndarray
        Mel-frequency value or ndarray in the Mel scale.

    Returns
    -------
    freq : scalar or ndarray
        Frequency value or array in Hz.
    """

    # Convert Mel-frequency values to frequency values in Hz
    return 250.0 * (9 ** (mel / 3340.0)) - 250.0


def melfrequencies_mel_filterbank(
    num_bands, freq_min, freq_max, num_fft_bands
):
    """
    Returns center frequencies and band edges for a Mel filter bank.

    Parameters
    ----------
    num_bands : int
        Number of Mel bands.
    freq_min : float
        Minimum frequency for the first band.
    freq_max : float
        Maximum frequency for the last band.
    num_fft_bands : int
        Number of FFT bands.

    Returns
    -------
    center_frequencies_mel : ndarray
        Center frequencies of the Mel bands in the Mel scale.
    lower_edges_mel : ndarray
        Lower edges of the Mel bands in the Mel scale.
    upper_edges_mel : ndarray
        Upper edges of the Mel bands in the Mel scale.
    """

    # Convert frequency limits to the Mel scale
    mel_max = hertz_to_mel(freq_max)
    mel_min = hertz_to_mel(freq_min)

    # Compute the Mel band spacing
    delta_mel = abs(mel_max - mel_min) / (num_bands + 1.0)

    # Calculate Mel frequencies for band edges
    frequencies_mel = mel_min + delta_mel * np.arange(0, num_bands + 2)

    # Extract lower edges, upper edges, and center frequencies in the Mel scale
    lower_edges_mel = frequencies_mel[:-2]
    upper_edges_mel = frequencies_mel[2:]
    center_frequencies_mel = frequencies_mel[1:-1]

    return center_frequencies_mel, lower_edges_mel, upper_edges_mel


def compute_melmat(
    num_mel_bands=12,
    freq_min=64,
    freq_max=8000,
    num_fft_bands=513,
    sample_rate=16000,
):
    """
    Returns the Mel filterbank matrix for transforming an FFT spectrum into a Mel spectrum.

    Parameters
    ----------
    num_mel_bands : int, optional
        Number of Mel bands. Number of rows in the Mel filterbank matrix. Default is 12.
    freq_min : float, optional
        Minimum frequency for the first band. Default is 64.
    freq_max : float, optional
        Maximum frequency for the last band. Default is 8000.
    num_fft_bands : int, optional
        Number of FFT frequency bands. This is NFFT/2+1, and determines the number of columns in the Mel filterbank matrix.
        Default is 513 (corresponds to NFFT=1024).
    sample_rate : float, optional
        Sample rate for the signals that will be used. Default is 16000.

    Returns
    -------
    melmat : ndarray
        Transformation matrix for the Mel spectrum. Use this with FFT spectra of num_fft_bands length
        and multiply the spectrum with the Mel filterbank matrix to transform the FFT spectrum
        into a Mel spectrum.
    frequencies : tuple (ndarray <num_mel_bands>, ndarray <num_fft_bands>)
        Center frequencies of the Mel bands, center frequencies of the FFT spectrum.
    """

    # Compute center frequencies and edges for Mel filterbank
    (
        center_frequencies_mel,
        lower_edges_mel,
        upper_edges_mel,
    ) = melfrequencies_mel_filterbank(
        num_mel_bands, freq_min, freq_max, num_fft_bands
    )

    # Convert Mel frequencies to Hz
    center_frequencies_hz = mel_to_hertz(center_frequencies_mel)
    lower_edges_hz = mel_to_hertz(lower_edges_mel)
    upper_edges_hz = mel_to_hertz(upper_edges_mel)

    # Compute the array of FFT frequency bins
    freqs = np.linspace(0.0, sample_rate / 2.0, num_fft_bands)

    # Initialize the Mel filterbank matrix with zeros
    melmat = np.zeros((num_mel_bands, num_fft_bands))

    # Iterate through each Mel band and compute the corresponding filter coefficients
    for imelband, (center, lower, upper) in enumerate(
        zip(center_frequencies_hz, lower_edges_hz, upper_edges_hz)
    ):
        # Compute the left slope of the triangular filter for this Mel band
        left_slope = (freqs >= lower) & (freqs <= center)
        melmat[imelband, left_slope] = (freqs[left_slope] - lower) / (
            center - lower
        )

        # Compute the right slope of the triangular filter for this Mel band
        right_slope = (freqs >= center) & (freqs <= upper)
        melmat[imelband, right_slope] = (upper - freqs[right_slope]) / (
            upper - center
        )

    return (melmat, center_frequencies_hz, freqs)


def compute_melmat_from_range(
    lower_edges_hz, upper_edges_hz, num_fft_bands=513, sample_rate=16000
):
    """
    Computes the Mel filterbank matrix given the lower and upper edge frequencies for each band.

    Args:
        lower_edges_hz (array-like): Lower edge frequencies for each Mel band.
        upper_edges_hz (array-like): Upper edge frequencies for each Mel band.
        num_fft_bands (int, optional): Number of FFT frequency bands. Default is 513.
        sample_rate (int, optional): Audio sample rate in Hz. Default is 16000.

    Returns:
        tuple: A tuple containing the Mel filterbank matrix, center frequencies, and FFT frequencies.
    """

    # Initialize the Mel filterbank matrix with zeros
    melmat = np.zeros((len(lower_edges_hz), num_fft_bands))

    # Compute the array of FFT frequency bins
    freqs = np.linspace(0.0, sample_rate / 2.0, num_fft_bands)

    # Compute the center frequencies for each Mel band
    center_frequencies_hz = np.mean([lower_edges_hz, upper_edges_hz], axis=0)

    # Iterate through each Mel band and compute the corresponding filter coefficients
    for imelband, (lower, center, upper) in enumerate(
        zip(lower_edges_hz, center_frequencies_hz, upper_edges_hz)
    ):
        # Compute the left slope of the triangular filter for this Mel band
        left_slope = (freqs >= lower) & (freqs <= center)
        melmat[imelband, left_slope] = (freqs[left_slope] - lower) / (
            center - lower
        )

        # Compute the right slope of the triangular filter for this Mel band
        right_slope = (freqs >= center) & (freqs <= upper)
        melmat[imelband, right_slope] = (upper - freqs[right_slope]) / (
            upper - center
        )

    return (melmat, center_frequencies_hz, freqs)
