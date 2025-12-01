"""
Pytest fixtures for Multi-FFT testing suite.

Provides fixtures for:
- Test signal generation
- Audio analysis source setup
- Ground truth loading
- Metrics collection
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from .ground_truth_schema import SignalDefinition
from .signal_generator import (
    DEFAULT_SAMPLE_RATE,
    generate_chromatic_scale,
    generate_click_track,
    generate_complex_signal,
    generate_onset_signal,
)


@pytest.fixture
def sample_rate():
    """Default sample rate for tests."""
    return DEFAULT_SAMPLE_RATE


@pytest.fixture
def temp_signal_dir():
    """Temporary directory for test signals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def click_track_120bpm(sample_rate):
    """Generate a 120 BPM click track for testing."""
    audio, signal_def = generate_click_track(
        bpm=120,
        duration=10.0,
        sample_rate=sample_rate,
    )
    return audio, signal_def


@pytest.fixture
def click_track_60bpm(sample_rate):
    """Generate a slow 60 BPM click track."""
    audio, signal_def = generate_click_track(
        bpm=60,
        duration=15.0,
        sample_rate=sample_rate,
    )
    return audio, signal_def


@pytest.fixture
def click_track_180bpm(sample_rate):
    """Generate a fast 180 BPM click track."""
    audio, signal_def = generate_click_track(
        bpm=180,
        duration=10.0,
        sample_rate=sample_rate,
    )
    return audio, signal_def


@pytest.fixture
def onset_impulse(sample_rate):
    """Generate impulse onset test signal."""
    return generate_onset_signal(
        attack_type="impulse",
        interval_ms=500.0,
        duration=5.0,
        sample_rate=sample_rate,
    )


@pytest.fixture
def onset_sharp(sample_rate):
    """Generate sharp attack onset test signal."""
    return generate_onset_signal(
        attack_type="sharp",
        interval_ms=500.0,
        duration=5.0,
        sample_rate=sample_rate,
    )


@pytest.fixture
def onset_medium(sample_rate):
    """Generate medium attack onset test signal."""
    return generate_onset_signal(
        attack_type="medium",
        interval_ms=500.0,
        duration=5.0,
        sample_rate=sample_rate,
    )


@pytest.fixture
def onset_slow(sample_rate):
    """Generate slow attack onset test signal."""
    return generate_onset_signal(
        attack_type="slow",
        interval_ms=500.0,
        duration=5.0,
        sample_rate=sample_rate,
    )


@pytest.fixture
def chromatic_scale_sine(sample_rate):
    """Generate chromatic scale with sine waves."""
    return generate_chromatic_scale(
        start_midi=48,  # C3
        end_midi=60,  # C4
        note_duration=0.5,
        sample_rate=sample_rate,
        waveform="sine",
    )


@pytest.fixture
def chromatic_scale_triangle(sample_rate):
    """Generate chromatic scale with triangle waves."""
    return generate_chromatic_scale(
        start_midi=48,
        end_midi=60,
        note_duration=0.5,
        sample_rate=sample_rate,
        waveform="triangle",
    )


@pytest.fixture
def complex_signal_clean(sample_rate):
    """Generate complex signal with high SNR (clean)."""
    return generate_complex_signal(
        bpm=120,
        duration=15.0,
        sample_rate=sample_rate,
        snr_db=30.0,
    )


@pytest.fixture
def complex_signal_noisy(sample_rate):
    """Generate complex signal with low SNR (noisy)."""
    return generate_complex_signal(
        bpm=120,
        duration=15.0,
        sample_rate=sample_rate,
        snr_db=10.0,
    )


@pytest.fixture
def standard_tempos():
    """List of standard test tempos."""
    return [60, 80, 100, 120, 140, 160, 180]


@pytest.fixture
def standard_attack_types():
    """List of standard onset attack types."""
    return ["impulse", "sharp", "medium", "slow"]


@pytest.fixture
def fft_presets():
    """FFT preset configurations."""
    return {
        "balanced": {
            "onset": (1024, 256),
            "tempo": (2048, 367),
            "pitch": (4096, 367),
        },
        "low_latency": {
            "onset": (512, 128),
            "tempo": (1024, 183),
            "pitch": (2048, 183),
        },
        "high_precision": {
            "onset": (2048, 512),
            "tempo": (4096, 734),
            "pitch": (8192, 734),
        },
    }


class SignalPlayer:
    """
    Utility class for streaming audio samples to analysis components.

    Simulates real-time audio input by providing samples in frame-sized chunks.
    """

    def __init__(
        self,
        audio: np.ndarray,
        signal_def: SignalDefinition,
        hop_size: int = 367,
    ):
        self.audio = audio
        self.signal_def = signal_def
        self.hop_size = hop_size
        self.sample_rate = signal_def.metadata.sample_rate
        self.position = 0

    def get_next_frame(self) -> np.ndarray | None:
        """
        Get the next frame of audio samples.

        Returns:
            Audio samples for the next frame, or None if exhausted.
        """
        if self.position >= len(self.audio):
            return None

        end = min(self.position + self.hop_size, len(self.audio))
        frame = self.audio[self.position : end]
        self.position = end

        # Pad if necessary
        if len(frame) < self.hop_size:
            frame = np.pad(frame, (0, self.hop_size - len(frame)))

        return frame.astype(np.float32)

    def reset(self):
        """Reset playback position to start."""
        self.position = 0

    def get_current_time(self) -> float:
        """Get current playback time in seconds."""
        return self.position / self.sample_rate

    def is_exhausted(self) -> bool:
        """Check if all samples have been played."""
        return self.position >= len(self.audio)


@pytest.fixture
def signal_player_factory():
    """Factory fixture to create SignalPlayer instances."""

    def _create_player(audio, signal_def, hop_size=367):
        return SignalPlayer(audio, signal_def, hop_size)

    return _create_player
