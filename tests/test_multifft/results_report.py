"""
Results Report Generator for Multi-FFT Testing

This module provides utilities for generating comprehensive reports
from preset validation tests, including:
- Accuracy metrics dashboard
- Performance profiling summary
- Comparative analysis across presets
- Export to various formats (text, markdown, JSON)

Part of Milestone 2: Accuracy Metrics Dashboard
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from .metrics import (
    AnalysisResult,
    OnsetMetrics,
    PerformanceMetrics,
    PitchMetrics,
    TempoMetrics,
)


@dataclass
class PresetSummary:
    """Summary statistics for a single preset."""

    preset_name: str
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0

    # Tempo statistics
    tempo_tests: int = 0
    tempo_passed: int = 0
    avg_bpm_error: float = 0.0
    avg_beat_recall: float = 0.0
    avg_beat_precision: float = 0.0

    # Onset statistics
    onset_tests: int = 0
    onset_passed: int = 0
    avg_onset_recall: float = 0.0
    avg_onset_precision: float = 0.0
    avg_onset_f1: float = 0.0

    # Pitch statistics
    pitch_tests: int = 0
    pitch_passed: int = 0
    avg_detection_rate: float = 0.0
    avg_error_cents: float = 0.0

    # Performance statistics
    avg_frame_time_us: float = 0.0
    p95_frame_time_us: float = 0.0
    max_frame_time_us: float = 0.0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100


@dataclass
class ValidationReport:
    """Complete validation report for all presets."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    preset_summaries: dict[str, PresetSummary] = field(default_factory=dict)
    raw_results: dict[str, list[AnalysisResult]] = field(default_factory=dict)

    # Overall statistics
    total_tests: int = 0
    total_passed: int = 0
    total_failed: int = 0

    # Best performing preset per category
    best_tempo_preset: str = ""
    best_onset_preset: str = ""
    best_pitch_preset: str = ""
    best_performance_preset: str = ""

    def add_preset_results(
        self, preset_name: str, results: list[AnalysisResult]
    ) -> None:
        """
        Add results from a preset to the report.

        Args:
            preset_name: Name of the preset
            results: List of AnalysisResult objects
        """
        self.raw_results[preset_name] = results

        # Calculate summary statistics
        summary = PresetSummary(preset_name=preset_name)
        summary.total_tests = len(results)
        summary.passed_tests = sum(1 for r in results if r.passed)
        summary.failed_tests = summary.total_tests - summary.passed_tests

        # Collect metrics by type
        tempo_metrics: list[TempoMetrics] = []
        onset_metrics: list[OnsetMetrics] = []
        pitch_metrics: list[PitchMetrics] = []
        perf_metrics: list[PerformanceMetrics] = []

        for result in results:
            if result.tempo_metrics:
                tempo_metrics.append(result.tempo_metrics)
                summary.tempo_tests += 1
                if result.passed:
                    summary.tempo_passed += 1

            if result.onset_metrics:
                onset_metrics.append(result.onset_metrics)
                summary.onset_tests += 1
                if result.passed:
                    summary.onset_passed += 1

            if result.pitch_metrics:
                pitch_metrics.append(result.pitch_metrics)
                summary.pitch_tests += 1
                if result.passed:
                    summary.pitch_passed += 1

            if result.performance_metrics:
                perf_metrics.append(result.performance_metrics)

        # Calculate averages for tempo
        if tempo_metrics:
            summary.avg_bpm_error = float(
                np.mean([m.bpm_error for m in tempo_metrics])
            )
            summary.avg_beat_recall = float(
                np.mean([m.recall for m in tempo_metrics])
            )
            summary.avg_beat_precision = float(
                np.mean([m.precision for m in tempo_metrics])
            )

        # Calculate averages for onset
        if onset_metrics:
            summary.avg_onset_recall = float(
                np.mean([m.recall for m in onset_metrics])
            )
            summary.avg_onset_precision = float(
                np.mean([m.precision for m in onset_metrics])
            )
            summary.avg_onset_f1 = float(
                np.mean([m.f1_score for m in onset_metrics])
            )

        # Calculate averages for pitch
        if pitch_metrics:
            summary.avg_detection_rate = float(
                np.mean([m.detection_rate for m in pitch_metrics])
            )
            summary.avg_error_cents = float(
                np.mean(
                    [
                        abs(m.mean_error_cents)
                        for m in pitch_metrics
                        if m.mean_error_cents != 0
                    ]
                    or [0]
                )
            )

        # Calculate averages for performance
        if perf_metrics:
            summary.avg_frame_time_us = float(
                np.mean(
                    [
                        m.mean_frame_time_us
                        for m in perf_metrics
                        if m.mean_frame_time_us > 0
                    ]
                    or [0]
                )
            )
            summary.p95_frame_time_us = float(
                np.mean(
                    [
                        m.p95_frame_time_us
                        for m in perf_metrics
                        if m.p95_frame_time_us > 0
                    ]
                    or [0]
                )
            )
            summary.max_frame_time_us = float(
                np.max(
                    [
                        m.max_frame_time_us
                        for m in perf_metrics
                        if m.max_frame_time_us > 0
                    ]
                    or [0]
                )
            )

        self.preset_summaries[preset_name] = summary

        # Update totals
        self.total_tests += summary.total_tests
        self.total_passed += summary.passed_tests
        self.total_failed += summary.failed_tests

    def determine_best_presets(self) -> None:
        """Determine the best performing preset for each category."""
        if not self.preset_summaries:
            return

        # Best tempo (lowest BPM error)
        tempo_presets = [
            (name, s.avg_bpm_error)
            for name, s in self.preset_summaries.items()
            if s.tempo_tests > 0
        ]
        if tempo_presets:
            self.best_tempo_preset = min(tempo_presets, key=lambda x: x[1])[0]

        # Best onset (highest F1 score)
        onset_presets = [
            (name, s.avg_onset_f1)
            for name, s in self.preset_summaries.items()
            if s.onset_tests > 0
        ]
        if onset_presets:
            self.best_onset_preset = max(onset_presets, key=lambda x: x[1])[0]

        # Best pitch (highest detection rate)
        pitch_presets = [
            (name, s.avg_detection_rate)
            for name, s in self.preset_summaries.items()
            if s.pitch_tests > 0
        ]
        if pitch_presets:
            self.best_pitch_preset = max(pitch_presets, key=lambda x: x[1])[0]

        # Best performance (lowest average frame time)
        perf_presets = [
            (name, s.avg_frame_time_us)
            for name, s in self.preset_summaries.items()
            if s.avg_frame_time_us > 0
        ]
        if perf_presets:
            self.best_performance_preset = min(
                perf_presets, key=lambda x: x[1]
            )[0]


def generate_text_report(report: ValidationReport) -> str:
    """
    Generate a human-readable text report.

    Args:
        report: ValidationReport to format

    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("MULTI-FFT PRESET VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {report.timestamp}")
    lines.append("")

    # Overall summary
    lines.append("-" * 70)
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 70)
    lines.append(f"Total Tests: {report.total_tests}")
    lines.append(f"Passed: {report.total_passed}")
    lines.append(f"Failed: {report.total_failed}")
    if report.total_tests > 0:
        pass_rate = (report.total_passed / report.total_tests) * 100
        lines.append(f"Pass Rate: {pass_rate:.1f}%")
    lines.append("")

    # Best presets
    lines.append("-" * 70)
    lines.append("BEST PERFORMING PRESETS")
    lines.append("-" * 70)
    lines.append(f"Best Tempo Accuracy: {report.best_tempo_preset or 'N/A'}")
    lines.append(f"Best Onset Detection: {report.best_onset_preset or 'N/A'}")
    lines.append(f"Best Pitch Detection: {report.best_pitch_preset or 'N/A'}")
    lines.append(
        f"Best Performance: {report.best_performance_preset or 'N/A'}"
    )
    lines.append("")

    # Per-preset details
    for preset_name, summary in report.preset_summaries.items():
        lines.append("-" * 70)
        lines.append(f"PRESET: {preset_name.upper()}")
        lines.append("-" * 70)
        lines.append(
            f"Pass Rate: {summary.pass_rate:.1f}% ({summary.passed_tests}/{summary.total_tests})"
        )
        lines.append("")

        # Tempo stats
        if summary.tempo_tests > 0:
            lines.append("  Tempo Detection:")
            lines.append(
                f"    Tests: {summary.tempo_passed}/{summary.tempo_tests} passed"
            )
            lines.append(f"    Avg BPM Error: {summary.avg_bpm_error:.1f}")
            lines.append(f"    Avg Beat Recall: {summary.avg_beat_recall:.2f}")
            lines.append(
                f"    Avg Beat Precision: {summary.avg_beat_precision:.2f}"
            )
            lines.append("")

        # Onset stats
        if summary.onset_tests > 0:
            lines.append("  Onset Detection:")
            lines.append(
                f"    Tests: {summary.onset_passed}/{summary.onset_tests} passed"
            )
            lines.append(f"    Avg Recall: {summary.avg_onset_recall:.2f}")
            lines.append(
                f"    Avg Precision: {summary.avg_onset_precision:.2f}"
            )
            lines.append(f"    Avg F1 Score: {summary.avg_onset_f1:.2f}")
            lines.append("")

        # Pitch stats
        if summary.pitch_tests > 0:
            lines.append("  Pitch Detection:")
            lines.append(
                f"    Tests: {summary.pitch_passed}/{summary.pitch_tests} passed"
            )
            lines.append(
                f"    Avg Detection Rate: {summary.avg_detection_rate:.2f}"
            )
            lines.append(f"    Avg Error: {summary.avg_error_cents:.1f} cents")
            lines.append("")

        # Performance stats
        if summary.avg_frame_time_us > 0:
            lines.append("  Performance:")
            lines.append(
                f"    Avg Frame Time: {summary.avg_frame_time_us:.1f} µs"
            )
            lines.append(
                f"    P95 Frame Time: {summary.p95_frame_time_us:.1f} µs"
            )
            lines.append(
                f"    Max Frame Time: {summary.max_frame_time_us:.1f} µs"
            )
            lines.append("")

    lines.append("=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_markdown_report(report: ValidationReport) -> str:
    """
    Generate a markdown-formatted report.

    Args:
        report: ValidationReport to format

    Returns:
        Markdown formatted report
    """
    lines = []
    lines.append("# Multi-FFT Preset Validation Report")
    lines.append("")
    lines.append(f"**Generated:** {report.timestamp}")
    lines.append("")

    # Overall summary
    lines.append("## Overall Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Tests | {report.total_tests} |")
    lines.append(f"| Passed | {report.total_passed} |")
    lines.append(f"| Failed | {report.total_failed} |")
    if report.total_tests > 0:
        pass_rate = (report.total_passed / report.total_tests) * 100
        lines.append(f"| Pass Rate | {pass_rate:.1f}% |")
    lines.append("")

    # Best presets
    lines.append("## Best Performing Presets")
    lines.append("")
    lines.append("| Category | Best Preset |")
    lines.append("|----------|-------------|")
    lines.append(f"| Tempo Accuracy | {report.best_tempo_preset or 'N/A'} |")
    lines.append(f"| Onset Detection | {report.best_onset_preset or 'N/A'} |")
    lines.append(f"| Pitch Detection | {report.best_pitch_preset or 'N/A'} |")
    lines.append(
        f"| Performance | {report.best_performance_preset or 'N/A'} |"
    )
    lines.append("")

    # Comparison table
    lines.append("## Preset Comparison")
    lines.append("")
    lines.append("### Accuracy Metrics")
    lines.append("")
    lines.append(
        "| Preset | Pass Rate | BPM Error | Beat Recall | Onset F1 | Pitch Rate |"
    )
    lines.append(
        "|--------|-----------|-----------|-------------|----------|------------|"
    )

    for preset_name, summary in report.preset_summaries.items():
        lines.append(
            f"| {preset_name} | {summary.pass_rate:.1f}% | "
            f"{summary.avg_bpm_error:.1f} | {summary.avg_beat_recall:.2f} | "
            f"{summary.avg_onset_f1:.2f} | {summary.avg_detection_rate:.2f} |"
        )
    lines.append("")

    # Performance comparison
    lines.append("### Performance Metrics")
    lines.append("")
    lines.append("| Preset | Avg Time (µs) | P95 Time (µs) | Max Time (µs) |")
    lines.append("|--------|---------------|---------------|---------------|")

    for preset_name, summary in report.preset_summaries.items():
        lines.append(
            f"| {preset_name} | {summary.avg_frame_time_us:.1f} | "
            f"{summary.p95_frame_time_us:.1f} | {summary.max_frame_time_us:.1f} |"
        )
    lines.append("")

    # Per-preset details
    for preset_name, summary in report.preset_summaries.items():
        lines.append(f"## {preset_name.replace('_', ' ').title()} Preset")
        lines.append("")
        lines.append(
            f"**Pass Rate:** {summary.pass_rate:.1f}% ({summary.passed_tests}/{summary.total_tests})"
        )
        lines.append("")

        if summary.tempo_tests > 0:
            lines.append("### Tempo Detection")
            lines.append("")
            lines.append(
                f"- Tests: {summary.tempo_passed}/{summary.tempo_tests} passed"
            )
            lines.append(f"- Average BPM Error: {summary.avg_bpm_error:.1f}")
            lines.append(
                f"- Average Beat Recall: {summary.avg_beat_recall:.2f}"
            )
            lines.append(
                f"- Average Beat Precision: {summary.avg_beat_precision:.2f}"
            )
            lines.append("")

        if summary.onset_tests > 0:
            lines.append("### Onset Detection")
            lines.append("")
            lines.append(
                f"- Tests: {summary.onset_passed}/{summary.onset_tests} passed"
            )
            lines.append(f"- Average Recall: {summary.avg_onset_recall:.2f}")
            lines.append(
                f"- Average Precision: {summary.avg_onset_precision:.2f}"
            )
            lines.append(f"- Average F1 Score: {summary.avg_onset_f1:.2f}")
            lines.append("")

        if summary.pitch_tests > 0:
            lines.append("### Pitch Detection")
            lines.append("")
            lines.append(
                f"- Tests: {summary.pitch_passed}/{summary.pitch_tests} passed"
            )
            lines.append(
                f"- Average Detection Rate: {summary.avg_detection_rate:.2f}"
            )
            lines.append(
                f"- Average Error: {summary.avg_error_cents:.1f} cents"
            )
            lines.append("")

    return "\n".join(lines)


def generate_json_report(report: ValidationReport) -> str:
    """
    Generate a JSON-formatted report.

    Args:
        report: ValidationReport to format

    Returns:
        JSON string
    """
    data = {
        "timestamp": report.timestamp,
        "total_tests": report.total_tests,
        "total_passed": report.total_passed,
        "total_failed": report.total_failed,
        "best_presets": {
            "tempo": report.best_tempo_preset,
            "onset": report.best_onset_preset,
            "pitch": report.best_pitch_preset,
            "performance": report.best_performance_preset,
        },
        "presets": {},
    }

    for preset_name, summary in report.preset_summaries.items():
        data["presets"][preset_name] = {
            "pass_rate": summary.pass_rate,
            "total_tests": summary.total_tests,
            "passed_tests": summary.passed_tests,
            "failed_tests": summary.failed_tests,
            "tempo": {
                "tests": summary.tempo_tests,
                "passed": summary.tempo_passed,
                "avg_bpm_error": summary.avg_bpm_error,
                "avg_beat_recall": summary.avg_beat_recall,
                "avg_beat_precision": summary.avg_beat_precision,
            },
            "onset": {
                "tests": summary.onset_tests,
                "passed": summary.onset_passed,
                "avg_recall": summary.avg_onset_recall,
                "avg_precision": summary.avg_onset_precision,
                "avg_f1": summary.avg_onset_f1,
            },
            "pitch": {
                "tests": summary.pitch_tests,
                "passed": summary.pitch_passed,
                "avg_detection_rate": summary.avg_detection_rate,
                "avg_error_cents": summary.avg_error_cents,
            },
            "performance": {
                "avg_frame_time_us": summary.avg_frame_time_us,
                "p95_frame_time_us": summary.p95_frame_time_us,
                "max_frame_time_us": summary.max_frame_time_us,
            },
        }

    return json.dumps(data, indent=2)


def save_report(
    report: ValidationReport,
    output_dir: str | Path,
    formats: list[str] | None = None,
) -> list[Path]:
    """
    Save report to files in specified formats.

    Args:
        report: ValidationReport to save
        output_dir: Output directory
        formats: List of formats ('text', 'markdown', 'json'). Default: all.

    Returns:
        List of paths to saved files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["text", "markdown", "json"]

    saved_paths = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if "text" in formats:
        text_path = output_dir / f"validation_report_{timestamp}.txt"
        text_path.write_text(generate_text_report(report))
        saved_paths.append(text_path)

    if "markdown" in formats:
        md_path = output_dir / f"validation_report_{timestamp}.md"
        md_path.write_text(generate_markdown_report(report))
        saved_paths.append(md_path)

    if "json" in formats:
        json_path = output_dir / f"validation_report_{timestamp}.json"
        json_path.write_text(generate_json_report(report))
        saved_paths.append(json_path)

    return saved_paths


def print_dashboard(report: ValidationReport) -> None:
    """
    Print a compact dashboard to console.

    Args:
        report: ValidationReport to display
    """
    print("\n" + "=" * 60)
    print("MULTI-FFT VALIDATION DASHBOARD")
    print("=" * 60)

    # Overall status
    if report.total_tests > 0:
        pass_rate = (report.total_passed / report.total_tests) * 100
        status = (
            "✓ PASS"
            if pass_rate >= 80
            else "⚠ WARN" if pass_rate >= 50 else "✗ FAIL"
        )
        print(f"\nStatus: {status} ({pass_rate:.0f}% pass rate)")
    print(f"Tests: {report.total_passed}/{report.total_tests} passed")

    # Preset summary table
    print("\n┌─────────────────┬────────┬──────────┬──────────┬──────────┐")
    print("│ Preset          │  Pass  │  Tempo   │  Onset   │  Pitch   │")
    print("├─────────────────┼────────┼──────────┼──────────┼──────────┤")

    for preset_name, summary in report.preset_summaries.items():
        tempo_str = (
            f"{summary.avg_bpm_error:.1f}err"
            if summary.tempo_tests > 0
            else "N/A"
        )
        onset_str = (
            f"{summary.avg_onset_f1:.2f}F1"
            if summary.onset_tests > 0
            else "N/A"
        )
        pitch_str = (
            f"{summary.avg_detection_rate:.2f}det"
            if summary.pitch_tests > 0
            else "N/A"
        )
        print(
            f"│ {preset_name:15s} │ {summary.pass_rate:5.1f}% │ {tempo_str:8s} │ "
            f"{onset_str:8s} │ {pitch_str:8s} │"
        )

    print("└─────────────────┴────────┴──────────┴──────────┴──────────┘")

    # Best presets
    print("\nBest Presets:")
    if report.best_tempo_preset:
        print(f"  Tempo: {report.best_tempo_preset}")
    if report.best_onset_preset:
        print(f"  Onset: {report.best_onset_preset}")
    if report.best_pitch_preset:
        print(f"  Pitch: {report.best_pitch_preset}")
    if report.best_performance_preset:
        print(f"  Performance: {report.best_performance_preset}")

    print("\n" + "=" * 60)
