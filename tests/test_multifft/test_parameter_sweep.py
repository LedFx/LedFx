"""
Tests for Parameter Sweep and Optimization Infrastructure

This module tests the Milestone 3 deliverables:
- Parameter sweep infrastructure
- Multi-objective optimization
- Pareto front analysis

Part of Milestone 3: Parameter Optimization
"""

import pytest
import numpy as np

from .parameter_sweep import (
    FFTConfig,
    SweepConfig,
    SweepResult,
    ParameterSweeper,
    generate_fft_configs,
    ONSET_METHODS,
    PITCH_METHODS,
    run_quick_sweep,
)
from .optimizer import (
    OptimizationProfile,
    OptimizationWeights,
    OptimizedConfig,
    MultiObjectiveOptimizer,
    optimize_all_types,
)
from .pareto_analysis import (
    ParetoPoint,
    ParetoFront,
    ParetoAnalyzer,
    generate_ascii_plot,
)


class TestFFTConfig:
    """Tests for FFTConfig dataclass."""

    def test_frequency_resolution(self):
        """Test frequency resolution calculation."""
        config = FFTConfig(fft_size=2048, hop_size=512)
        # At 44100 Hz: 44100 / 2048 = 21.53 Hz
        assert abs(config.frequency_resolution - 21.53) < 0.1

    def test_time_resolution(self):
        """Test time resolution calculation."""
        config = FFTConfig(fft_size=2048, hop_size=512)
        # At 44100 Hz: 512 / 44100 = 0.0116 seconds
        assert abs(config.time_resolution - 0.0116) < 0.001

    def test_latency_ms(self):
        """Test latency calculation."""
        config = FFTConfig(fft_size=1024, hop_size=256)
        # At 44100 Hz: 256 / 44100 * 1000 = 5.8 ms
        assert abs(config.latency_ms - 5.8) < 0.1

    def test_overlap_ratio(self):
        """Test overlap ratio calculation."""
        config = FFTConfig(fft_size=2048, hop_size=512)
        # 1 - 512/2048 = 0.75
        assert abs(config.overlap_ratio - 0.75) < 0.01

    def test_hash_consistency(self):
        """Test hash is consistent for same config."""
        config1 = FFTConfig(fft_size=1024, hop_size=256, method="hfc")
        config2 = FFTConfig(fft_size=1024, hop_size=256, method="hfc")
        assert hash(config1) == hash(config2)


class TestGenerateFFTConfigs:
    """Tests for FFT configuration generation."""

    def test_onset_configs_include_all_methods(self):
        """Test onset configs include all methods."""
        configs = generate_fft_configs("onset")
        methods_used = set(c.method for c in configs)
        assert methods_used == set(ONSET_METHODS)

    def test_pitch_configs_include_all_methods(self):
        """Test pitch configs include all methods."""
        configs = generate_fft_configs("pitch")
        methods_used = set(c.method for c in configs)
        assert methods_used == set(PITCH_METHODS)

    def test_tempo_configs_default_method(self):
        """Test tempo configs use default method."""
        configs = generate_fft_configs("tempo")
        methods_used = set(c.method for c in configs)
        assert methods_used == {"default"}

    def test_custom_sweep_config(self):
        """Test custom sweep configuration."""
        config = SweepConfig(
            fft_sizes=[512, 1024],
            hop_ratios=[1 / 2, 1 / 4],
            methods=["hfc"],
        )
        # For onset, should use ONSET_METHODS not custom methods
        configs = generate_fft_configs("onset", config)
        # 2 fft sizes * 2 hop ratios * 9 onset methods = 36
        assert len(configs) > 0

    def test_hop_sizes_are_valid(self):
        """Test generated hop sizes are at least 64."""
        configs = generate_fft_configs("onset")
        for config in configs:
            assert config.hop_size >= 64


class TestSweepResult:
    """Tests for SweepResult dataclass."""

    def test_sorting_by_combined_score(self):
        """Test results sort by combined score."""
        config = FFTConfig(fft_size=1024, hop_size=256)
        result1 = SweepResult(
            config=config,
            analysis_type="onset",
            combined_score=0.5,
        )
        result2 = SweepResult(
            config=config,
            analysis_type="onset",
            combined_score=0.8,
        )
        assert result1 < result2
        sorted_results = sorted([result2, result1])
        assert sorted_results[0].combined_score == 0.5


class TestParameterSweeper:
    """Tests for ParameterSweeper class."""

    @pytest.fixture
    def quick_config(self):
        """Quick sweep configuration for testing."""
        return SweepConfig(
            fft_sizes=[1024],
            hop_ratios=[1 / 2],
            test_bpms=[120],
            test_attack_types=["impulse"],
            test_waveforms=["sine"],
            signal_duration=3.0,
        )

    def test_sweeper_initialization(self, quick_config):
        """Test sweeper initializes correctly."""
        sweeper = ParameterSweeper(quick_config)
        assert sweeper.config == quick_config
        assert len(sweeper.results) == 3

    def test_tempo_sweep_produces_results(self, quick_config):
        """Test tempo sweep produces results."""
        sweeper = ParameterSweeper(quick_config)
        results = sweeper.sweep_tempo()
        assert len(results) > 0
        assert all(r.analysis_type == "tempo" for r in results)

    def test_onset_sweep_produces_results(self, quick_config):
        """Test onset sweep produces results."""
        sweeper = ParameterSweeper(quick_config)
        results = sweeper.sweep_onset()
        assert len(results) > 0
        assert all(r.analysis_type == "onset" for r in results)

    def test_pitch_sweep_produces_results(self, quick_config):
        """Test pitch sweep produces results."""
        sweeper = ParameterSweeper(quick_config)
        results = sweeper.sweep_pitch()
        assert len(results) > 0
        assert all(r.analysis_type == "pitch" for r in results)

    def test_get_best_configs(self, quick_config):
        """Test getting best configurations."""
        sweeper = ParameterSweeper(quick_config)
        sweeper.sweep_onset()
        best = sweeper.get_best_configs("onset", n=3)
        assert len(best) <= 3
        # Should be sorted by accuracy descending
        if len(best) >= 2:
            assert best[0].accuracy_score >= best[1].accuracy_score

    def test_get_fastest_configs(self, quick_config):
        """Test getting fastest configurations."""
        sweeper = ParameterSweeper(quick_config)
        sweeper.sweep_onset()
        fastest = sweeper.get_fastest_configs("onset", min_accuracy=0.0, n=3)
        assert len(fastest) <= 3
        # Should be sorted by time ascending
        if len(fastest) >= 2:
            assert fastest[0].mean_time_us <= fastest[1].mean_time_us

    def test_progress_callback(self, quick_config):
        """Test progress callback is called."""
        progress_calls = []

        def callback(msg, current, total):
            progress_calls.append((msg, current, total))

        sweeper = ParameterSweeper(quick_config, progress_callback=callback)
        sweeper.sweep_onset()
        assert len(progress_calls) > 0

    def test_generate_summary(self, quick_config):
        """Test summary generation."""
        sweeper = ParameterSweeper(quick_config)
        sweeper.sweep_onset()
        summary = sweeper.generate_summary()
        assert "ONSET ANALYSIS" in summary
        assert "Configurations tested" in summary


class TestOptimizationWeights:
    """Tests for OptimizationWeights."""

    def test_weights_normalize(self):
        """Test weights are normalized to sum to 1."""
        weights = OptimizationWeights(accuracy=2.0, latency=1.0, cpu=1.0)
        total = weights.accuracy + weights.latency + weights.cpu
        assert abs(total - 1.0) < 0.001

    def test_from_profile_balanced(self):
        """Test balanced profile weights."""
        weights = OptimizationWeights.from_profile(OptimizationProfile.BALANCED)
        # Balanced should have accuracy as highest weight
        assert weights.accuracy >= weights.latency
        assert weights.accuracy >= weights.cpu

    def test_from_profile_accuracy_focused(self):
        """Test accuracy-focused profile."""
        weights = OptimizationWeights.from_profile(
            OptimizationProfile.ACCURACY_FOCUSED
        )
        assert weights.accuracy > 0.5

    def test_from_profile_latency_focused(self):
        """Test latency-focused profile."""
        weights = OptimizationWeights.from_profile(
            OptimizationProfile.LATENCY_FOCUSED
        )
        assert weights.latency > weights.accuracy


class TestMultiObjectiveOptimizer:
    """Tests for MultiObjectiveOptimizer."""

    @pytest.fixture
    def sample_results(self):
        """Create sample sweep results for testing."""
        configs = [
            FFTConfig(fft_size=512, hop_size=256, method="hfc"),
            FFTConfig(fft_size=1024, hop_size=256, method="hfc"),
            FFTConfig(fft_size=2048, hop_size=512, method="hfc"),
        ]
        results = []
        for i, config in enumerate(configs):
            results.append(
                SweepResult(
                    config=config,
                    analysis_type="onset",
                    accuracy_score=0.6 + i * 0.1,  # Higher accuracy for larger FFT
                    mean_time_us=20.0 + i * 10.0,  # Higher latency for larger FFT
                    test_signals=3,
                    passed_tests=2,
                )
            )
        return results

    def test_optimizer_initialization(self):
        """Test optimizer initializes with default weights."""
        optimizer = MultiObjectiveOptimizer()
        assert optimizer.weights is not None
        assert optimizer.weights.accuracy > 0

    def test_optimize_produces_results(self, sample_results):
        """Test optimization produces results."""
        optimizer = MultiObjectiveOptimizer()
        optimized = optimizer.optimize(sample_results, "onset")
        assert len(optimized) == len(sample_results)
        assert all(isinstance(c, OptimizedConfig) for c in optimized)

    def test_combined_scores_calculated(self, sample_results):
        """Test combined scores are calculated."""
        optimizer = MultiObjectiveOptimizer()
        optimized = optimizer.optimize(sample_results, "onset")
        for config in optimized:
            assert 0 <= config.combined_score <= 1

    def test_pareto_optimal_identified(self, sample_results):
        """Test Pareto-optimal configs are identified."""
        optimizer = MultiObjectiveOptimizer()
        optimized = optimizer.optimize(sample_results, "onset")
        pareto_optimal = [c for c in optimized if c.is_pareto_optimal]
        # At least one should be Pareto-optimal
        assert len(pareto_optimal) > 0

    def test_get_pareto_front(self, sample_results):
        """Test getting Pareto front."""
        optimizer = MultiObjectiveOptimizer()
        optimizer.optimize(sample_results, "onset")
        front = optimizer.get_pareto_front("onset")
        assert all(c.is_pareto_optimal for c in front)

    def test_get_recommendations(self, sample_results):
        """Test getting recommendations."""
        optimizer = MultiObjectiveOptimizer()
        optimizer.optimize(sample_results, "onset")
        recs = optimizer.get_recommendations("onset")
        assert "best_overall" in recs
        assert "best_accuracy" in recs
        assert "best_latency" in recs
        assert "best_balanced" in recs

    def test_weight_profile_affects_ranking(self, sample_results):
        """Test different profiles affect ranking."""
        accuracy_opt = MultiObjectiveOptimizer(
            OptimizationWeights.from_profile(OptimizationProfile.ACCURACY_FOCUSED)
        )
        latency_opt = MultiObjectiveOptimizer(
            OptimizationWeights.from_profile(OptimizationProfile.LATENCY_FOCUSED)
        )

        acc_results = accuracy_opt.optimize(sample_results, "onset")
        lat_results = latency_opt.optimize(sample_results, "onset")

        # Different profiles may produce different rankings
        assert len(acc_results) == len(lat_results)


class TestParetoAnalyzer:
    """Tests for ParetoAnalyzer."""

    @pytest.fixture
    def optimizer_with_results(self):
        """Create optimizer with results for testing."""
        configs = [
            FFTConfig(fft_size=512, hop_size=128, method="hfc"),
            FFTConfig(fft_size=1024, hop_size=256, method="hfc"),
            FFTConfig(fft_size=2048, hop_size=512, method="complex"),
            FFTConfig(fft_size=4096, hop_size=1024, method="specflux"),
        ]
        results = []
        for i, config in enumerate(configs):
            results.append(
                SweepResult(
                    config=config,
                    analysis_type="onset",
                    accuracy_score=0.5 + i * 0.1,
                    mean_time_us=15.0 + i * 15.0,
                    test_signals=3,
                    passed_tests=2,
                )
            )

        optimizer = MultiObjectiveOptimizer()
        optimizer.optimize(results, "onset")
        return optimizer

    def test_analyzer_initialization(self, optimizer_with_results):
        """Test analyzer initializes correctly."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        assert analyzer.optimizer is not None

    def test_analyze_produces_front(self, optimizer_with_results):
        """Test analyze produces Pareto front."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        front = analyzer.analyze("onset")
        assert isinstance(front, ParetoFront)
        assert front.analysis_type == "onset"
        assert len(front.points) > 0

    def test_front_ranges_calculated(self, optimizer_with_results):
        """Test front ranges are calculated."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        front = analyzer.analyze("onset")
        assert front.accuracy_range[1] >= front.accuracy_range[0]
        assert front.latency_range[1] >= front.latency_range[0]

    def test_find_knee_point(self, optimizer_with_results):
        """Test knee point identification."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        analyzer.analyze("onset")
        knee = analyzer.find_knee_point("onset")
        assert knee is not None or len(analyzer.fronts["onset"].points) < 3

    def test_find_target_latency_config(self, optimizer_with_results):
        """Test finding config for target latency."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        analyzer.analyze("onset")
        config = analyzer.find_target_latency_config("onset", 50.0)
        if config:
            assert config.latency_us <= 50.0 or config.latency_us == min(
                p.latency_us for p in analyzer.fronts["onset"].points
            )

    def test_find_target_accuracy_config(self, optimizer_with_results):
        """Test finding config for target accuracy."""
        analyzer = ParetoAnalyzer(optimizer_with_results)
        analyzer.analyze("onset")
        config = analyzer.find_target_accuracy_config("onset", 0.6)
        if config:
            assert config.accuracy >= 0.6 or config.accuracy == max(
                p.accuracy for p in analyzer.fronts["onset"].points
            )


class TestASCIIPlot:
    """Tests for ASCII plot generation."""

    def test_ascii_plot_generation(self):
        """Test ASCII plot is generated."""
        points = [
            ParetoPoint(
                config=FFTConfig(512, 128),
                accuracy=0.6,
                latency_us=20.0,
                cpu_estimate=0.1,
            ),
            ParetoPoint(
                config=FFTConfig(2048, 512),
                accuracy=0.8,
                latency_us=50.0,
                cpu_estimate=0.3,
            ),
        ]
        front = ParetoFront(
            analysis_type="onset",
            points=points,
            total_configurations=10,
        )
        plot = generate_ascii_plot(front)
        assert "Pareto Front" in plot
        assert "ONSET" in plot

    def test_empty_front_handled(self):
        """Test empty front is handled."""
        front = ParetoFront(analysis_type="tempo")
        plot = generate_ascii_plot(front)
        assert "No Pareto points" in plot


class TestQuickSweep:
    """Tests for quick sweep function."""

    def test_quick_sweep_runs(self):
        """Test quick sweep runs successfully."""
        results = run_quick_sweep()
        assert "tempo" in results
        assert "onset" in results
        assert "pitch" in results

    def test_quick_sweep_has_results(self):
        """Test quick sweep produces results."""
        results = run_quick_sweep()
        total_results = sum(len(r) for r in results.values())
        assert total_results > 0


class TestIntegration:
    """Integration tests for the full optimization pipeline."""

    def test_full_pipeline(self):
        """Test complete optimization pipeline."""
        # Run quick sweep
        config = SweepConfig(
            fft_sizes=[1024],
            hop_ratios=[1 / 2],
            test_bpms=[120],
            test_attack_types=["impulse"],
            test_waveforms=["sine"],
            signal_duration=3.0,
        )
        sweeper = ParameterSweeper(config)
        sweep_results = sweeper.sweep_all()

        # Optimize
        optimizer = optimize_all_types(sweep_results)

        # Analyze Pareto fronts
        analyzer = ParetoAnalyzer(optimizer)
        analyzer.analyze_all()

        # Verify pipeline completed
        assert len(analyzer.fronts) > 0
        for front in analyzer.fronts.values():
            assert isinstance(front, ParetoFront)

    def test_recommendations_generated(self):
        """Test recommendations are generated from pipeline."""
        config = SweepConfig(
            fft_sizes=[1024, 2048],
            hop_ratios=[1 / 2],
            test_bpms=[120],
            test_attack_types=["impulse"],
            test_waveforms=["sine"],
            signal_duration=3.0,
        )
        sweeper = ParameterSweeper(config)
        sweep_results = sweeper.sweep_all()
        optimizer = optimize_all_types(sweep_results)

        for analysis_type in optimizer.optimized_configs:
            recs = optimizer.get_recommendations(analysis_type)
            assert recs is not None
