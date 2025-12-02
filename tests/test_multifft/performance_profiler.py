"""
Performance Profiling Integration for Multi-FFT Testing

This module provides utilities for collecting and analyzing performance
metrics during audio analysis, including:
- Per-FFT configuration timing
- CPU usage estimation
- Memory footprint measurement
- FFT deduplication analysis

Part of Milestone 2: Performance Profiling Integration
"""

import gc
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .metrics import PerformanceMetrics


@dataclass
class FFTProfile:
    """Detailed profile for a single FFT configuration."""

    fft_size: int
    hop_size: int
    sample_rate: int = 44100

    # Timing statistics (microseconds)
    call_count: int = 0
    total_time_us: float = 0.0
    min_time_us: float = float("inf")
    max_time_us: float = 0.0
    times: list[float] = field(default_factory=list)

    @property
    def mean_time_us(self) -> float:
        """Calculate mean processing time."""
        if self.call_count == 0:
            return 0.0
        return self.total_time_us / self.call_count

    @property
    def std_time_us(self) -> float:
        """Calculate standard deviation of processing time."""
        if len(self.times) < 2:
            return 0.0
        return float(np.std(self.times))

    @property
    def p50_time_us(self) -> float:
        """Calculate median processing time."""
        if not self.times:
            return 0.0
        return float(np.percentile(self.times, 50))

    @property
    def p95_time_us(self) -> float:
        """Calculate 95th percentile processing time."""
        if not self.times:
            return 0.0
        return float(np.percentile(self.times, 95))

    @property
    def p99_time_us(self) -> float:
        """Calculate 99th percentile processing time."""
        if not self.times:
            return 0.0
        return float(np.percentile(self.times, 99))

    def record_time(self, time_us: float) -> None:
        """Record a timing measurement."""
        self.call_count += 1
        self.total_time_us += time_us
        self.min_time_us = min(self.min_time_us, time_us)
        self.max_time_us = max(self.max_time_us, time_us)
        self.times.append(time_us)

    @property
    def theoretical_max_fps(self) -> float:
        """Calculate theoretical maximum FPS based on mean processing time."""
        if self.mean_time_us == 0:
            return float("inf")
        # Convert µs to seconds, then to FPS
        return 1_000_000 / self.mean_time_us

    @property
    def frequency_resolution(self) -> float:
        """Calculate frequency resolution in Hz."""
        return self.sample_rate / self.fft_size

    @property
    def time_resolution(self) -> float:
        """Calculate time resolution (hop size) in seconds."""
        return self.hop_size / self.sample_rate

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fft_size": self.fft_size,
            "hop_size": self.hop_size,
            "sample_rate": self.sample_rate,
            "call_count": self.call_count,
            "mean_time_us": self.mean_time_us,
            "std_time_us": self.std_time_us,
            "min_time_us": (
                self.min_time_us if self.min_time_us != float("inf") else 0.0
            ),
            "max_time_us": self.max_time_us,
            "p50_time_us": self.p50_time_us,
            "p95_time_us": self.p95_time_us,
            "p99_time_us": self.p99_time_us,
            "theoretical_max_fps": self.theoretical_max_fps,
            "frequency_resolution": self.frequency_resolution,
            "time_resolution": self.time_resolution,
        }


@dataclass
class PresetProfile:
    """Complete profile for an FFT preset."""

    preset_name: str
    fft_profiles: dict[str, FFTProfile] = field(default_factory=dict)

    # Overall timing
    total_frames: int = 0
    total_time_us: float = 0.0
    frame_times: list[float] = field(default_factory=list)

    # Memory tracking
    peak_memory_mb: float = 0.0

    @property
    def mean_frame_time_us(self) -> float:
        """Calculate mean frame processing time."""
        if self.total_frames == 0:
            return 0.0
        return self.total_time_us / self.total_frames

    @property
    def p95_frame_time_us(self) -> float:
        """Calculate 95th percentile frame time."""
        if not self.frame_times:
            return 0.0
        return float(np.percentile(self.frame_times, 95))

    @property
    def p99_frame_time_us(self) -> float:
        """Calculate 99th percentile frame time."""
        if not self.frame_times:
            return 0.0
        return float(np.percentile(self.frame_times, 99))

    @property
    def theoretical_max_fps(self) -> float:
        """Calculate theoretical maximum FPS."""
        if self.mean_frame_time_us == 0:
            return float("inf")
        return 1_000_000 / self.mean_frame_time_us

    @property
    def frame_budget_at_120fps(self) -> float:
        """Calculate percentage of frame budget used at 120 FPS."""
        # At 120 FPS, frame budget is ~8333 µs
        budget_us = 1_000_000 / 120
        return (self.mean_frame_time_us / budget_us) * 100

    def add_fft_profile(self, analysis_type: str, profile: FFTProfile) -> None:
        """Add an FFT profile for an analysis type."""
        self.fft_profiles[analysis_type] = profile

    def record_frame(self, frame_time_us: float) -> None:
        """Record a frame timing."""
        self.total_frames += 1
        self.total_time_us += frame_time_us
        self.frame_times.append(frame_time_us)

    def to_performance_metrics(self) -> PerformanceMetrics:
        """Convert to PerformanceMetrics."""
        metrics = PerformanceMetrics()
        metrics.mean_frame_time_us = self.mean_frame_time_us
        metrics.p95_frame_time_us = self.p95_frame_time_us
        metrics.p99_frame_time_us = self.p99_frame_time_us
        metrics.max_frame_time_us = (
            max(self.frame_times) if self.frame_times else 0.0
        )
        metrics.memory_mb = self.peak_memory_mb

        for analysis_type, profile in self.fft_profiles.items():
            metrics.fft_timings[(profile.fft_size, profile.hop_size)] = (
                profile.mean_time_us
            )

        return metrics

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "preset_name": self.preset_name,
            "total_frames": self.total_frames,
            "mean_frame_time_us": self.mean_frame_time_us,
            "p95_frame_time_us": self.p95_frame_time_us,
            "p99_frame_time_us": self.p99_frame_time_us,
            "theoretical_max_fps": self.theoretical_max_fps,
            "frame_budget_at_120fps": self.frame_budget_at_120fps,
            "peak_memory_mb": self.peak_memory_mb,
            "fft_profiles": {
                name: profile.to_dict()
                for name, profile in self.fft_profiles.items()
            },
        }


class PerformanceProfiler:
    """
    Profiler for measuring FFT processing performance.

    Collects detailed timing data for each FFT configuration and provides
    aggregate statistics for comparison across presets.
    """

    def __init__(self):
        self.preset_profiles: dict[str, PresetProfile] = {}
        self._current_preset: str | None = None
        self._frame_start_time: float = 0.0

    def start_preset(self, preset_name: str) -> None:
        """Start profiling a new preset."""
        if preset_name not in self.preset_profiles:
            self.preset_profiles[preset_name] = PresetProfile(
                preset_name=preset_name
            )
        self._current_preset = preset_name

        # Force garbage collection before profiling
        gc.collect()

    def end_preset(self) -> None:
        """End profiling the current preset."""
        self._current_preset = None

    def start_frame(self) -> None:
        """Mark the start of a frame."""
        self._frame_start_time = time.perf_counter()

    def end_frame(self) -> None:
        """Mark the end of a frame and record timing."""
        if self._current_preset and self._frame_start_time > 0:
            elapsed_us = (
                time.perf_counter() - self._frame_start_time
            ) * 1_000_000
            self.preset_profiles[self._current_preset].record_frame(elapsed_us)
        self._frame_start_time = 0.0

    def record_fft_time(
        self,
        analysis_type: str,
        fft_size: int,
        hop_size: int,
        time_us: float,
        sample_rate: int = 44100,
    ) -> None:
        """Record FFT processing time for an analysis type."""
        if not self._current_preset:
            return

        profile = self.preset_profiles[self._current_preset]
        if analysis_type not in profile.fft_profiles:
            profile.fft_profiles[analysis_type] = FFTProfile(
                fft_size=fft_size,
                hop_size=hop_size,
                sample_rate=sample_rate,
            )
        profile.fft_profiles[analysis_type].record_time(time_us)

    def get_comparison_table(self) -> str:
        """Generate a comparison table of all presets."""
        lines = []
        lines.append("=" * 80)
        lines.append("PERFORMANCE COMPARISON")
        lines.append("=" * 80)
        lines.append("")

        # Header
        lines.append(
            f"{'Preset':<15} {'Mean (µs)':<12} {'P95 (µs)':<12} {'Max FPS':<10} {'Budget %':<10}"
        )
        lines.append("-" * 60)

        for preset_name, profile in self.preset_profiles.items():
            lines.append(
                f"{preset_name:<15} "
                f"{profile.mean_frame_time_us:<12.1f} "
                f"{profile.p95_frame_time_us:<12.1f} "
                f"{profile.theoretical_max_fps:<10.0f} "
                f"{profile.frame_budget_at_120fps:<10.1f}"
            )

        lines.append("")

        # Per-FFT breakdown
        lines.append("FFT Configuration Breakdown:")
        lines.append("-" * 80)

        for preset_name, profile in self.preset_profiles.items():
            lines.append(f"\n{preset_name}:")
            for analysis_type, fft_profile in profile.fft_profiles.items():
                lines.append(
                    f"  {analysis_type:<8} ({fft_profile.fft_size},{fft_profile.hop_size}): "
                    f"mean={fft_profile.mean_time_us:.1f}µs, "
                    f"p95={fft_profile.p95_time_us:.1f}µs, "
                    f"calls={fft_profile.call_count}"
                )

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics for all presets."""
        return {
            preset_name: profile.to_dict()
            for preset_name, profile in self.preset_profiles.items()
        }


def calculate_fft_deduplication_savings(
    preset_configs: dict[str, tuple[int, int]],
) -> dict[str, Any]:
    """
    Calculate potential savings from FFT deduplication.

    Args:
        preset_configs: Dict mapping analysis type to (fft_size, hop_size)

    Returns:
        Dictionary with deduplication analysis
    """
    # Group by unique configurations
    unique_configs = set(preset_configs.values())
    total_configs = len(preset_configs)

    # Calculate which analyses share configurations
    sharing_map: dict[tuple[int, int], list[str]] = defaultdict(list)
    for analysis_type, config in preset_configs.items():
        sharing_map[config].append(analysis_type)

    # Calculate savings
    saved_configs = total_configs - len(unique_configs)
    savings_percent = (
        (saved_configs / total_configs * 100) if total_configs > 0 else 0
    )

    return {
        "total_analyses": total_configs,
        "unique_configs": len(unique_configs),
        "deduplicated_configs": saved_configs,
        "savings_percent": savings_percent,
        "sharing_map": {
            f"({fft},{hop})": analyses
            for (fft, hop), analyses in sharing_map.items()
        },
    }


def estimate_memory_usage(
    preset_configs: dict[str, tuple[int, int]],
) -> dict[str, float]:
    """
    Estimate memory usage for FFT configurations.

    Args:
        preset_configs: Dict mapping analysis type to (fft_size, hop_size)

    Returns:
        Dictionary with memory estimates in bytes
    """
    estimates = {}

    for analysis_type, (fft_size, hop_size) in preset_configs.items():
        # Phase vocoder: 2 complex arrays of fft_size floats each
        pvoc_memory = 2 * fft_size * 8  # 8 bytes per complex float

        # Input buffer: hop_size floats
        input_buffer = hop_size * 4  # 4 bytes per float32

        # Output buffer: fft_size/2+1 complex values for cvec
        output_buffer = (fft_size // 2 + 1) * 8

        total = pvoc_memory + input_buffer + output_buffer
        estimates[analysis_type] = total

    # Add total
    unique_configs = set(preset_configs.values())
    total_memory = 0
    for fft_size, hop_size in unique_configs:
        pvoc_memory = 2 * fft_size * 8
        input_buffer = hop_size * 4
        output_buffer = (fft_size // 2 + 1) * 8
        total_memory += pvoc_memory + input_buffer + output_buffer

    estimates["total"] = total_memory
    estimates["total_kb"] = total_memory / 1024
    estimates["total_mb"] = total_memory / (1024 * 1024)

    return estimates


def print_performance_summary(profiler: PerformanceProfiler) -> None:
    """Print a formatted performance summary."""
    print(profiler.get_comparison_table())
