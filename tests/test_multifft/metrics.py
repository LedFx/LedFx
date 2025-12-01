"""
Metrics Collection for Multi-FFT Testing

This module provides utilities for calculating and collecting accuracy
and performance metrics from audio analysis tests.

Metrics Categories:
- Accuracy: tempo error, beat F1, onset precision/recall, pitch accuracy
- Latency: frame processing time, FFT computation time
- Computational: CPU usage, memory, deduplication savings
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .ground_truth_schema import (
    BeatAnnotation,
    OnsetAnnotation,
    PitchAnnotation,
    TestCriteria,
)


@dataclass
class TempoMetrics:
    """Metrics for tempo/beat tracking accuracy."""

    # BPM accuracy
    detected_bpm: float = 0.0
    expected_bpm: float = 0.0
    bpm_error: float = 0.0
    bpm_error_percent: float = 0.0

    # Beat detection
    total_expected_beats: int = 0
    correctly_detected_beats: int = 0
    missed_beats: int = 0
    false_positive_beats: int = 0

    # F1 metrics
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    # Timing
    mean_timing_error_ms: float = 0.0
    std_timing_error_ms: float = 0.0

    # Lock performance
    time_to_lock_seconds: float = 0.0
    lock_achieved: bool = False


@dataclass
class OnsetMetrics:
    """Metrics for onset detection accuracy."""

    total_expected_onsets: int = 0
    correctly_detected_onsets: int = 0
    missed_onsets: int = 0
    false_positive_onsets: int = 0

    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    mean_timing_error_ms: float = 0.0
    std_timing_error_ms: float = 0.0


@dataclass
class PitchMetrics:
    """Metrics for pitch detection accuracy."""

    total_expected_pitches: int = 0
    correctly_detected_pitches: int = 0
    missed_pitches: int = 0
    octave_errors: int = 0

    # Error in cents (100 cents = 1 semitone)
    mean_error_cents: float = 0.0
    std_error_cents: float = 0.0
    max_error_cents: float = 0.0

    detection_rate: float = 0.0


@dataclass
class PerformanceMetrics:
    """Performance/latency metrics."""

    # Frame timing (microseconds)
    mean_frame_time_us: float = 0.0
    p95_frame_time_us: float = 0.0
    p99_frame_time_us: float = 0.0
    max_frame_time_us: float = 0.0

    # FFT timing per config (fft_size, hop_size) -> timing
    fft_timings: dict[tuple[int, int], float] = field(default_factory=dict)

    # Resource usage
    cpu_percent: float = 0.0
    memory_mb: float = 0.0

    # Efficiency
    fft_dedup_savings_percent: float = 0.0


@dataclass
class TestResult:
    """Complete result from a single test."""

    test_name: str
    signal_type: str
    passed: bool = True
    error_message: str = ""

    tempo_metrics: TempoMetrics | None = None
    onset_metrics: OnsetMetrics | None = None
    pitch_metrics: PitchMetrics | None = None
    performance_metrics: PerformanceMetrics | None = None


def calculate_tempo_metrics(
    detected_beats: list[float],
    expected_beats: list[BeatAnnotation],
    detected_bpm: float,
    expected_bpm: float,
    tolerance_ms: float = 50.0,
    time_to_lock: float = 0.0,
    lock_achieved: bool = False,
) -> TempoMetrics:
    """
    Calculate tempo/beat tracking metrics.

    Args:
        detected_beats: List of detected beat times in seconds
        expected_beats: List of expected beat annotations
        detected_bpm: Detected tempo in BPM
        expected_bpm: Expected/ground truth tempo in BPM
        tolerance_ms: Tolerance for beat matching in milliseconds
        time_to_lock: Time taken to achieve tempo lock
        lock_achieved: Whether tempo lock was achieved

    Returns:
        TempoMetrics with all calculated values
    """
    metrics = TempoMetrics(
        detected_bpm=detected_bpm,
        expected_bpm=expected_bpm,
        time_to_lock_seconds=time_to_lock,
        lock_achieved=lock_achieved,
    )

    # BPM error
    metrics.bpm_error = abs(detected_bpm - expected_bpm)
    if expected_bpm > 0:
        metrics.bpm_error_percent = (metrics.bpm_error / expected_bpm) * 100

    # Beat matching
    expected_times = [b.time for b in expected_beats]
    metrics.total_expected_beats = len(expected_times)

    tolerance_s = tolerance_ms / 1000.0
    matched_expected = set()
    matched_detected = set()
    timing_errors = []

    for i, detected_time in enumerate(detected_beats):
        best_match = None
        best_error = float("inf")

        for j, expected_time in enumerate(expected_times):
            if j in matched_expected:
                continue
            error = abs(detected_time - expected_time)
            if error < tolerance_s and error < best_error:
                best_match = j
                best_error = error

        if best_match is not None:
            matched_expected.add(best_match)
            matched_detected.add(i)
            timing_errors.append(best_error * 1000)  # Convert to ms

    metrics.correctly_detected_beats = len(matched_expected)
    metrics.missed_beats = metrics.total_expected_beats - len(matched_expected)
    metrics.false_positive_beats = len(detected_beats) - len(matched_detected)

    # Precision, Recall, F1
    if len(detected_beats) > 0:
        metrics.precision = len(matched_detected) / len(detected_beats)
    if metrics.total_expected_beats > 0:
        metrics.recall = len(matched_expected) / metrics.total_expected_beats
    if metrics.precision + metrics.recall > 0:
        metrics.f1_score = (
            2
            * metrics.precision
            * metrics.recall
            / (metrics.precision + metrics.recall)
        )

    # Timing error statistics
    if timing_errors:
        metrics.mean_timing_error_ms = float(np.mean(timing_errors))
        metrics.std_timing_error_ms = float(np.std(timing_errors))

    return metrics


def calculate_onset_metrics(
    detected_onsets: list[float],
    expected_onsets: list[OnsetAnnotation],
    tolerance_ms: float = 50.0,
) -> OnsetMetrics:
    """
    Calculate onset detection metrics.

    Args:
        detected_onsets: List of detected onset times in seconds
        expected_onsets: List of expected onset annotations
        tolerance_ms: Tolerance for onset matching in milliseconds

    Returns:
        OnsetMetrics with all calculated values
    """
    metrics = OnsetMetrics()
    metrics.total_expected_onsets = len(expected_onsets)

    tolerance_s = tolerance_ms / 1000.0
    expected_times = [o.time for o in expected_onsets]

    matched_expected = set()
    matched_detected = set()
    timing_errors = []

    for i, detected_time in enumerate(detected_onsets):
        best_match = None
        best_error = float("inf")

        for j, expected_time in enumerate(expected_times):
            if j in matched_expected:
                continue
            error = abs(detected_time - expected_time)
            if error < tolerance_s and error < best_error:
                best_match = j
                best_error = error

        if best_match is not None:
            matched_expected.add(best_match)
            matched_detected.add(i)
            timing_errors.append(best_error * 1000)

    metrics.correctly_detected_onsets = len(matched_expected)
    metrics.missed_onsets = metrics.total_expected_onsets - len(matched_expected)
    metrics.false_positive_onsets = len(detected_onsets) - len(matched_detected)

    if len(detected_onsets) > 0:
        metrics.precision = len(matched_detected) / len(detected_onsets)
    if metrics.total_expected_onsets > 0:
        metrics.recall = len(matched_expected) / metrics.total_expected_onsets
    if metrics.precision + metrics.recall > 0:
        metrics.f1_score = (
            2
            * metrics.precision
            * metrics.recall
            / (metrics.precision + metrics.recall)
        )

    if timing_errors:
        metrics.mean_timing_error_ms = float(np.mean(timing_errors))
        metrics.std_timing_error_ms = float(np.std(timing_errors))

    return metrics


def midi_difference_to_cents(midi_a: float, midi_b: float) -> float:
    """Calculate error in cents between two MIDI note values.

    Each semitone (MIDI step) equals 100 cents, so the difference
    in MIDI notes multiplied by 100 gives the error in cents.
    """
    return (midi_a - midi_b) * 100.0


def calculate_pitch_metrics(
    detected_pitches: list[tuple[float, float]],  # (time, midi_note)
    expected_pitches: list[PitchAnnotation],
    tolerance_cents: float = 50.0,
) -> PitchMetrics:
    """
    Calculate pitch detection metrics.

    Args:
        detected_pitches: List of (time, midi_note) tuples
        expected_pitches: List of expected pitch annotations
        tolerance_cents: Tolerance for pitch matching in cents

    Returns:
        PitchMetrics with all calculated values
    """
    metrics = PitchMetrics()
    metrics.total_expected_pitches = len(expected_pitches)

    if not expected_pitches or not detected_pitches:
        return metrics

    errors_cents = []
    correctly_detected = 0
    octave_errors = 0

    for expected in expected_pitches:
        # Find detections within this pitch's time range
        detections_in_range = [
            (t, m)
            for t, m in detected_pitches
            if expected.start_time <= t < expected.end_time
        ]

        if not detections_in_range:
            continue

        # Use median detected pitch in range
        detected_midis = [m for _, m in detections_in_range]
        median_midi = float(np.median(detected_midis))

        # Calculate error
        error_cents = midi_difference_to_cents(median_midi, expected.midi_note)
        abs_error = abs(error_cents)

        # Check for octave error (within 50 cents of ±1200 cents)
        if abs(abs_error - 1200) < 50 or abs(abs_error - 2400) < 50:
            octave_errors += 1

        if abs_error <= tolerance_cents:
            correctly_detected += 1

        errors_cents.append(error_cents)

    metrics.correctly_detected_pitches = correctly_detected
    metrics.missed_pitches = metrics.total_expected_pitches - correctly_detected
    metrics.octave_errors = octave_errors

    if metrics.total_expected_pitches > 0:
        metrics.detection_rate = correctly_detected / metrics.total_expected_pitches

    if errors_cents:
        metrics.mean_error_cents = float(np.mean(errors_cents))
        metrics.std_error_cents = float(np.std(errors_cents))
        metrics.max_error_cents = float(np.max(np.abs(errors_cents)))

    return metrics


def check_test_passed(
    test_result: TestResult,
    criteria: TestCriteria,
) -> bool:
    """
    Check if a test result passes the given criteria.

    Args:
        test_result: Test result to check
        criteria: Success criteria

    Returns:
        True if test passes all relevant criteria
    """
    passed = True
    reasons = []

    if test_result.tempo_metrics:
        tm = test_result.tempo_metrics
        if tm.bpm_error > criteria.tempo_tolerance_bpm:
            passed = False
            reasons.append(
                f"BPM error {tm.bpm_error:.1f} > tolerance {criteria.tempo_tolerance_bpm}"
            )
        if tm.recall < criteria.min_detection_rate:
            passed = False
            reasons.append(
                f"Beat recall {tm.recall:.2f} < min rate {criteria.min_detection_rate}"
            )

    if test_result.onset_metrics:
        om = test_result.onset_metrics
        if om.recall < criteria.min_detection_rate:
            passed = False
            reasons.append(
                f"Onset recall {om.recall:.2f} < min rate {criteria.min_detection_rate}"
            )

    if test_result.pitch_metrics:
        pm = test_result.pitch_metrics
        if pm.detection_rate < criteria.min_detection_rate:
            passed = False
            reasons.append(
                f"Pitch detection rate {pm.detection_rate:.2f} < min rate {criteria.min_detection_rate}"
            )

    test_result.passed = passed
    if not passed:
        test_result.error_message = "; ".join(reasons)

    return passed


def format_metrics_report(test_result: TestResult) -> str:
    """
    Format a test result as a human-readable report.

    Args:
        test_result: Test result to format

    Returns:
        Formatted string report
    """
    lines = [
        f"Test: {test_result.test_name}",
        f"Type: {test_result.signal_type}",
        f"Status: {'PASSED' if test_result.passed else 'FAILED'}",
    ]

    if test_result.error_message:
        lines.append(f"Errors: {test_result.error_message}")

    if test_result.tempo_metrics:
        tm = test_result.tempo_metrics
        lines.extend(
            [
                "",
                "Tempo Metrics:",
                f"  BPM: {tm.detected_bpm:.1f} (expected {tm.expected_bpm:.1f}, error {tm.bpm_error:.1f})",
                f"  Beats: {tm.correctly_detected_beats}/{tm.total_expected_beats} correct",
                f"  Precision: {tm.precision:.3f}, Recall: {tm.recall:.3f}, F1: {tm.f1_score:.3f}",
                f"  Timing error: {tm.mean_timing_error_ms:.1f}ms ± {tm.std_timing_error_ms:.1f}ms",
                f"  Lock: {'achieved in ' + f'{tm.time_to_lock_seconds:.2f}s' if tm.lock_achieved else 'not achieved'}",
            ]
        )

    if test_result.onset_metrics:
        om = test_result.onset_metrics
        lines.extend(
            [
                "",
                "Onset Metrics:",
                f"  Onsets: {om.correctly_detected_onsets}/{om.total_expected_onsets} correct",
                f"  Precision: {om.precision:.3f}, Recall: {om.recall:.3f}, F1: {om.f1_score:.3f}",
                f"  Timing error: {om.mean_timing_error_ms:.1f}ms ± {om.std_timing_error_ms:.1f}ms",
            ]
        )

    if test_result.pitch_metrics:
        pm = test_result.pitch_metrics
        lines.extend(
            [
                "",
                "Pitch Metrics:",
                f"  Pitches: {pm.correctly_detected_pitches}/{pm.total_expected_pitches} correct",
                f"  Detection rate: {pm.detection_rate:.3f}",
                f"  Error: {pm.mean_error_cents:.1f} cents ± {pm.std_error_cents:.1f} cents",
                f"  Octave errors: {pm.octave_errors}",
            ]
        )

    if test_result.performance_metrics:
        perf = test_result.performance_metrics
        lines.extend(
            [
                "",
                "Performance Metrics:",
                f"  Frame time: {perf.mean_frame_time_us:.1f}µs (p95: {perf.p95_frame_time_us:.1f}µs)",
                f"  CPU: {perf.cpu_percent:.1f}%, Memory: {perf.memory_mb:.1f}MB",
            ]
        )

    return "\n".join(lines)
