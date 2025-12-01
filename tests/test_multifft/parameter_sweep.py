"""
Parameter Sweep Infrastructure for Multi-FFT Optimization

This module provides utilities for systematically exploring the parameter space
of FFT configurations to find optimal settings for tempo, onset, and pitch
detection.

Sweep Dimensions:
- FFT sizes: Powers of 2 from 256 to 16384
- Hop sizes: Ratios of FFT size (1/2, 1/3, 1/4, 1/6, 1/8)
- Methods: All available aubio methods for each analysis type

Part of Milestone 3: Parameter Optimization
"""

import time
from dataclasses import dataclass, field
from typing import Callable

import aubio
import numpy as np

from .metrics import (
    calculate_onset_metrics,
    calculate_pitch_metrics,
    calculate_tempo_metrics,
)
from .signal_generator import (
    generate_chromatic_scale,
    generate_click_track,
    generate_onset_signal,
)

SAMPLE_RATE = 44100


@dataclass
class FFTConfig:
    """Configuration for a single FFT analysis."""

    fft_size: int
    hop_size: int
    method: str = "default"

    @property
    def frequency_resolution(self) -> float:
        """Frequency resolution in Hz."""
        return SAMPLE_RATE / self.fft_size

    @property
    def time_resolution(self) -> float:
        """Time resolution (hop duration) in seconds."""
        return self.hop_size / SAMPLE_RATE

    @property
    def latency_ms(self) -> float:
        """Latency in milliseconds based on hop size."""
        return (self.hop_size / SAMPLE_RATE) * 1000

    @property
    def overlap_ratio(self) -> float:
        """Overlap ratio between frames."""
        return 1.0 - (self.hop_size / self.fft_size)

    def __hash__(self):
        return hash((self.fft_size, self.hop_size, self.method))


@dataclass
class SweepResult:
    """Result from a single parameter configuration test."""

    config: FFTConfig
    analysis_type: str  # 'tempo', 'onset', or 'pitch'

    # Accuracy metrics
    accuracy_score: float = 0.0  # Normalized 0-1 score
    raw_metrics: dict[str, float] = field(default_factory=dict)

    # Performance metrics
    mean_time_us: float = 0.0
    p95_time_us: float = 0.0
    max_time_us: float = 0.0

    # Combined score (set by optimizer)
    combined_score: float = 0.0

    # Test details
    test_signals: int = 0
    passed_tests: int = 0

    def __lt__(self, other: "SweepResult") -> bool:
        """For sorting by combined score."""
        return self.combined_score < other.combined_score


@dataclass
class SweepConfig:
    """Configuration for a parameter sweep."""

    # FFT sizes to test
    fft_sizes: list[int] = field(
        default_factory=lambda: [512, 1024, 2048, 4096]
    )

    # Hop size ratios (as fraction of FFT size)
    hop_ratios: list[float] = field(
        default_factory=lambda: [1 / 2, 1 / 3, 1 / 4, 1 / 6]
    )

    # Methods to test
    methods: list[str] = field(default_factory=lambda: ["default"])

    # Test signal configurations
    test_bpms: list[int] = field(default_factory=lambda: [80, 120, 160])
    test_attack_types: list[str] = field(
        default_factory=lambda: ["impulse", "sharp", "medium"]
    )
    test_waveforms: list[str] = field(
        default_factory=lambda: ["sine", "triangle"]
    )

    # Duration of test signals
    signal_duration: float = 10.0


# Available methods for each analysis type
ONSET_METHODS = [
    "energy",
    "hfc",
    "complex",
    "phase",
    "wphase",
    "specdiff",
    "kl",
    "mkl",
    "specflux",
]

PITCH_METHODS = ["yinfft", "yin", "yinfast", "specacf", "schmitt"]

TEMPO_METHODS = ["default"]  # aubio.tempo only supports 'default'


def generate_fft_configs(
    analysis_type: str,
    sweep_config: SweepConfig | None = None,
) -> list[FFTConfig]:
    """
    Generate all FFT configurations to test for an analysis type.

    Args:
        analysis_type: 'tempo', 'onset', or 'pitch'
        sweep_config: Optional sweep configuration

    Returns:
        List of FFTConfig objects to test
    """
    if sweep_config is None:
        sweep_config = SweepConfig()

    # Default FFT sizes for each analysis type
    fft_sizes = {
        "onset": [512, 1024, 2048, 4096],
        "tempo": [1024, 2048, 4096, 8192],
        "pitch": [2048, 4096, 8192, 16384],
    }.get(analysis_type, sweep_config.fft_sizes)

    # Methods for each analysis type
    methods = {
        "onset": ONSET_METHODS,
        "tempo": TEMPO_METHODS,
        "pitch": PITCH_METHODS,
    }.get(analysis_type, ["default"])

    configs = []
    for fft_size in fft_sizes:
        for hop_ratio in sweep_config.hop_ratios:
            hop_size = int(fft_size * hop_ratio)
            # Ensure hop size is at least 64
            hop_size = max(64, hop_size)

            for method in methods:
                configs.append(
                    FFTConfig(
                        fft_size=fft_size,
                        hop_size=hop_size,
                        method=method,
                    )
                )

    return configs


class ParameterSweeper:
    """
    Performs systematic parameter sweeps for audio analysis optimization.

    This class tests all combinations of FFT sizes, hop sizes, and methods
    to find optimal configurations for tempo, onset, and pitch detection.
    """

    def __init__(
        self,
        sweep_config: SweepConfig | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ):
        """
        Initialize the parameter sweeper.

        Args:
            sweep_config: Configuration for the sweep
            progress_callback: Optional callback(message, current, total)
        """
        self.config = sweep_config or SweepConfig()
        self.progress_callback = progress_callback
        self.results: dict[str, list[SweepResult]] = {
            "tempo": [],
            "onset": [],
            "pitch": [],
        }

    def _report_progress(self, message: str, current: int, total: int) -> None:
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(message, current, total)

    def sweep_tempo(
        self,
        configs: list[FFTConfig] | None = None,
    ) -> list[SweepResult]:
        """
        Sweep tempo detection parameters.

        Args:
            configs: Optional list of configurations to test

        Returns:
            List of SweepResult objects
        """
        if configs is None:
            configs = generate_fft_configs("tempo", self.config)

        results = []
        total = len(configs)

        for idx, config in enumerate(configs):
            self._report_progress(
                f"Testing tempo: {config.fft_size}/{config.hop_size}",
                idx + 1,
                total,
            )

            result = self._test_tempo_config(config)
            results.append(result)

        self.results["tempo"] = results
        return results

    def _test_tempo_config(self, config: FFTConfig) -> SweepResult:
        """Test a single tempo configuration across test signals."""
        all_bpm_errors = []
        all_recalls = []
        all_times = []

        for bpm in self.config.test_bpms:
            try:
                # Generate test signal
                audio, signal_def = generate_click_track(
                    bpm=bpm,
                    duration=self.config.signal_duration,
                    sample_rate=SAMPLE_RATE,
                )

                # Create tempo tracker
                tempo = aubio.tempo(
                    config.method,
                    config.fft_size,
                    config.hop_size,
                    SAMPLE_RATE,
                )

                # Enable available features
                self._enable_tempo_features(tempo)

                # Analyze
                detected_beats = []
                times = []

                for i in range(0, len(audio) - config.hop_size, config.hop_size):
                    chunk = audio[i : i + config.hop_size].astype(np.float32)
                    t0 = time.perf_counter()
                    is_beat = tempo(chunk)
                    times.append((time.perf_counter() - t0) * 1_000_000)

                    if is_beat:
                        detected_beats.append(i / SAMPLE_RATE)

                detected_bpm = float(tempo.get_bpm())

                # Calculate metrics
                metrics = calculate_tempo_metrics(
                    detected_beats=detected_beats,
                    expected_beats=signal_def.ground_truth.beats,
                    detected_bpm=detected_bpm,
                    expected_bpm=bpm,
                )

                # Handle octave errors (double/half tempo detection)
                bpm_error = metrics.bpm_error
                if abs(detected_bpm - bpm * 2) < abs(bpm_error):
                    bpm_error = abs(detected_bpm - bpm * 2)
                if abs(detected_bpm - bpm / 2) < abs(bpm_error):
                    bpm_error = abs(detected_bpm - bpm / 2)

                all_bpm_errors.append(bpm_error)
                all_recalls.append(metrics.recall)
                all_times.extend(times)

            except Exception as e:
                # Config may not work for all signals
                print(f"Error testing tempo config {config}: {e}")

        # Calculate aggregate metrics
        if all_bpm_errors:
            avg_bpm_error = float(np.mean(all_bpm_errors))
            avg_recall = float(np.mean(all_recalls))

            # Accuracy score: combine BPM accuracy and beat recall
            # BPM score: 1.0 at 0 error, 0.0 at 10+ BPM error
            bpm_score = max(0.0, 1.0 - avg_bpm_error / 10.0)
            accuracy_score = 0.7 * bpm_score + 0.3 * avg_recall

            return SweepResult(
                config=config,
                analysis_type="tempo",
                accuracy_score=accuracy_score,
                raw_metrics={
                    "avg_bpm_error": avg_bpm_error,
                    "avg_recall": avg_recall,
                },
                mean_time_us=float(np.mean(all_times)),
                p95_time_us=float(np.percentile(all_times, 95)),
                max_time_us=float(np.max(all_times)),
                test_signals=len(self.config.test_bpms),
                passed_tests=sum(
                    1 for e in all_bpm_errors if e < 5.0
                ),
            )

        return SweepResult(
            config=config,
            analysis_type="tempo",
            accuracy_score=0.0,
            test_signals=len(self.config.test_bpms),
        )

    def _enable_tempo_features(self, tempo: aubio.tempo) -> None:
        """Enable available tempo features."""
        features = [
            lambda: tempo.set_multi_octave(1),
            lambda: tempo.set_onset_enhancement(1),
            lambda: tempo.set_fft_autocorr(1),
            lambda: tempo.set_dynamic_tempo(1),
            lambda: tempo.set_adaptive_winlen(1),
            lambda: tempo.set_use_tempogram(1),
        ]
        for setter in features:
            try:
                setter()
            except (ValueError, RuntimeError, AttributeError):
                pass

    def sweep_onset(
        self,
        configs: list[FFTConfig] | None = None,
    ) -> list[SweepResult]:
        """
        Sweep onset detection parameters.

        Args:
            configs: Optional list of configurations to test

        Returns:
            List of SweepResult objects
        """
        if configs is None:
            configs = generate_fft_configs("onset", self.config)

        results = []
        total = len(configs)

        for idx, config in enumerate(configs):
            self._report_progress(
                f"Testing onset: {config.method} {config.fft_size}/{config.hop_size}",
                idx + 1,
                total,
            )

            result = self._test_onset_config(config)
            results.append(result)

        self.results["onset"] = results
        return results

    def _test_onset_config(self, config: FFTConfig) -> SweepResult:
        """Test a single onset configuration across test signals."""
        all_f1_scores = []
        all_precisions = []
        all_recalls = []
        all_times = []

        for attack_type in self.config.test_attack_types:
            try:
                # Generate test signal
                audio, signal_def = generate_onset_signal(
                    attack_type=attack_type,
                    interval_ms=500.0,
                    duration=self.config.signal_duration,
                    sample_rate=SAMPLE_RATE,
                )

                # Create onset detector
                onset = aubio.onset(
                    config.method,
                    config.fft_size,
                    config.hop_size,
                    SAMPLE_RATE,
                )

                # Analyze
                detected_onsets = []
                times = []

                for i in range(0, len(audio) - config.hop_size, config.hop_size):
                    chunk = audio[i : i + config.hop_size].astype(np.float32)
                    t0 = time.perf_counter()
                    is_onset = onset(chunk)
                    times.append((time.perf_counter() - t0) * 1_000_000)

                    if is_onset:
                        detected_onsets.append(i / SAMPLE_RATE)

                # Calculate metrics
                metrics = calculate_onset_metrics(
                    detected_onsets=detected_onsets,
                    expected_onsets=signal_def.ground_truth.onsets,
                )

                all_f1_scores.append(metrics.f1_score)
                all_precisions.append(metrics.precision)
                all_recalls.append(metrics.recall)
                all_times.extend(times)

            except Exception as e:
                print(f"Error testing onset config {config}: {e}")

        # Calculate aggregate metrics
        if all_f1_scores:
            avg_f1 = float(np.mean(all_f1_scores))
            avg_precision = float(np.mean(all_precisions))
            avg_recall = float(np.mean(all_recalls))

            return SweepResult(
                config=config,
                analysis_type="onset",
                accuracy_score=avg_f1,
                raw_metrics={
                    "avg_f1": avg_f1,
                    "avg_precision": avg_precision,
                    "avg_recall": avg_recall,
                },
                mean_time_us=float(np.mean(all_times)),
                p95_time_us=float(np.percentile(all_times, 95)),
                max_time_us=float(np.max(all_times)),
                test_signals=len(self.config.test_attack_types),
                passed_tests=sum(
                    1 for f1 in all_f1_scores if f1 >= 0.5
                ),
            )

        return SweepResult(
            config=config,
            analysis_type="onset",
            accuracy_score=0.0,
            test_signals=len(self.config.test_attack_types),
        )

    def sweep_pitch(
        self,
        configs: list[FFTConfig] | None = None,
    ) -> list[SweepResult]:
        """
        Sweep pitch detection parameters.

        Args:
            configs: Optional list of configurations to test

        Returns:
            List of SweepResult objects
        """
        if configs is None:
            configs = generate_fft_configs("pitch", self.config)

        results = []
        total = len(configs)

        for idx, config in enumerate(configs):
            self._report_progress(
                f"Testing pitch: {config.method} {config.fft_size}/{config.hop_size}",
                idx + 1,
                total,
            )

            result = self._test_pitch_config(config)
            results.append(result)

        self.results["pitch"] = results
        return results

    def _test_pitch_config(self, config: FFTConfig) -> SweepResult:
        """Test a single pitch configuration across test signals."""
        all_detection_rates = []
        all_error_cents = []
        all_times = []

        for waveform in self.config.test_waveforms:
            try:
                # Generate test signal
                audio, signal_def = generate_chromatic_scale(
                    start_midi=48,
                    end_midi=60,
                    note_duration=0.5,
                    sample_rate=SAMPLE_RATE,
                    waveform=waveform,
                )

                # Create pitch detector
                pitch = aubio.pitch(
                    config.method,
                    config.fft_size,
                    config.hop_size,
                    SAMPLE_RATE,
                )
                pitch.set_unit("midi")
                pitch.set_tolerance(0.8)

                # Analyze
                detected_pitches = []
                times = []

                for i in range(0, len(audio) - config.hop_size, config.hop_size):
                    chunk = audio[i : i + config.hop_size].astype(np.float32)
                    t0 = time.perf_counter()
                    midi_note = float(pitch(chunk)[0])
                    times.append((time.perf_counter() - t0) * 1_000_000)

                    pitch_time = i / SAMPLE_RATE
                    if midi_note > 20:
                        detected_pitches.append((pitch_time, midi_note))

                # Calculate metrics
                metrics = calculate_pitch_metrics(
                    detected_pitches=detected_pitches,
                    expected_pitches=signal_def.ground_truth.pitches,
                )

                all_detection_rates.append(metrics.detection_rate)
                if metrics.mean_error_cents != 0:
                    all_error_cents.append(abs(metrics.mean_error_cents))
                all_times.extend(times)

            except Exception as e:
                print(f"Error testing pitch config {config}: {e}")

        # Calculate aggregate metrics
        if all_detection_rates:
            avg_detection_rate = float(np.mean(all_detection_rates))
            avg_error_cents = (
                float(np.mean(all_error_cents)) if all_error_cents else 0.0
            )

            # Accuracy score: combine detection rate and error
            # Error score: 1.0 at 0 cents, 0.0 at 100+ cents
            error_score = max(0.0, 1.0 - avg_error_cents / 100.0)
            accuracy_score = 0.7 * avg_detection_rate + 0.3 * error_score

            return SweepResult(
                config=config,
                analysis_type="pitch",
                accuracy_score=accuracy_score,
                raw_metrics={
                    "avg_detection_rate": avg_detection_rate,
                    "avg_error_cents": avg_error_cents,
                },
                mean_time_us=float(np.mean(all_times)),
                p95_time_us=float(np.percentile(all_times, 95)),
                max_time_us=float(np.max(all_times)),
                test_signals=len(self.config.test_waveforms),
                passed_tests=sum(
                    1 for r in all_detection_rates if r >= 0.5
                ),
            )

        return SweepResult(
            config=config,
            analysis_type="pitch",
            accuracy_score=0.0,
            test_signals=len(self.config.test_waveforms),
        )

    def sweep_all(self) -> dict[str, list[SweepResult]]:
        """
        Run complete parameter sweep for all analysis types.

        Returns:
            Dictionary mapping analysis type to list of results
        """
        self.sweep_tempo()
        self.sweep_onset()
        self.sweep_pitch()
        return self.results

    def get_best_configs(
        self,
        analysis_type: str,
        n: int = 5,
    ) -> list[SweepResult]:
        """
        Get top N configurations for an analysis type by accuracy.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            n: Number of top results to return

        Returns:
            List of top N SweepResult objects
        """
        results = self.results.get(analysis_type, [])
        sorted_results = sorted(
            results, key=lambda r: r.accuracy_score, reverse=True
        )
        return sorted_results[:n]

    def get_fastest_configs(
        self,
        analysis_type: str,
        min_accuracy: float = 0.5,
        n: int = 5,
    ) -> list[SweepResult]:
        """
        Get fastest configurations meeting minimum accuracy threshold.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            min_accuracy: Minimum accuracy score required
            n: Number of results to return

        Returns:
            List of fastest SweepResult objects meeting threshold
        """
        results = self.results.get(analysis_type, [])
        qualified = [r for r in results if r.accuracy_score >= min_accuracy]
        sorted_results = sorted(qualified, key=lambda r: r.mean_time_us)
        return sorted_results[:n]

    def generate_summary(self) -> str:
        """Generate a text summary of sweep results."""
        lines = []
        lines.append("=" * 70)
        lines.append("PARAMETER SWEEP SUMMARY")
        lines.append("=" * 70)

        for analysis_type in ["tempo", "onset", "pitch"]:
            results = self.results.get(analysis_type, [])
            if not results:
                continue

            lines.append(f"\n{analysis_type.upper()} ANALYSIS")
            lines.append("-" * 40)
            lines.append(f"Configurations tested: {len(results)}")

            # Best by accuracy
            best = self.get_best_configs(analysis_type, 3)
            lines.append("\nTop 3 by accuracy:")
            for r in best:
                lines.append(
                    f"  {r.config.method:10s} ({r.config.fft_size:5d}, {r.config.hop_size:4d}): "
                    f"accuracy={r.accuracy_score:.3f}, time={r.mean_time_us:.1f}µs"
                )

            # Fastest
            fastest = self.get_fastest_configs(analysis_type, 0.4, 3)
            if fastest:
                lines.append("\nTop 3 fastest (accuracy >= 0.4):")
                for r in fastest:
                    lines.append(
                        f"  {r.config.method:10s} ({r.config.fft_size:5d}, {r.config.hop_size:4d}): "
                        f"time={r.mean_time_us:.1f}µs, accuracy={r.accuracy_score:.3f}"
                    )

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


def run_quick_sweep() -> dict[str, list[SweepResult]]:
    """
    Run a quick parameter sweep with reduced configuration space.

    Good for quick testing and development.

    Returns:
        Dictionary of sweep results
    """
    config = SweepConfig(
        fft_sizes=[1024, 2048],
        hop_ratios=[1 / 2, 1 / 4],
        test_bpms=[120],
        test_attack_types=["impulse", "sharp"],
        test_waveforms=["sine"],
        signal_duration=5.0,
    )

    sweeper = ParameterSweeper(config)
    return sweeper.sweep_all()


def run_full_sweep(
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict[str, list[SweepResult]]:
    """
    Run a comprehensive parameter sweep.

    This tests all FFT sizes, hop ratios, and methods for all analysis types.
    Can take several minutes to complete.

    Args:
        progress_callback: Optional progress callback function

    Returns:
        Dictionary of sweep results
    """
    config = SweepConfig(
        fft_sizes=[512, 1024, 2048, 4096],
        hop_ratios=[1 / 2, 1 / 3, 1 / 4, 1 / 6],
        test_bpms=[60, 80, 100, 120, 140, 160, 180],
        test_attack_types=["impulse", "sharp", "medium", "slow"],
        test_waveforms=["sine", "triangle"],
        signal_duration=10.0,
    )

    sweeper = ParameterSweeper(config, progress_callback)
    return sweeper.sweep_all()
