"""
Pareto Front Analysis and Visualization for FFT Optimization

This module provides tools for analyzing and visualizing the Pareto front
of FFT configurations, helping identify optimal trade-offs between
accuracy, latency, and computational cost.

Features:
- Pareto front extraction and validation
- Trade-off curve analysis
- Text-based visualization for console output
- Data export for external plotting tools

Part of Milestone 3: Parameter Optimization
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from .optimizer import MultiObjectiveOptimizer
from .parameter_sweep import FFTConfig


@dataclass
class ParetoPoint:
    """A single point on the Pareto front."""

    config: FFTConfig
    accuracy: float
    latency_us: float
    cpu_estimate: float

    # Marginal rates (how much latency saved per accuracy lost, etc.)
    marginal_latency_per_accuracy: float = 0.0
    marginal_cpu_per_accuracy: float = 0.0

    @property
    def efficiency_ratio(self) -> float:
        """Ratio of accuracy to latency (higher is better)."""
        if self.latency_us > 0:
            return self.accuracy / self.latency_us * 1000  # Scale for readability
        return 0.0


@dataclass
class ParetoFront:
    """Complete Pareto front for an analysis type."""

    analysis_type: str
    points: list[ParetoPoint] = field(default_factory=list)
    total_configurations: int = 0
    dominated_count: int = 0

    @property
    def efficiency_range(self) -> tuple[float, float]:
        """Range of efficiency ratios on the front."""
        if not self.points:
            return (0.0, 0.0)
        ratios = [p.efficiency_ratio for p in self.points]
        return (min(ratios), max(ratios))

    @property
    def accuracy_range(self) -> tuple[float, float]:
        """Range of accuracy scores on the front."""
        if not self.points:
            return (0.0, 0.0)
        accuracies = [p.accuracy for p in self.points]
        return (min(accuracies), max(accuracies))

    @property
    def latency_range(self) -> tuple[float, float]:
        """Range of latencies on the front."""
        if not self.points:
            return (0.0, 0.0)
        latencies = [p.latency_us for p in self.points]
        return (min(latencies), max(latencies))


class ParetoAnalyzer:
    """
    Analyzer for Pareto fronts and trade-off curves.

    Provides tools for understanding the trade-offs between different
    objectives and identifying optimal configurations for specific needs.
    """

    def __init__(self, optimizer: MultiObjectiveOptimizer):
        """
        Initialize the analyzer.

        Args:
            optimizer: MultiObjectiveOptimizer with results
        """
        self.optimizer = optimizer
        self.fronts: dict[str, ParetoFront] = {}

    def analyze(self, analysis_type: str) -> ParetoFront:
        """
        Analyze Pareto front for an analysis type.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'

        Returns:
            ParetoFront with analysis results
        """
        configs = self.optimizer.optimized_configs.get(analysis_type, [])
        pareto_configs = self.optimizer.get_pareto_front(analysis_type)

        front = ParetoFront(
            analysis_type=analysis_type,
            total_configurations=len(configs),
            dominated_count=len(configs) - len(pareto_configs),
        )

        # Convert to ParetoPoints
        for config in pareto_configs:
            point = ParetoPoint(
                config=config.config,
                accuracy=config.accuracy_score,
                latency_us=config.latency_us,
                cpu_estimate=config.cpu_estimate,
            )
            front.points.append(point)

        # Sort by accuracy (descending) for consistent ordering
        front.points.sort(key=lambda p: p.accuracy, reverse=True)

        # Calculate marginal rates
        self._calculate_marginal_rates(front)

        self.fronts[analysis_type] = front
        return front

    def _calculate_marginal_rates(self, front: ParetoFront) -> None:
        """Calculate marginal rates between adjacent Pareto points."""
        for i in range(1, len(front.points)):
            prev = front.points[i - 1]
            curr = front.points[i]

            # How much accuracy we lose
            accuracy_diff = prev.accuracy - curr.accuracy

            # How much latency we save
            latency_diff = prev.latency_us - curr.latency_us

            # How much CPU we save
            cpu_diff = prev.cpu_estimate - curr.cpu_estimate

            if accuracy_diff > 0:
                curr.marginal_latency_per_accuracy = latency_diff / accuracy_diff
                curr.marginal_cpu_per_accuracy = cpu_diff / accuracy_diff

    def analyze_all(self) -> dict[str, ParetoFront]:
        """Analyze Pareto fronts for all analysis types."""
        for analysis_type in self.optimizer.optimized_configs.keys():
            self.analyze(analysis_type)
        return self.fronts

    def find_knee_point(self, analysis_type: str) -> ParetoPoint | None:
        """
        Find the "knee" of the Pareto front.

        The knee point represents the best trade-off, where marginal
        improvements in one objective require large sacrifices in another.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'

        Returns:
            ParetoPoint at the knee, or None if not found
        """
        front = self.fronts.get(analysis_type)
        if not front or len(front.points) < 3:
            return front.points[0] if front and front.points else None

        # Calculate curvature at each point
        # Knee is where curvature is maximized
        max_curvature = 0.0
        knee_point = front.points[1]  # Default to second point

        for i in range(1, len(front.points) - 1):
            prev = front.points[i - 1]
            curr = front.points[i]
            next_pt = front.points[i + 1]

            # Calculate curvature using cross product
            v1 = (curr.accuracy - prev.accuracy, curr.latency_us - prev.latency_us)
            v2 = (next_pt.accuracy - curr.accuracy, next_pt.latency_us - curr.latency_us)

            # Normalize to account for different scales
            # Scale latency to match accuracy range
            scale = (
                front.accuracy_range[1] - front.accuracy_range[0]
            ) / max(
                front.latency_range[1] - front.latency_range[0], 1
            )

            v1 = (v1[0], v1[1] * scale)
            v2 = (v2[0], v2[1] * scale)

            # Cross product magnitude (curvature proxy)
            cross = abs(v1[0] * v2[1] - v1[1] * v2[0])
            length = np.sqrt(v1[0] ** 2 + v1[1] ** 2) * np.sqrt(
                v2[0] ** 2 + v2[1] ** 2
            )

            if length > 0:
                curvature = cross / length
                if curvature > max_curvature:
                    max_curvature = curvature
                    knee_point = curr

        return knee_point

    def find_target_latency_config(
        self,
        analysis_type: str,
        target_latency_us: float,
    ) -> ParetoPoint | None:
        """
        Find best configuration for a target latency.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            target_latency_us: Target latency in microseconds

        Returns:
            Best ParetoPoint meeting latency constraint
        """
        front = self.fronts.get(analysis_type)
        if not front:
            return None

        # Filter points meeting latency constraint
        qualified = [p for p in front.points if p.latency_us <= target_latency_us]

        if not qualified:
            # Return lowest latency point if none qualify
            return min(front.points, key=lambda p: p.latency_us, default=None)

        # Return highest accuracy among qualified
        return max(qualified, key=lambda p: p.accuracy, default=None)

    def find_target_accuracy_config(
        self,
        analysis_type: str,
        target_accuracy: float,
    ) -> ParetoPoint | None:
        """
        Find fastest configuration for a target accuracy.

        Args:
            analysis_type: 'tempo', 'onset', or 'pitch'
            target_accuracy: Target accuracy score (0-1)

        Returns:
            Fastest ParetoPoint meeting accuracy constraint
        """
        front = self.fronts.get(analysis_type)
        if not front:
            return None

        # Filter points meeting accuracy constraint
        qualified = [p for p in front.points if p.accuracy >= target_accuracy]

        if not qualified:
            # Return highest accuracy point if none qualify
            return max(front.points, key=lambda p: p.accuracy, default=None)

        # Return lowest latency among qualified
        return min(qualified, key=lambda p: p.latency_us, default=None)


def generate_ascii_plot(
    front: ParetoFront,
    width: int = 60,
    height: int = 20,
) -> str:
    """
    Generate ASCII art visualization of Pareto front.

    Args:
        front: ParetoFront to visualize
        width: Plot width in characters
        height: Plot height in lines

    Returns:
        ASCII plot string
    """
    if not front.points:
        return "No Pareto points to plot"

    lines = []
    lines.append(f"Pareto Front: {front.analysis_type.upper()}")
    lines.append(f"Points: {len(front.points)} (of {front.total_configurations} total)")
    lines.append("")

    # Get ranges
    acc_min, acc_max = front.accuracy_range
    lat_min, lat_max = front.latency_range

    # Add margin
    acc_range = max(acc_max - acc_min, 0.1)
    lat_range = max(lat_max - lat_min, 1.0)

    # Create grid
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Plot points
    for point in front.points:
        # Normalize to grid coordinates
        x = int((point.latency_us - lat_min) / lat_range * (width - 1))
        y = int((1 - (point.accuracy - acc_min) / acc_range) * (height - 1))

        # Clamp to grid bounds
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))

        # Use different markers for FFT sizes
        if point.config.fft_size <= 1024:
            marker = "o"
        elif point.config.fft_size <= 2048:
            marker = "+"
        elif point.config.fft_size <= 4096:
            marker = "*"
        else:
            marker = "#"

        grid[y][x] = marker

    # Build plot
    lines.append("Accuracy")
    lines.append(f"  {acc_max:.2f} |" + "".join(grid[0]))

    for i in range(1, height - 1):
        if i == height // 2:
            mid_acc = (acc_max + acc_min) / 2
            lines.append(f"  {mid_acc:.2f} |" + "".join(grid[i]))
        else:
            lines.append("       |" + "".join(grid[i]))

    lines.append(f"  {acc_min:.2f} |" + "".join(grid[-1]))
    lines.append("       +" + "-" * width)
    lines.append(
        f"        {lat_min:.0f}" + " " * (width - 10) + f"{lat_max:.0f} µs"
    )
    lines.append(" " * 25 + "Latency")

    # Legend
    lines.append("")
    lines.append("Legend: o=512-1024, +=1024-2048, *=2048-4096, #=4096+")

    return "\n".join(lines)


def generate_pareto_report(analyzer: ParetoAnalyzer) -> str:
    """
    Generate comprehensive Pareto analysis report.

    Args:
        analyzer: Configured ParetoAnalyzer

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("PARETO FRONT ANALYSIS REPORT")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 70)

    for analysis_type, front in analyzer.fronts.items():
        lines.append(f"\n{'─' * 70}")
        lines.append(f"{analysis_type.upper()} ANALYSIS")
        lines.append(f"{'─' * 70}")

        # Summary
        lines.append(f"\nTotal configurations: {front.total_configurations}")
        lines.append(f"Pareto-optimal: {len(front.points)}")
        lines.append(f"Dominated: {front.dominated_count}")

        # Ranges
        lines.append(
            f"\nAccuracy range: {front.accuracy_range[0]:.3f} - {front.accuracy_range[1]:.3f}"
        )
        lines.append(
            f"Latency range: {front.latency_range[0]:.1f} - {front.latency_range[1]:.1f} µs"
        )

        # Knee point
        knee = analyzer.find_knee_point(analysis_type)
        if knee:
            lines.append("\nKnee point (best trade-off):")
            lines.append(
                f"  {knee.config.method} ({knee.config.fft_size}, {knee.config.hop_size})"
            )
            lines.append(
                f"  Accuracy: {knee.accuracy:.3f}, Latency: {knee.latency_us:.1f} µs"
            )

        # ASCII plot
        lines.append("")
        lines.append(generate_ascii_plot(front))

        # Pareto points table
        lines.append("\nPareto-optimal configurations:")
        lines.append(
            f"{'Method':<10} {'FFT':>5} {'Hop':>5} "
            f"{'Accuracy':>8} {'Latency':>10} {'Efficiency':>10}"
        )
        lines.append("-" * 54)

        for point in front.points[:10]:  # Top 10
            lines.append(
                f"{point.config.method:<10} "
                f"{point.config.fft_size:>5} "
                f"{point.config.hop_size:>5} "
                f"{point.accuracy:>8.3f} "
                f"{point.latency_us:>9.1f}µs "
                f"{point.efficiency_ratio:>10.2f}"
            )

        if len(front.points) > 10:
            lines.append(f"  ... and {len(front.points) - 10} more")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def export_pareto_data(
    analyzer: ParetoAnalyzer,
    output_path: str | Path,
) -> Path:
    """
    Export Pareto front data to JSON for external visualization.

    Args:
        analyzer: Configured ParetoAnalyzer
        output_path: Output file path

    Returns:
        Path to saved file
    """
    output_path = Path(output_path)

    data = {
        "timestamp": datetime.now().isoformat(),
        "analysis_types": {},
    }

    for analysis_type, front in analyzer.fronts.items():
        front_data = {
            "total_configurations": front.total_configurations,
            "pareto_optimal_count": len(front.points),
            "dominated_count": front.dominated_count,
            "accuracy_range": front.accuracy_range,
            "latency_range": front.latency_range,
            "points": [
                {
                    "method": p.config.method,
                    "fft_size": p.config.fft_size,
                    "hop_size": p.config.hop_size,
                    "accuracy": p.accuracy,
                    "latency_us": p.latency_us,
                    "cpu_estimate": p.cpu_estimate,
                    "efficiency_ratio": p.efficiency_ratio,
                    "marginal_latency_per_accuracy": p.marginal_latency_per_accuracy,
                }
                for p in front.points
            ],
        }
        data["analysis_types"][analysis_type] = front_data

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    return output_path


def generate_preset_recommendations(
    analyzer: ParetoAnalyzer,
    current_presets: dict[str, dict[str, tuple[int, int]]],
) -> str:
    """
    Generate recommendations for updating current presets.

    Args:
        analyzer: Configured ParetoAnalyzer
        current_presets: Current preset configurations by preset name and analysis type

    Returns:
        Recommendation report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("PRESET OPTIMIZATION RECOMMENDATIONS")
    lines.append("=" * 70)

    for preset_name, analyses in current_presets.items():
        lines.append(f"\n{preset_name.upper()} PRESET")
        lines.append("-" * 40)

        for analysis_type, (fft_size, hop_size) in analyses.items():
            front = analyzer.fronts.get(analysis_type)
            if not front:
                continue

            # Find current config on Pareto front
            current_on_front = None
            for point in front.points:
                if (
                    point.config.fft_size == fft_size
                    and point.config.hop_size == hop_size
                ):
                    current_on_front = point
                    break

            lines.append(f"\n  {analysis_type}:")
            lines.append(f"    Current: ({fft_size}, {hop_size})")

            if current_on_front:
                lines.append("    Status: ✓ Pareto-optimal")
                lines.append(
                    f"    Metrics: accuracy={current_on_front.accuracy:.3f}, "
                    f"latency={current_on_front.latency_us:.1f}µs"
                )
            else:
                # Find improvement
                target = None
                for point in front.points:
                    if point.latency_us <= (
                        hop_size / 44100 * 1_000_000
                    ):  # Similar latency
                        if target is None or point.accuracy > target.accuracy:
                            target = point

                if target:
                    lines.append("    Status: ✗ Not Pareto-optimal")
                    lines.append(
                        f"    Suggested: ({target.config.fft_size}, {target.config.hop_size})"
                    )
                    lines.append(
                        f"    Improvement: accuracy={target.accuracy:.3f}, "
                        f"latency={target.latency_us:.1f}µs"
                    )
                else:
                    lines.append("    Status: ? Not in sweep results")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)
