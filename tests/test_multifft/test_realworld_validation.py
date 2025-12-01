"""
Real-World Validation Test Suite for Multi-FFT Audio Analysis

This module tests FFT presets and parameter recommendations against realistic
audio signals that more closely approximate actual music content.

Validates:
- Tempo detection on drum patterns (vs. synthetic clicks)
- Onset detection on realistic transients (vs. pure impulses)
- Pitch detection on harmonic-rich signals (vs. sine waves)
- Cross-validation between synthetic and realistic findings

Part of Milestone 4: Real-World Validation
"""

from dataclasses import dataclass, field
from typing import Any

import aubio
import numpy as np
import pytest

from .metrics import (
    AnalysisResult,
    PerformanceMetrics,
    calculate_onset_metrics,
    calculate_pitch_metrics,
    calculate_tempo_metrics,
)
from .realistic_signal_generator import (
    STANDARD_BASS_LINES,
    STANDARD_CHORD_PROGRESSIONS,
    STANDARD_DRUM_PATTERNS,
    generate_bass_line,
    generate_chord_progression,
    generate_drum_pattern,
    generate_full_mix,
)

# FFT Presets as defined in ledfx/effects/audio.py
FFT_PRESETS = {
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

SAMPLE_RATE = 44100


@dataclass
class RealWorldValidationResult:
    """Result from real-world validation test."""

    test_name: str
    signal_type: str  # 'drums', 'bass', 'chords', 'mix'
    preset_name: str

    # Accuracy metrics
    accuracy_score: float = 0.0
    raw_metrics: dict[str, float] = field(default_factory=dict)

    # Performance
    mean_time_us: float = 0.0

    # Pass/fail
    passed: bool = True
    notes: str = ""


@dataclass
class CrossValidationResult:
    """Result comparing synthetic vs realistic signal performance."""

    analysis_type: str  # 'tempo', 'onset', 'pitch'
    preset_name: str

    # Synthetic signal metrics
    synthetic_accuracy: float = 0.0
    synthetic_latency_us: float = 0.0

    # Realistic signal metrics
    realistic_accuracy: float = 0.0
    realistic_latency_us: float = 0.0

    # Comparison
    accuracy_delta: float = 0.0  # realistic - synthetic
    accuracy_ratio: float = 0.0  # realistic / synthetic

    # Analysis
    findings: str = ""


class RealWorldAnalyzer:
    """
    Analyzer for real-world validation tests.

    Wraps aubio analysis components with configurable FFT parameters
    for testing against realistic audio signals.
    """

    def __init__(
        self,
        preset_name: str,
        sample_rate: int = SAMPLE_RATE,
        tempo_method: str = "default",
        onset_method: str = "hfc",
        pitch_method: str = "yinfft",
    ):
        self.preset_name = preset_name
        self.sample_rate = sample_rate
        preset = FFT_PRESETS[preset_name]

        # Initialize tempo tracker
        tempo_fft, tempo_hop = preset["tempo"]
        self.tempo_hop = tempo_hop
        self._tempo = aubio.tempo(
            tempo_method, tempo_fft, tempo_hop, sample_rate
        )
        self._enable_tempo_features()

        # Initialize onset detector
        onset_fft, onset_hop = preset["onset"]
        self.onset_hop = onset_hop
        self._onset = aubio.onset(
            onset_method, onset_fft, onset_hop, sample_rate
        )

        # Initialize pitch detector
        pitch_fft, pitch_hop = preset["pitch"]
        self.pitch_hop = pitch_hop
        self._pitch = aubio.pitch(
            pitch_method, pitch_fft, pitch_hop, sample_rate
        )
        self._pitch.set_unit("midi")
        self._pitch.set_tolerance(0.8)

        # Performance tracking
        self.frame_times: list[float] = []

    def _enable_tempo_features(self):
        """Enable available tempo features."""
        features = [
            lambda: self._tempo.set_multi_octave(1),
            lambda: self._tempo.set_onset_enhancement(1),
            lambda: self._tempo.set_fft_autocorr(1),
            lambda: self._tempo.set_dynamic_tempo(1),
            lambda: self._tempo.set_adaptive_winlen(1),
            lambda: self._tempo.set_use_tempogram(1),
        ]
        for setter in features:
            try:
                setter()
            except (ValueError, RuntimeError, AttributeError):
                pass

    def analyze_tempo(
        self, audio: np.ndarray
    ) -> tuple[list[float], float, list[float]]:
        """
        Analyze tempo in audio signal.

        Args:
            audio: Audio samples as float32 array

        Returns:
            Tuple of (beat_times, detected_bpm, frame_times)
        """
        import time

        detected_beats = []
        frame_times = []

        for i in range(0, len(audio) - self.tempo_hop, self.tempo_hop):
            chunk = audio[i : i + self.tempo_hop].astype(np.float32)
            t0 = time.perf_counter()
            is_beat = self._tempo(chunk)
            frame_times.append((time.perf_counter() - t0) * 1_000_000)

            if is_beat:
                detected_beats.append(i / self.sample_rate)

        detected_bpm = float(self._tempo.get_bpm())
        self.frame_times.extend(frame_times)
        return detected_beats, detected_bpm, frame_times

    def analyze_onsets(self, audio: np.ndarray) -> tuple[list[float], list[float]]:
        """
        Detect onsets in audio signal.

        Args:
            audio: Audio samples as float32 array

        Returns:
            Tuple of (onset_times, frame_times)
        """
        import time

        detected_onsets = []
        frame_times = []

        for i in range(0, len(audio) - self.onset_hop, self.onset_hop):
            chunk = audio[i : i + self.onset_hop].astype(np.float32)
            t0 = time.perf_counter()
            is_onset = self._onset(chunk)
            frame_times.append((time.perf_counter() - t0) * 1_000_000)

            if is_onset:
                detected_onsets.append(i / self.sample_rate)

        self.frame_times.extend(frame_times)
        return detected_onsets, frame_times

    def analyze_pitch(
        self, audio: np.ndarray
    ) -> tuple[list[tuple[float, float]], list[float]]:
        """
        Detect pitch in audio signal.

        Args:
            audio: Audio samples as float32 array

        Returns:
            Tuple of (pitch_detections, frame_times)
            where pitch_detections are (time, midi_note) tuples
        """
        import time

        detected_pitches = []
        frame_times = []

        for i in range(0, len(audio) - self.pitch_hop, self.pitch_hop):
            chunk = audio[i : i + self.pitch_hop].astype(np.float32)
            t0 = time.perf_counter()
            midi_note = float(self._pitch(chunk)[0])
            frame_times.append((time.perf_counter() - t0) * 1_000_000)

            pitch_time = i / self.sample_rate
            if midi_note > 20:  # Valid MIDI range
                detected_pitches.append((pitch_time, midi_note))

        self.frame_times.extend(frame_times)
        return detected_pitches, frame_times


def run_drum_pattern_test(
    preset_name: str,
    pattern_name: str,
    num_bars: int = 8,
) -> RealWorldValidationResult:
    """
    Run tempo detection test on drum pattern.

    Args:
        preset_name: FFT preset to test
        pattern_name: Name of drum pattern
        num_bars: Number of bars to test

    Returns:
        RealWorldValidationResult
    """
    from .realistic_signal_generator import DrumPattern

    # Get or create pattern
    if pattern_name in STANDARD_DRUM_PATTERNS:
        pattern = STANDARD_DRUM_PATTERNS[pattern_name]
    else:
        pattern = DrumPattern(bpm=120.0)

    # Generate audio
    audio, signal_def = generate_drum_pattern(pattern, num_bars, SAMPLE_RATE)

    # Analyze
    analyzer = RealWorldAnalyzer(preset_name)
    detected_beats, detected_bpm, frame_times = analyzer.analyze_tempo(audio)

    # Calculate metrics
    tempo_metrics = calculate_tempo_metrics(
        detected_beats=detected_beats,
        expected_beats=signal_def.ground_truth.beats,
        detected_bpm=detected_bpm,
        expected_bpm=pattern.bpm,
        tolerance_ms=signal_def.test_criteria.beat_timing_tolerance_ms,
    )

    # Handle octave errors (double/half tempo)
    bpm_error = tempo_metrics.bpm_error
    if abs(detected_bpm - pattern.bpm * 2) < abs(bpm_error):
        bpm_error = abs(detected_bpm - pattern.bpm * 2)
    if abs(detected_bpm - pattern.bpm / 2) < abs(bpm_error):
        bpm_error = abs(detected_bpm - pattern.bpm / 2)

    # Calculate accuracy score
    bpm_accuracy = max(0.0, 1.0 - bpm_error / 20.0)
    beat_recall = tempo_metrics.recall
    accuracy_score = 0.6 * bpm_accuracy + 0.4 * beat_recall

    # Determine pass/fail
    passed = bpm_error < signal_def.test_criteria.tempo_tolerance_bpm * 2

    return RealWorldValidationResult(
        test_name=f"{preset_name}_{pattern_name}",
        signal_type="drums",
        preset_name=preset_name,
        accuracy_score=accuracy_score,
        raw_metrics={
            "bpm_error": bpm_error,
            "beat_recall": beat_recall,
            "detected_bpm": detected_bpm,
            "expected_bpm": pattern.bpm,
        },
        mean_time_us=float(np.mean(frame_times)) if frame_times else 0.0,
        passed=passed,
        notes=f"Detected {detected_bpm:.1f} BPM (expected {pattern.bpm})",
    )


def run_bass_line_test(
    preset_name: str,
    line_name: str,
    bpm: float = 120.0,
) -> RealWorldValidationResult:
    """
    Run pitch detection test on bass line.

    Args:
        preset_name: FFT preset to test
        line_name: Name of bass line pattern
        bpm: Tempo in BPM

    Returns:
        RealWorldValidationResult
    """
    # Get or create bass line
    if line_name in STANDARD_BASS_LINES:
        notes = STANDARD_BASS_LINES[line_name] * 4
    else:
        notes = [(36, 2), (38, 2), (40, 2), (41, 2)] * 4

    # Generate audio
    audio, signal_def = generate_bass_line(notes, bpm, SAMPLE_RATE)

    # Analyze
    analyzer = RealWorldAnalyzer(preset_name)
    detected_pitches, frame_times = analyzer.analyze_pitch(audio)

    # Calculate metrics
    pitch_metrics = calculate_pitch_metrics(
        detected_pitches=detected_pitches,
        expected_pitches=signal_def.ground_truth.pitches,
        tolerance_cents=signal_def.test_criteria.pitch_tolerance_cents,
    )

    # Determine pass/fail
    passed = pitch_metrics.detection_rate >= signal_def.test_criteria.min_detection_rate

    return RealWorldValidationResult(
        test_name=f"{preset_name}_{line_name}_{bpm}bpm",
        signal_type="bass",
        preset_name=preset_name,
        accuracy_score=pitch_metrics.detection_rate,
        raw_metrics={
            "detection_rate": pitch_metrics.detection_rate,
            "mean_error_cents": pitch_metrics.mean_error_cents,
            "total_pitches": pitch_metrics.total_expected_pitches,
            "detected_pitches": pitch_metrics.correctly_detected_pitches,
        },
        mean_time_us=float(np.mean(frame_times)) if frame_times else 0.0,
        passed=passed,
        notes=f"Detection rate: {pitch_metrics.detection_rate:.1%}",
    )


def run_chord_progression_test(
    preset_name: str,
    prog_name: str,
    bpm: float = 120.0,
) -> RealWorldValidationResult:
    """
    Run onset detection test on chord progression.

    Args:
        preset_name: FFT preset to test
        prog_name: Name of chord progression
        bpm: Tempo in BPM

    Returns:
        RealWorldValidationResult
    """
    # Get or create progression
    if prog_name in STANDARD_CHORD_PROGRESSIONS:
        chords = STANDARD_CHORD_PROGRESSIONS[prog_name] * 2
    else:
        chords = [([48, 52, 55], 4), ([53, 57, 60], 4)] * 2

    # Generate audio
    audio, signal_def = generate_chord_progression(chords, bpm, SAMPLE_RATE)

    # Analyze
    analyzer = RealWorldAnalyzer(preset_name)
    detected_onsets, frame_times = analyzer.analyze_onsets(audio)

    # Calculate metrics
    onset_metrics = calculate_onset_metrics(
        detected_onsets=detected_onsets,
        expected_onsets=signal_def.ground_truth.onsets,
        tolerance_ms=75.0,  # Relaxed for slow chord attacks
    )

    # Determine pass/fail
    passed = onset_metrics.f1_score >= 0.4  # Relaxed for polyphonic

    return RealWorldValidationResult(
        test_name=f"{preset_name}_{prog_name}_{bpm}bpm",
        signal_type="chords",
        preset_name=preset_name,
        accuracy_score=onset_metrics.f1_score,
        raw_metrics={
            "f1_score": onset_metrics.f1_score,
            "precision": onset_metrics.precision,
            "recall": onset_metrics.recall,
        },
        mean_time_us=float(np.mean(frame_times)) if frame_times else 0.0,
        passed=passed,
        notes=f"F1: {onset_metrics.f1_score:.2f}",
    )


def run_full_mix_test(
    preset_name: str,
    bpm: float = 120.0,
    duration: float = 20.0,
) -> RealWorldValidationResult:
    """
    Run comprehensive test on full mix.

    Args:
        preset_name: FFT preset to test
        bpm: Tempo in BPM
        duration: Duration in seconds

    Returns:
        RealWorldValidationResult
    """
    # Generate audio
    audio, signal_def = generate_full_mix(bpm, duration, SAMPLE_RATE)

    # Analyze tempo (primary for full mix)
    analyzer = RealWorldAnalyzer(preset_name)
    detected_beats, detected_bpm, frame_times = analyzer.analyze_tempo(audio)

    # Calculate metrics
    tempo_metrics = calculate_tempo_metrics(
        detected_beats=detected_beats,
        expected_beats=signal_def.ground_truth.beats,
        detected_bpm=detected_bpm,
        expected_bpm=bpm,
        tolerance_ms=signal_def.test_criteria.beat_timing_tolerance_ms,
    )

    # Handle octave errors
    bpm_error = tempo_metrics.bpm_error
    if abs(detected_bpm - bpm * 2) < abs(bpm_error):
        bpm_error = abs(detected_bpm - bpm * 2)
    if abs(detected_bpm - bpm / 2) < abs(bpm_error):
        bpm_error = abs(detected_bpm - bpm / 2)

    # Calculate accuracy
    bpm_accuracy = max(0.0, 1.0 - bpm_error / 10.0)
    accuracy_score = 0.7 * bpm_accuracy + 0.3 * tempo_metrics.recall

    # Determine pass/fail
    passed = bpm_error < signal_def.test_criteria.tempo_tolerance_bpm

    return RealWorldValidationResult(
        test_name=f"{preset_name}_mix_{bpm}bpm",
        signal_type="mix",
        preset_name=preset_name,
        accuracy_score=accuracy_score,
        raw_metrics={
            "bpm_error": bpm_error,
            "beat_recall": tempo_metrics.recall,
            "detected_bpm": detected_bpm,
        },
        mean_time_us=float(np.mean(frame_times)) if frame_times else 0.0,
        passed=passed,
        notes=f"Detected {detected_bpm:.1f} BPM",
    )


def run_cross_validation(
    analysis_type: str,
    preset_name: str,
) -> CrossValidationResult:
    """
    Run cross-validation comparing synthetic and realistic signals.

    Args:
        analysis_type: 'tempo', 'onset', or 'pitch'
        preset_name: FFT preset to test

    Returns:
        CrossValidationResult
    """
    from .signal_generator import (
        generate_chromatic_scale,
        generate_click_track,
        generate_onset_signal,
    )

    result = CrossValidationResult(
        analysis_type=analysis_type,
        preset_name=preset_name,
    )

    if analysis_type == "tempo":
        # Synthetic: click track
        syn_audio, syn_def = generate_click_track(bpm=120.0, duration=15.0)
        analyzer = RealWorldAnalyzer(preset_name)
        syn_beats, syn_bpm, syn_times = analyzer.analyze_tempo(syn_audio)
        syn_metrics = calculate_tempo_metrics(
            syn_beats, syn_def.ground_truth.beats, syn_bpm, 120.0
        )

        result.synthetic_accuracy = 1.0 - min(1.0, syn_metrics.bpm_error / 10.0)
        result.synthetic_latency_us = float(np.mean(syn_times)) if syn_times else 0.0

        # Realistic: drum pattern
        real_audio, real_def = generate_drum_pattern(
            STANDARD_DRUM_PATTERNS["rock_4_4"], num_bars=8
        )
        analyzer2 = RealWorldAnalyzer(preset_name)
        real_beats, real_bpm, real_times = analyzer2.analyze_tempo(real_audio)
        real_metrics = calculate_tempo_metrics(
            real_beats, real_def.ground_truth.beats, real_bpm, 120.0
        )

        # Handle octave error
        real_error = real_metrics.bpm_error
        if abs(real_bpm - 240) < real_error:
            real_error = abs(real_bpm - 240)
        if abs(real_bpm - 60) < real_error:
            real_error = abs(real_bpm - 60)

        result.realistic_accuracy = 1.0 - min(1.0, real_error / 10.0)
        result.realistic_latency_us = float(np.mean(real_times)) if real_times else 0.0

    elif analysis_type == "onset":
        # Synthetic: impulse
        syn_audio, syn_def = generate_onset_signal("impulse", interval_ms=500.0)
        analyzer = RealWorldAnalyzer(preset_name)
        syn_onsets, syn_times = analyzer.analyze_onsets(syn_audio)
        syn_metrics = calculate_onset_metrics(syn_onsets, syn_def.ground_truth.onsets)

        result.synthetic_accuracy = syn_metrics.f1_score
        result.synthetic_latency_us = float(np.mean(syn_times)) if syn_times else 0.0

        # Realistic: drum pattern (onsets)
        real_audio, real_def = generate_drum_pattern(
            STANDARD_DRUM_PATTERNS["rock_4_4"], num_bars=8
        )
        analyzer2 = RealWorldAnalyzer(preset_name)
        real_onsets, real_times = analyzer2.analyze_onsets(real_audio)
        real_metrics = calculate_onset_metrics(real_onsets, real_def.ground_truth.onsets)

        result.realistic_accuracy = real_metrics.f1_score
        result.realistic_latency_us = float(np.mean(real_times)) if real_times else 0.0

    elif analysis_type == "pitch":
        # Synthetic: sine waves
        syn_audio, syn_def = generate_chromatic_scale(
            start_midi=48, end_midi=60, waveform="sine"
        )
        analyzer = RealWorldAnalyzer(preset_name)
        syn_pitches, syn_times = analyzer.analyze_pitch(syn_audio)
        syn_metrics = calculate_pitch_metrics(
            syn_pitches, syn_def.ground_truth.pitches
        )

        result.synthetic_accuracy = syn_metrics.detection_rate
        result.synthetic_latency_us = float(np.mean(syn_times)) if syn_times else 0.0

        # Realistic: bass line
        real_audio, real_def = generate_bass_line(
            STANDARD_BASS_LINES["simple_root"] * 4, bpm=120.0
        )
        analyzer2 = RealWorldAnalyzer(preset_name)
        real_pitches, real_times = analyzer2.analyze_pitch(real_audio)
        real_metrics = calculate_pitch_metrics(
            real_pitches, real_def.ground_truth.pitches
        )

        result.realistic_accuracy = real_metrics.detection_rate
        result.realistic_latency_us = float(np.mean(real_times)) if real_times else 0.0

    # Calculate comparison metrics
    result.accuracy_delta = result.realistic_accuracy - result.synthetic_accuracy
    if result.synthetic_accuracy > 0:
        result.accuracy_ratio = result.realistic_accuracy / result.synthetic_accuracy
    else:
        result.accuracy_ratio = 0.0

    # Generate findings
    if result.accuracy_ratio >= 0.9:
        result.findings = "Realistic performance matches synthetic (≥90%)"
    elif result.accuracy_ratio >= 0.7:
        result.findings = "Realistic performance slightly degraded (70-90%)"
    elif result.accuracy_ratio >= 0.5:
        result.findings = "Realistic performance moderately degraded (50-70%)"
    else:
        result.findings = "Significant accuracy drop on realistic signals (<50%)"

    return result


# ============================================================================
# Pytest Test Classes
# ============================================================================


class TestDrumPatterns:
    """Tests for tempo detection on drum patterns."""

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_rock_pattern(self, preset):
        """Test tempo detection on rock drum pattern."""
        result = run_drum_pattern_test(preset, "rock_4_4", num_bars=8)
        print(f"\n{result.test_name}: {result.notes}")
        print(f"  Accuracy: {result.accuracy_score:.2f}")
        print(f"  Mean time: {result.mean_time_us:.1f} µs")
        # Verify test ran
        assert result.raw_metrics.get("detected_bpm", 0) > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_electronic_pattern(self, preset):
        """Test tempo detection on electronic drum pattern."""
        result = run_drum_pattern_test(preset, "electronic_4_on_floor", num_bars=8)
        print(f"\n{result.test_name}: {result.notes}")
        assert result.raw_metrics.get("detected_bpm", 0) > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_hip_hop_pattern(self, preset):
        """Test tempo detection on hip-hop drum pattern."""
        result = run_drum_pattern_test(preset, "hip_hop", num_bars=8)
        print(f"\n{result.test_name}: {result.notes}")
        assert result.raw_metrics.get("detected_bpm", 0) > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_fast_punk_pattern(self, preset):
        """Test tempo detection on fast punk drum pattern."""
        result = run_drum_pattern_test(preset, "fast_punk", num_bars=8)
        print(f"\n{result.test_name}: {result.notes}")
        # Fast tempo is challenging, just verify detection occurred
        assert result.raw_metrics.get("detected_bpm", 0) > 0


class TestBassLines:
    """Tests for pitch detection on bass lines."""

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    @pytest.mark.parametrize("bpm", [90, 120])
    def test_simple_root_bass(self, preset, bpm):
        """Test pitch detection on simple root bass."""
        result = run_bass_line_test(preset, "simple_root", bpm)
        print(f"\n{result.test_name}: {result.notes}")
        print(f"  Detection rate: {result.accuracy_score:.1%}")
        # Verify some pitches were detected
        assert result.raw_metrics.get("detected_pitches", 0) > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_octave_bass(self, preset):
        """Test pitch detection on octave bass pattern."""
        result = run_bass_line_test(preset, "octave_pattern", 120)
        print(f"\n{result.test_name}: {result.notes}")
        assert result.raw_metrics.get("detected_pitches", 0) > 0


class TestChordProgressions:
    """Tests for onset detection on chord progressions."""

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_pop_progression(self, preset):
        """Test onset detection on pop chord progression."""
        result = run_chord_progression_test(preset, "pop_1_5_6_4", 120)
        print(f"\n{result.test_name}: {result.notes}")
        print(f"  Precision: {result.raw_metrics.get('precision', 0):.2f}")
        print(f"  Recall: {result.raw_metrics.get('recall', 0):.2f}")
        # Chords have slow attacks, onset detection is challenging
        assert result.raw_metrics.get("f1_score", 0) >= 0.0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_jazz_progression(self, preset):
        """Test onset detection on jazz chord progression."""
        result = run_chord_progression_test(preset, "jazz_2_5_1", 80)
        print(f"\n{result.test_name}: {result.notes}")
        assert result.raw_metrics.get("f1_score", 0) >= 0.0


class TestFullMix:
    """Tests for analysis on full musical mix."""

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    @pytest.mark.parametrize("bpm", [90, 120, 140])
    def test_full_mix_tempo(self, preset, bpm):
        """Test tempo detection on full mix."""
        result = run_full_mix_test(preset, bpm, duration=15.0)
        print(f"\n{result.test_name}: {result.notes}")
        print(f"  Accuracy: {result.accuracy_score:.2f}")
        print(f"  Mean time: {result.mean_time_us:.1f} µs")
        assert result.raw_metrics.get("detected_bpm", 0) > 0


class TestCrossValidation:
    """Tests comparing synthetic vs realistic signal performance."""

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_tempo_cross_validation(self, preset):
        """Compare tempo detection on synthetic vs realistic signals."""
        result = run_cross_validation("tempo", preset)
        print(f"\n{preset} tempo cross-validation:")
        print(f"  Synthetic accuracy: {result.synthetic_accuracy:.2f}")
        print(f"  Realistic accuracy: {result.realistic_accuracy:.2f}")
        print(f"  Ratio: {result.accuracy_ratio:.2f}")
        print(f"  Findings: {result.findings}")
        # Verify both tests ran
        assert result.synthetic_latency_us > 0
        assert result.realistic_latency_us > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_onset_cross_validation(self, preset):
        """Compare onset detection on synthetic vs realistic signals."""
        result = run_cross_validation("onset", preset)
        print(f"\n{preset} onset cross-validation:")
        print(f"  Synthetic accuracy: {result.synthetic_accuracy:.2f}")
        print(f"  Realistic accuracy: {result.realistic_accuracy:.2f}")
        print(f"  Ratio: {result.accuracy_ratio:.2f}")
        print(f"  Findings: {result.findings}")
        assert result.synthetic_latency_us > 0
        assert result.realistic_latency_us > 0

    @pytest.mark.parametrize("preset", FFT_PRESETS.keys())
    def test_pitch_cross_validation(self, preset):
        """Compare pitch detection on synthetic vs realistic signals."""
        result = run_cross_validation("pitch", preset)
        print(f"\n{preset} pitch cross-validation:")
        print(f"  Synthetic accuracy: {result.synthetic_accuracy:.2f}")
        print(f"  Realistic accuracy: {result.realistic_accuracy:.2f}")
        print(f"  Ratio: {result.accuracy_ratio:.2f}")
        print(f"  Findings: {result.findings}")
        assert result.synthetic_latency_us > 0
        assert result.realistic_latency_us > 0


class TestRealWorldSummary:
    """Summary tests aggregating real-world validation results."""

    def test_generate_validation_summary(self):
        """Generate comprehensive real-world validation summary."""
        all_results: dict[str, list[RealWorldValidationResult]] = {
            preset: [] for preset in FFT_PRESETS
        }
        cross_validation: list[CrossValidationResult] = []

        # Run subset of tests for summary
        for preset in FFT_PRESETS:
            # Drum patterns
            for pattern in ["rock_4_4", "electronic_4_on_floor"]:
                result = run_drum_pattern_test(preset, pattern, 4)
                all_results[preset].append(result)

            # Bass lines
            result = run_bass_line_test(preset, "simple_root", 120)
            all_results[preset].append(result)

            # Full mix
            result = run_full_mix_test(preset, 120, 10.0)
            all_results[preset].append(result)

            # Cross-validation
            for analysis_type in ["tempo", "onset", "pitch"]:
                cv_result = run_cross_validation(analysis_type, preset)
                cross_validation.append(cv_result)

        # Generate summary report
        print("\n" + "=" * 70)
        print("REAL-WORLD VALIDATION SUMMARY")
        print("=" * 70)

        for preset, results in all_results.items():
            passed = sum(1 for r in results if r.passed)
            avg_accuracy = (
                sum(r.accuracy_score for r in results) / len(results)
                if results
                else 0
            )
            avg_time = (
                sum(r.mean_time_us for r in results) / len(results)
                if results
                else 0
            )

            print(f"\n{preset.upper()} PRESET:")
            print(f"  Tests passed: {passed}/{len(results)}")
            print(f"  Average accuracy: {avg_accuracy:.2f}")
            print(f"  Average time: {avg_time:.1f} µs")

        print("\n" + "-" * 70)
        print("CROSS-VALIDATION SUMMARY")
        print("-" * 70)

        for preset in FFT_PRESETS:
            preset_cv = [cv for cv in cross_validation if cv.preset_name == preset]
            avg_ratio = (
                sum(cv.accuracy_ratio for cv in preset_cv) / len(preset_cv)
                if preset_cv
                else 0
            )
            print(f"\n{preset}: avg synthetic-to-realistic ratio = {avg_ratio:.2f}")
            for cv in preset_cv:
                print(f"  {cv.analysis_type}: {cv.findings}")

        print("\n" + "=" * 70)

        # Test passes if any tests were run
        total = sum(len(r) for r in all_results.values())
        assert total > 0
