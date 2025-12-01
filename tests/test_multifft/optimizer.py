"""
Multi-Objective Optimization for FFT Parameter Selection

This module implements multi-objective optimization to find the best
FFT configurations balancing accuracy, latency, and computational cost.

Features:
- Configurable weight profiles for different use cases
- Pareto front identification
- Dominated solution filtering
- Recommendation generation

Part of Milestone 3: Parameter Optimization
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from .parameter_sweep import FFTConfig, SweepResult


class OptimizationProfile(Enum):
    """Pre-defined optimization profiles for different use cases."""

    ACCURACY_FOCUSED = "accuracy_focused"
    LATENCY_FOCUSED = "latency_focused"
    BALANCED = "balanced"
    CPU_EFFICIENT = "cpu_efficient"


@dataclass
class OptimizationWeights:
    """Weights for multi-objective optimization."""

    accuracy: float = 0.6
    latency: float = 0.3
    cpu: float = 0.1

    def __post_init__(self):
        """Normalize weights to sum to 1.0."""
        total = self.accuracy + self.latency + self.cpu
        if total > 0:
            self.accuracy /= total
            self.latency /= total
            self.cpu /= total

    @classmethod
    def from_profile(
        cls, profile: OptimizationProfile
    ) -> "OptimizationWeights":
        """Create weights from a predefined profile."""
        profiles = {
            OptimizationProfile.ACCURACY_FOCUSED: cls(0.8, 0.15, 0.05),
            OptimizationProfile.LATENCY_FOCUSED: cls(0.3, 0.6, 0.1),
            OptimizationProfile.BALANCED: cls(0.5, 0.35, 0.15),
            OptimizationProfile.CPU_EFFICIENT: cls(0.3, 0.2, 0.5),
        }
        return profiles.get(profile, cls())


@dataclass
class OptimizedConfig:
    """An optimized configuration with scoring details."""

    config: FFTConfig
    analysis_type: str

    # Raw metrics
    accuracy_score: float = 0.0
    latency_us: float = 0.0
    cpu_estimate: float = 0.0

    # Normalized scores (0-1, higher is better)
    normalized_accuracy: float = 0.0
    normalized_latency: float = 0.0  # Inverted: lower latency = higher score
    normalized_cpu: float = 0.0  # Inverted: lower CPU = higher score

    # Final combined score
    combined_score: float = 0.0

    # Pareto optimality
    is_pareto_optimal: bool = False
    dominated_by: list[str] = field(default_factory=list)

    @property
    def config_id(self) -> str:
        """Unique identifier for this configuration."""
        return f"{self.config.method}_{self.config.fft_size}_{self.config.hop_size}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "config": {
                "method": self.config.method,
                "fft_size": self.config.fft_size,
                "hop_size": self.config.hop_size,
            },
            "analysis_type": self.analysis_type,
            "accuracy_score": self.accuracy_score,
            "latency_us": self.latency_us,
            "cpu_estimate": self.cpu_estimate,
            "combined_score": self.combined_score,
            "is_pareto_optimal": self.is_pareto_optimal,
        }


class MultiObjectiveOptimizer:
    """
    Multi-objective optimizer for FFT configuration selection.

    Balances accuracy, latency, and computational cost to find optimal
    configurations for different use cases.
    """

    def __init__(self, weights: OptimizationWeights | None = None):
        """
        Initialize the optimizer.

        Args:
            weights: Optimization weights (default: balanced profile)
        """
        self.weights = weights or OptimizationWeights.from_profile(
            OptimizationProfile.BALANCED
        )
        self.optimized_configs: dict[str, list[OptimizedConfig]] = {}

    def set_weights(self, weights: OptimizationWeights) -> None:
        """Update optimization weights."""
        self.weights = weights

    def set_profile(self, profile: OptimizationProfile) -> None:
        """Set weights from a predefined profile."""
        self.weights = OptimizationWeights.from_profile(profile)

    def optimize(
        self,
        results: list[SweepResult],
        analysis_type: str,
    ) -> list[OptimizedConfig]:
        """
        Optimize configurations from sweep results.

        Args:
            results: List of SweepResult from parameter sweep
            analysis_type: 'tempo', 'onset', or 'pitch'

        Returns:
            List of OptimizedConfig sorted by combined score
        """
        if not results:
            return []

        # Extract metrics for normalization
        accuracies = [r.accuracy_score for r in results]
        latencies = [r.mean_time_us for r in results]

        # Estimate CPU usage based on FFT complexity
        cpu_estimates = [
            self._estimate_cpu_usage(r.config, r.mean_time_us) for r in results
        ]

        # Normalize metrics
        acc_min, acc_max = min(accuracies), max(accuracies)
        lat_min, lat_max = min(latencies), max(latencies)
        cpu_min, cpu_max = min(cpu_estimates), max(cpu_estimates)

        optimized = []
        for result, cpu_est in zip(results, cpu_estimates):
            config = OptimizedConfig(
                config=result.config,
                analysis_type=analysis_type,
                accuracy_score=result.accuracy_score,
                latency_us=result.mean_time_us,
                cpu_estimate=cpu_est,
            )

            # Normalize (0-1 scale)
            if acc_max > acc_min:
                config.normalized_accuracy = (
                    result.accuracy_score - acc_min
                ) / (acc_max - acc_min)
            else:
                config.normalized_accuracy = 1.0

            # Invert latency (lower is better -> higher normalized score)
            if lat_max > lat_min:
                config.normalized_latency = 1.0 - (
                    result.mean_time_us - lat_min
                ) / (lat_max - lat_min)
            else:
                config.normalized_latency = 1.0

            # Invert CPU (lower is better -> higher normalized score)
            if cpu_max > cpu_min:
                config.normalized_cpu = 1.0 - (cpu_est - cpu_min) / (
                    cpu_max - cpu_min
                )
            else:
                config.normalized_cpu = 1.0

            # Calculate combined score
            config.combined_score = (
                self.weights.accuracy * config.normalized_accuracy
                + self.weights.latency * config.normalized_latency
                + self.weights.cpu * config.normalized_cpu
            )

            optimized.append(config)

        # Identify Pareto-optimal solutions
        self._identify_pareto_optimal(optimized)

        # Sort by combined score
        optimized.sort(key=lambda x: x.combined_score, reverse=True)

        self.optimized_configs[analysis_type] = optimized
        return optimized

    def _estimate_cpu_usage(
        self,
        config: FFTConfig,
        measured_time_us: float,
    ) -> float:
        """
        Estimate CPU usage for a configuration.

        Combines measured timing with theoretical FFT complexity.
        """
        # FFT complexity: O(N log N)
        fft_complexity = config.fft_size * np.log2(config.fft_size)

        # Frames per second based on hop size
        fps = 44100 / config.hop_size

        # Estimated CPU percentage (rough model)
        # Assumes 1000µs baseline per frame at 120fps
        baseline_fps = 120
        cpu_estimate = (measured_time_us * fps) / (1_000_000 / baseline_fps)

        return cpu_estimate

    def _identify_pareto_optimal(
        self,
        configs: list[OptimizedConfig],
    ) -> None:
        """
        Identify Pareto-optimal configurations.

        A configuration is Pareto-optimal if no other configuration
        dominates it (i.e., is better in all objectives).
        """
        for config in configs:
            config.is_pareto_optimal = True
            config.dominated_by = []

        for i, config_a in enumerate(configs):
            for j, config_b in enumerate(configs):
                if i == j:
                    continue

                # Check if config_b dominates config_a
                if self._dominates(config_b, config_a):
                    config_a.is_pareto_optimal = False
                    config_a.dominated_by.append(config_b.config_id)

    def _dominates(
        self,
        config_a: OptimizedConfig,
        config_b: OptimizedConfig,
    ) -> bool:
        """
        Check if config_a dominates config_b.

        A dominates B if A is at least as good as B in all objectives
        and strictly better in at least one.
        """
        at_least_as_good = (
            config_a.normalized_accuracy >= config_b.normalized_accuracy
            and config_a.normalized_latency >= config_b.normalized_latency
            and config_a.normalized_cpu >= config_b.normalized_cpu
        )

        strictly_better = (
            config_a.normalized_accuracy > config_b.normalized_accuracy
            or config_a.normalized_latency > config_b.normalized_latency
            or config_a.normalized_cpu > config_b.normalized_cpu
        )

        return at_least_as_good and strictly_better

    def get_pareto_front(
        self,
        analysis_type: str,
    ) -> list[OptimizedConfig]:
        """
        Get Pareto-optimal configurations for an analysis type.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'

        Returns:
            List of Pareto-optimal configurations
        """
        configs = self.optimized_configs.get(analysis_type, [])
        return [c for c in configs if c.is_pareto_optimal]

    def get_recommendations(
        self,
        analysis_type: str,
        profile: OptimizationProfile | None = None,
    ) -> dict[str, OptimizedConfig | None]:
        """
        Get recommended configurations for different use cases.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            profile: Optional profile to use for recommendations

        Returns:
            Dictionary with recommendations for different scenarios
        """
        configs = self.optimized_configs.get(analysis_type, [])
        if not configs:
            return {
                "best_overall": None,
                "best_accuracy": None,
                "best_latency": None,
                "best_balanced": None,
            }

        pareto = self.get_pareto_front(analysis_type)

        # Best overall (highest combined score with current weights)
        best_overall = configs[0] if configs else None

        # Best accuracy (highest accuracy among Pareto-optimal)
        best_accuracy = max(
            pareto, key=lambda x: x.accuracy_score, default=None
        )

        # Best latency (lowest latency among Pareto-optimal with accuracy >= 0.5)
        qualified = [c for c in pareto if c.accuracy_score >= 0.5]
        best_latency = min(qualified, key=lambda x: x.latency_us, default=None)

        # Best balanced (middle ground)
        balanced_weights = OptimizationWeights.from_profile(
            OptimizationProfile.BALANCED
        )
        best_balanced = max(
            pareto,
            key=lambda x: (
                balanced_weights.accuracy * x.normalized_accuracy
                + balanced_weights.latency * x.normalized_latency
                + balanced_weights.cpu * x.normalized_cpu
            ),
            default=None,
        )

        return {
            "best_overall": best_overall,
            "best_accuracy": best_accuracy,
            "best_latency": best_latency,
            "best_balanced": best_balanced,
        }

    def compare_to_current_presets(
        self,
        analysis_type: str,
        current_presets: dict[str, tuple[int, int]],
    ) -> dict[str, Any]:
        """
        Compare optimized configurations to current preset values.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            current_presets: Dict mapping preset name to (fft_size, hop_size)

        Returns:
            Comparison report
        """
        configs = self.optimized_configs.get(analysis_type, [])

        comparison = {}
        for preset_name, (fft_size, hop_size) in current_presets.items():
            # Find matching config in our results
            matching = [
                c
                for c in configs
                if c.config.fft_size == fft_size
                and c.config.hop_size == hop_size
            ]

            if matching:
                current = matching[0]
                rank = configs.index(current) + 1

                # Find best alternative
                best_similar = self._find_best_similar(
                    configs, current, fft_size, hop_size
                )

                comparison[preset_name] = {
                    "current": current.to_dict(),
                    "rank": rank,
                    "total_configs": len(configs),
                    "percentile": (len(configs) - rank + 1)
                    / len(configs)
                    * 100,
                    "is_pareto_optimal": current.is_pareto_optimal,
                    "suggested_improvement": (
                        best_similar.to_dict() if best_similar else None
                    ),
                }
            else:
                comparison[preset_name] = {
                    "current": {
                        "fft_size": fft_size,
                        "hop_size": hop_size,
                    },
                    "rank": None,
                    "note": "Configuration not tested in sweep",
                }

        return comparison

    def _find_best_similar(
        self,
        configs: list[OptimizedConfig],
        current: OptimizedConfig,
        fft_size: int,
        hop_size: int,
    ) -> OptimizedConfig | None:
        """Find best alternative with similar characteristics."""
        # Look for configs with similar latency but better accuracy
        tolerance = 0.2  # 20% latency tolerance

        candidates = [
            c
            for c in configs
            if c.latency_us <= current.latency_us * (1 + tolerance)
            and c.accuracy_score > current.accuracy_score
            and c.is_pareto_optimal
        ]

        if candidates:
            return max(candidates, key=lambda x: x.accuracy_score)
        return None


def generate_optimization_report(
    optimizer: MultiObjectiveOptimizer,
    analysis_types: list[str] | None = None,
) -> str:
    """
    Generate a comprehensive optimization report.

    Args:
        optimizer: Configured MultiObjectiveOptimizer
        analysis_types: Types to include (default: all)

    Returns:
        Formatted report string
    """
    if analysis_types is None:
        analysis_types = ["tempo", "onset", "pitch"]

    lines = []
    lines.append("=" * 70)
    lines.append("MULTI-OBJECTIVE OPTIMIZATION REPORT")
    lines.append("=" * 70)
    lines.append(
        f"Weights: accuracy={optimizer.weights.accuracy:.2f}, "
        f"latency={optimizer.weights.latency:.2f}, "
        f"cpu={optimizer.weights.cpu:.2f}"
    )

    for analysis_type in analysis_types:
        configs = optimizer.optimized_configs.get(analysis_type, [])
        if not configs:
            continue

        lines.append(f"\n{'-' * 70}")
        lines.append(f"{analysis_type.upper()} ANALYSIS")
        lines.append(f"{'-' * 70}")

        # Pareto front
        pareto = optimizer.get_pareto_front(analysis_type)
        lines.append(f"\nPareto-optimal configurations: {len(pareto)}")
        for config in pareto[:5]:
            lines.append(
                f"  {config.config.method:10s} "
                f"({config.config.fft_size:5d}, {config.config.hop_size:4d}): "
                f"score={config.combined_score:.3f}, "
                f"acc={config.accuracy_score:.3f}, "
                f"lat={config.latency_us:.1f}µs"
            )

        # Recommendations
        recs = optimizer.get_recommendations(analysis_type)
        lines.append("\nRecommendations:")
        for rec_type, config in recs.items():
            if config:
                lines.append(
                    f"  {rec_type:15s}: "
                    f"{config.config.method} "
                    f"({config.config.fft_size}, {config.config.hop_size})"
                )

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def optimize_all_types(
    sweep_results: dict[str, list[SweepResult]],
    profile: OptimizationProfile = OptimizationProfile.BALANCED,
) -> MultiObjectiveOptimizer:
    """
    Run optimization for all analysis types.

    Args:
        sweep_results: Results from parameter sweep
        profile: Optimization profile to use

    Returns:
        Configured MultiObjectiveOptimizer with results
    """
    weights = OptimizationWeights.from_profile(profile)
    optimizer = MultiObjectiveOptimizer(weights)

    for analysis_type, results in sweep_results.items():
        if results:
            optimizer.optimize(results, analysis_type)

    return optimizer
