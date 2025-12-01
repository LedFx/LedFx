# Multi-FFT Audio Analysis Testing and Optimization Plan

## Overview

This document outlines a comprehensive testing and optimization strategy for LedFx's multi-FFT audio analysis architecture. The plan leverages synthetic audio generation with ground truth data to systematically validate and optimize aubio analysis parameters across tempo tracking, onset detection, pitch detection, and melbank processing.

## Current Implementation Analysis

### Multi-FFT Architecture

The system implements independent FFT configurations for different analysis types:

**FFT Presets:**
- **balanced** (default): onset(1024,256), tempo(2048,367), pitch(4096,367)
- **low_latency**: onset(512,128), tempo(1024,183), pitch(2048,183)
- **high_precision**: onset(2048,512), tempo(4096,734), pitch(8192,734)

**Key Architectural Features:**
- Independent resamplers per unique hop size with continuous state
- FFT deduplication to avoid redundant computation
- Fresh FFT computation each frame (no cross-frame caching)
- Tiered melbank FFT sizing based on frequency ranges
- Dev-mode profiling with µs-level timing

### Aubio Components & Current Parameters

#### Tempo Tracking (`aubio.tempo`)
- **Method**: `"default"` (configurable)
- **FFT Config**: (2048, 367) in balanced preset
- **Enabled Features**:
  - Multi-octave autocorrelation
  - Onset enhancement
  - FFT-based autocorrelation
  - Dynamic tempo tracking
  - Adaptive window length
  - Tempogram (single scale)
- **Beat Lock System**: 4-beat stability tracking with 15% deviation tolerance

#### Onset Detection (`aubio.onset`)
- **Method**: `"hfc"` (High Frequency Content)
- **FFT Config**: (1024, 256) in balanced preset
- **Available Methods**: energy, hfc, complex, phase, wphase, specdiff, kl, mkl, specflux

#### Pitch Detection (`aubio.pitch`)
- **Method**: `"yinfft"` (FFT-optimized YIN)
- **FFT Config**: (4096, 367) in balanced preset
- **Unit**: MIDI note numbers
- **Tolerance**: 0.8 (range: 0.0-2.0)
- **Available Methods**: yinfft, yin, yinfast, schmitt, specacf

#### Resampling
- **Algorithm**: `"sinc_fastest"`
- **Strategy**: Independent resampler per unique hop size
- **Tolerance**: 5% variance in output length

## Aubio Best Practices & Optimization Guidelines

### FFT Size Selection

**General Principles:**
- **Frequency Resolution**: Δf = sample_rate / fft_size
  - Larger FFT → better frequency resolution, worse time resolution
  - Smaller FFT → better time resolution, worse frequency resolution

**Optimal Ranges by Analysis Type:**

1. **Onset Detection**:
   - Target: 512-2048 samples
   - Rationale: Transients are brief (1-10ms), need fast response
   - Trade-off: Smaller FFT for lower latency vs accuracy
   - Recommended: 1024 @ 44.1kHz = ~23ms window, ~5.8ms latency @ hop=256

2. **Tempo Tracking**:
   - Target: 2048-4096 samples
   - Rationale: Beat periods span 200-1000ms, need stable frequency view
   - Trade-off: Larger FFT for stability vs latency
   - Recommended: 2048 @ 44.1kHz = ~46ms window, good for 60-180 BPM

3. **Pitch Detection**:
   - Target: 2048-8192 samples
   - Rationale: Low frequencies need high resolution (20Hz-4kHz range)
   - For A0 (27.5Hz): Need Δf < 13.75Hz → FFT ≥ 3204 @ 44.1kHz
   - Recommended: 4096 @ 44.1kHz = ~93ms window, Δf = 10.77Hz

### Hop Size Selection

**General Formula**: hop = sample_rate / desired_fps

**Optimal Ranges:**
- **Low Latency**: hop = fft_size / 4 (75% overlap)
- **Balanced**: hop = fft_size / 3 to fft_size / 2 (50-66% overlap)
- **High Efficiency**: hop = fft_size / 2 (50% overlap)

**Current Implementation Analysis**:
- Balanced preset: 256-367 samples @ 44.1kHz = 120-171 FPS
- Low latency preset: 128-183 samples = 241-345 FPS
- High precision preset: 512-734 samples = 60-86 FPS

### Method-Specific Recommendations

#### Onset Methods (ranked by general effectiveness):
1. **complex**: Best overall, combines phase and magnitude
2. **hfc**: Good for percussive/high-frequency onsets (current default)
3. **specflux**: Good for tonal onsets
4. **phase**/**wphase**: Good for complex signals
5. **energy**: Simple but less accurate
6. **kl**/**mkl**: Computationally expensive, theoretical best

#### Pitch Methods (ranked for musical applications):
1. **yinfft**: Best balance of accuracy and speed (current default)
2. **yin**: Slightly more accurate but slower
3. **yinfast**: Faster approximation, less accurate
4. **specacf**: Good for harmonic signals
5. **schmitt**: Fast but crude, not recommended for music

#### Tempo Method:
- **default**: Aubio's optimized algorithm, generally best
- Alternative: Can test specific beat tracking algorithms if exposed

### Resampling Quality Tradeoffs

**libsamplerate converters** (current: `"sinc_fastest"`):
- **sinc_best**: SRC_SINC_BEST_QUALITY - Highest quality, slowest (~97dB SNR)
- **sinc_medium**: SRC_SINC_MEDIUM_QUALITY - Good balance (~97dB SNR)
- **sinc_fastest**: SRC_SINC_FASTEST - Fast, good quality (~97dB SNR) ✓ CURRENT
- **zero_order_hold**: SRC_ZERO_ORDER_HOLD - Lowest quality, fastest
- **linear**: SRC_LINEAR - Basic linear interpolation

**Recommendation**: Test sinc_medium vs sinc_fastest to validate if quality improvement justifies performance cost.

## Testing Framework Architecture

### Phase 1: Synthetic Signal Generation

**Goal**: Create deterministic audio signals with known ground truth for quantitative validation.

#### Signal Types

1. **Tempo/Beat Signals**:
   ```python
   # Click track with precise tempo
   - BPM range: 60, 80, 100, 120, 140, 160, 180 BPM
   - Duration: 30 seconds each
   - Click characteristics: 10ms impulse, full-scale amplitude
   - Ground truth: Beat timestamps with 0.1ms precision
   ```

2. **Onset Signals**:
   ```python
   # Various attack transients
   - Impulse: delta function, instant attack
   - Sharp: 1ms attack time
   - Medium: 10ms attack time
   - Slow: 50ms attack time
   - Mixed: Random combination every 500ms
   - Ground truth: Onset timestamps, attack time
   ```

3. **Pitch Signals**:
   ```python
   # Pure tones across musical range
   - MIDI notes: 21 (A0) to 108 (C8), chromatic scale
   - Duration: 1 second per note
   - Waveforms: sine, triangle, sawtooth, square
   - Vibrato: ±50 cents, 5Hz rate (optional)
   - Ground truth: MIDI note number, frequency in Hz
   ```

4. **Complex Signals**:
   ```python
   # Musical realism tests
   - Chord progressions: Major, minor, 7th chords
   - Tempo changes: Linear ramp 60→180 BPM over 60s
   - Polyphonic: Multiple simultaneous pitches
   - Noise: SNR 20dB, 10dB, 0dB overlays
   - Ground truth: Multi-dimensional annotations
   ```

#### Ground Truth Format (JSON)

```json
{
  "signal_type": "tempo",
  "metadata": {
    "bpm": 120,
    "sample_rate": 44100,
    "duration": 30.0,
    "description": "Click track at 120 BPM"
  },
  "ground_truth": {
    "beats": [
      {"time": 0.500, "beat_number": 1, "bar": 1},
      {"time": 1.000, "beat_number": 2, "bar": 1},
      {"time": 1.500, "beat_number": 3, "bar": 1},
      {"time": 2.000, "beat_number": 4, "bar": 1}
    ]
  },
  "test_criteria": {
    "tempo_tolerance_bpm": 2.0,
    "beat_timing_tolerance_ms": 50.0,
    "min_detection_rate": 0.95
  }
}
```

### Phase 2: Preset Validation Tests

**Goal**: Validate that current presets perform as expected across use cases.

#### Test Suite Structure

```python
tests/test_multifft/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── test_signal_generation.py     # Validate synthetic signals
├── test_preset_validation.py     # Test all presets
├── test_tempo_tracking.py        # Tempo-specific tests
├── test_onset_detection.py       # Onset-specific tests
├── test_pitch_detection.py       # Pitch-specific tests
├── test_resampling.py            # Resampler accuracy tests
├── test_fft_deduplication.py     # Performance optimization tests
└── signals/                       # Generated test signals
    ├── tempo/
    ├── onset/
    ├── pitch/
    └── complex/
```

#### Metrics to Collect

**Accuracy Metrics:**
- **Tempo**: BPM error (absolute, %), beat detection F1 score, lock time
- **Onset**: Precision, recall, F1, timing error (mean, std dev)
- **Pitch**: MIDI error (cents), detection rate, octave errors
- **Overall**: False positive rate, false negative rate

**Latency Metrics:**
- Frame processing time (mean, p95, p99)
- FFT computation time per config
- Resampling overhead
- Total analysis pipeline latency

**Computational Metrics:**
- CPU usage (%)
- Memory allocation (MB)
- FFT deduplication savings (%)
- Resampler state memory

#### Expected Outcomes by Preset

| Preset | Accuracy | Latency | CPU Usage | Use Case |
|--------|----------|---------|-----------|----------|
| balanced | HIGH | MEDIUM | MEDIUM | Default - general music |
| low_latency | MEDIUM | LOW | LOW | Live performance, gaming |
| high_precision | VERY HIGH | HIGH | HIGH | Studio analysis, recording |

### Phase 3: Parameter Sweep & Optimization

**Goal**: Systematically explore parameter space to find optimal configurations.

#### Sweep Dimensions

**FFT Size Sweep** (powers of 2):
- Onset: [512, 1024, 2048, 4096]
- Tempo: [1024, 2048, 4096, 8192]
- Pitch: [2048, 4096, 8192, 16384]

**Hop Size Sweep** (for each FFT size):
- Ratios: [1/2, 1/3, 1/4, 1/6, 1/8] of FFT size
- Targets: 60, 90, 120, 180, 240 FPS

**Method Comparison**:
- Onset: Test all 9 methods on same signal set
- Pitch: Test all 5 methods on same signal set
- Tempo: Test available methods if configurable

**Resampler Quality**:
- Test sinc_fastest vs sinc_medium vs sinc_best
- Measure accuracy impact vs performance cost

#### Optimization Strategy

1. **Pareto Front Analysis**:
   - Plot accuracy vs latency for all configs
   - Identify Pareto-optimal solutions
   - Eliminate dominated configurations

2. **Multi-Objective Scoring**:
   ```python
   score = w_accuracy * accuracy_score
         - w_latency * latency_penalty
         - w_cpu * cpu_penalty

   # Example weights for balanced preset
   w_accuracy = 0.6
   w_latency = 0.3
   w_cpu = 0.1
   ```

3. **Cross-Validation**:
   - Train on synthetic signals
   - Validate on real music dataset
   - Ensure generalization

### Phase 4: Real-World Validation

**Goal**: Validate synthetic findings against actual music.

#### Test Dataset

**Genre Coverage**:
- Electronic: House, Techno, Drum & Bass (120-180 BPM)
- Rock/Pop: Various artists (80-140 BPM)
- Classical: Orchestral, variable tempo
- Jazz: Syncopated rhythms, complex harmony
- Hip-Hop: Heavy bass, 60-100 BPM

**Annotations**:
- Manual beat annotations (ground truth)
- MIDI transcriptions for pitch
- Onset annotations from expert listeners

**Test Criteria**:
- Tempo lock success rate
- Beat alignment accuracy (within 50ms)
- Pitch detection accuracy on monophonic passages
- Robustness to genre variation

### Phase 5: Melbank-Specific Testing

**Goal**: Validate melbank FFT sizing strategies.

#### Tiered Mode Validation

Test frequency range assignments:
- Bass (20-350Hz): Should use smaller FFT for time resolution
- Mids (350-2000Hz): Medium FFT for balance
- Highs (2000-22050Hz): Larger FFT acceptable (less critical)

#### Formula Mode Validation

Validate formula: `fft_size = 2^ceil(log2(max_freq / 10))`
- Does formula produce sensible FFT sizes?
- Compare accuracy vs tiered mode
- Test edge cases (very low/high frequencies)

#### Melbank Coefficient Types

Test impact of coefficient type on accuracy:
- matt_mel (default)
- triangle
- bark
- mel
- htk
- scott
- scott_mel

## Performance Profiling Infrastructure

### Dev-Mode Instrumentation

**Current Implementation**:
- µs-level timing per FFT config (already implemented)
- 120-frame rolling statistics
- Frame budget percentage calculation

**Enhancements Needed**:
```python
# Add to AudioAnalysisSource
def _collect_performance_metrics(self):
    """Collect comprehensive performance metrics."""
    return {
        "fft_timings": dict(self._fft_timings),
        "resampler_timings": self._measure_resampler_performance(),
        "memory_usage": self._get_memory_usage(),
        "cpu_percentage": self._get_cpu_usage(),
        "fft_dedup_savings": self._calculate_dedup_savings(),
    }
```

### Benchmark Suite

**Standard Benchmarks**:
1. **Cold Start**: Time to first analysis result
2. **Steady State**: Sustained processing rate (frames/sec)
3. **Memory Footprint**: Peak and average memory usage
4. **Cache Performance**: FFT deduplication hit rate

**Regression Testing**:
- Establish baseline metrics for current implementation
- Flag >5% performance regressions
- Celebrate >10% improvements

## Implementation Roadmap

### Milestone 1: Foundation (Week 1) ✅ COMPLETED

**Deliverables**:
- [x] Signal generation framework (`tests/test_multifft/signal_generator.py`)
- [x] Ground truth JSON schema (`tests/test_multifft/ground_truth_schema.py`)
- [x] Basic test harness (`tests/test_multifft/conftest.py`)
- [x] Metric collection utilities (`tests/test_multifft/metrics.py`)

**Success Criteria**:
- ✅ Generate all signal types (tempo, onset, pitch, complex)
- ✅ Load and validate ground truth (JSON schema with voluptuous validation)
- ✅ Run one complete test case (`tests/test_multifft/test_signal_generation.py`)

**Implementation Notes**:
- Signal generator supports all standard tempos (60-180 BPM)
- Four onset attack types: impulse, sharp, medium, slow
- Pitch signals with multiple waveforms (sine, triangle, sawtooth, square)
- Complex signals combine beats + melody + configurable noise (SNR 0-30 dB)
- Metrics module calculates precision, recall, F1 for all analysis types
- Tests verified manually due to main conftest.py requiring LedFx subprocess

### Milestone 2: Preset Validation (Week 2)

**Deliverables**:
- [ ] All preset validation tests
- [ ] Accuracy metrics dashboard
- [ ] Performance profiling integration
- [ ] Initial results report

**Success Criteria**:
- All 3 presets tested on all signal types
- Metrics collected and visualized
- Identify any preset deficiencies

### Milestone 3: Parameter Optimization (Week 3-4)

**Deliverables**:
- [ ] Parameter sweep infrastructure
- [ ] Multi-objective optimization
- [ ] Pareto front visualization
- [ ] Recommended preset updates

**Success Criteria**:
- Complete sweep of FFT/hop combinations
- Identify optimal configurations
- Propose preset improvements with data

### Milestone 4: Real-World Validation (Week 5)

**Deliverables**:
- [ ] Music dataset preparation
- [ ] Real-world test suite
- [ ] Cross-validation results
- [ ] Final recommendations

**Success Criteria**:
- Synthetic findings validated on real music
- No significant accuracy degradation
- Performance targets met

### Milestone 5: Documentation & Integration (Week 6)

**Deliverables**:
- [ ] Update MULTIFFT.md with findings
- [ ] Code documentation
- [ ] User-facing preset descriptions
- [ ] Integration into CI/CD

**Success Criteria**:
- All findings documented
- Tests integrated into test suite
- Presets updated if warranted

## Open Questions & Research Areas

### High Priority

1. **Tempo Feature Optimization**:
   - Which aubio tempo features provide the most value?
   - Can we disable expensive features with minimal accuracy loss?
   - Test combinations systematically

2. **Onset Method Selection**:
   - Is HFC truly optimal for LED visualization?
   - Would `complex` or `specflux` work better for certain music?
   - Create decision tree for method selection

3. **Pitch Tolerance Tuning**:
   - Current 0.8 tolerance - is this optimal?
   - Test range [0.4, 0.6, 0.8, 1.0, 1.2] on pitch accuracy
   - Genre-specific recommendations?

### Medium Priority

4. **Resampler Aliasing**:
   - Measure aliasing artifacts from sinc_fastest
   - Is upgrade to sinc_medium justified?
   - Impact on melbank frequency accuracy?

5. **Beat Lock Tuning**:
   - Optimize stability thresholds (currently 15% deviation)
   - Grace period duration (currently 2.0s)
   - Unlock counter threshold (currently 2 frames)

6. **Melbank FFT Formula**:
   - Validate formula produces sensible results
   - Compare to manually-tuned tiered mode
   - Propose improvements if needed

### Low Priority

7. **Pre-emphasis Filter Optimization**:
   - Current coefficients are melbank-coefficient-type dependent
   - Test if this actually improves results
   - Measure impact on onset/tempo/pitch

8. **Multi-Channel Analysis**:
   - Current: Downmix to mono
   - Future: Stereo analysis for spatial effects?
   - Worth the computational cost?

## Success Metrics

**Testing Framework**:
- ✅ 100% coverage of aubio analysis types
- ✅ >50 unique test signals with ground truth
- ✅ Automated regression testing
- ✅ Performance profiling integrated

**Optimization Results**:
- ✅ Quantitative accuracy improvements demonstrated
- ✅ Latency reductions measured (if applicable)
- ✅ No regression in existing use cases
- ✅ Preset recommendations data-driven

**Documentation**:
- ✅ MULTIFFT.md tracks all findings
- ✅ Code comments explain parameter choices
- ✅ User documentation updated with preset guidance
- ✅ Future maintainers understand design rationale

## Risk Mitigation

**Risk**: Synthetic signals don't represent real music well
- **Mitigation**: Phase 4 real-world validation required
- **Fallback**: Use synthetic for parameter bounds, real music for final tuning

**Risk**: Optimization overfits to test dataset
- **Mitigation**: Cross-validation with held-out music
- **Fallback**: Conservative preset updates, user override capability

**Risk**: Computational cost of exhaustive sweep
- **Mitigation**: Prioritize most impactful dimensions first
- **Fallback**: Sample parameter space strategically

**Risk**: Findings contradict existing user preferences
- **Mitigation**: Preserve current presets, add new optimized presets
- **Fallback**: Make new presets opt-in via config

## Appendix: Aubio API Reference

### Key Methods

**aubio.tempo**:
```python
tempo = aubio.tempo(method, fft_size, hop_size, sample_rate)
tempo.set_threshold(threshold)        # Beat detection threshold
tempo.set_silence(silence_threshold)  # Silence threshold in dB
tempo.set_multi_octave(enable)        # Multi-octave autocorrelation
tempo.set_onset_enhancement(enable)   # Enhance onset detection
tempo.set_fft_autocorr(enable)        # Use FFT for autocorrelation
tempo.set_dynamic_tempo(enable)       # Adapt to tempo changes
tempo.set_adaptive_winlen(enable)     # Adapt window length
tempo.set_use_tempogram(enable)       # Use tempogram analysis
beat = tempo(samples)                 # Returns 1 if beat detected
period = tempo.get_period()           # Beat period in samples
bpm = tempo.get_bpm()                 # Current BPM
confidence = tempo.get_confidence()   # Detection confidence [0-1]
```

**aubio.onset**:
```python
onset = aubio.onset(method, fft_size, hop_size, sample_rate)
onset.set_threshold(threshold)        # Detection threshold
onset.set_silence(silence_threshold)  # Silence threshold in dB
onset.set_minioi_ms(min_interval)     # Minimum inter-onset interval
detected = onset(samples)             # Returns 1 if onset detected
```

**aubio.pitch**:
```python
pitch = aubio.pitch(method, fft_size, hop_size, sample_rate)
pitch.set_unit(unit)                  # "Hz", "midi", "bin", "cent"
pitch.set_tolerance(tolerance)        # Detection tolerance [0-2]
pitch.set_silence(silence_threshold)  # Silence threshold in dB
midi_note = pitch(samples)            # Returns pitch in selected unit
confidence = pitch.get_confidence()   # Detection confidence [0-1]
```

### Performance Characteristics

**Computational Complexity**:
- FFT: O(N log N) where N = fft_size
- Tempo: Additional O(M) for autocorrelation where M = tempo_buffer_size
- Onset: O(N) post-FFT processing
- Pitch: O(N) for YIN, O(N log N) for YINFFT

**Memory Usage** (approximate):
- Phase vocoder: 4 * fft_size bytes (2 complex arrays)
- Tempo: Additional buffers for autocorrelation (~8KB)
- Pitch: YIN difference function buffer (~4KB for 4096 FFT)
- Per instance overhead: ~1-2KB

## Notes & Observations

*This section will be updated as testing progresses with discoveries, anomalies, and insights.*

### Milestone 1 Implementation Notes (2025-12-01)

**Testing Infrastructure Created:**
- `tests/test_multifft/signal_generator.py` - Comprehensive signal generation
- `tests/test_multifft/ground_truth_schema.py` - JSON schema with dataclasses
- `tests/test_multifft/conftest.py` - Pytest fixtures and SignalPlayer utility
- `tests/test_multifft/metrics.py` - Accuracy and performance metrics

**Key Discoveries:**

1. **Test Isolation Challenge**:
   - Main `tests/conftest.py` requires LedFx subprocess with `uv` command
   - Multi-FFT tests can run independently via direct Python execution
   - Consider adding pytest markers to differentiate unit vs integration tests

2. **Signal Generation Verification**:
   - Click tracks generate correct beat count within ±1 beat tolerance
   - Onset signals properly space attacks at configured intervals
   - Chromatic scales correctly map MIDI notes 21-108 to frequencies
   - Noise addition achieves target SNR within ±2dB

3. **Metrics Module Capabilities**:
   - Tempo metrics: BPM error, beat F1, timing error statistics
   - Onset metrics: Precision, recall, F1 with configurable tolerance
   - Pitch metrics: Detection rate, error in cents, octave error tracking
   - All metrics support human-readable report formatting

### Initial Observations

1. **Balanced Preset Rationale**:
   - Onset (1024, 256): 4x overlap, ~5.8ms latency at 44.1kHz
   - Tempo (2048, 367): ~5.6x overlap, ~8.3ms latency
   - Pitch (4096, 367): ~11x overlap, ~8.3ms latency
   - Hop sizes chosen for ~120 FPS target, not classical overlap ratios

2. **FFT Sharing**:
   - Tempo and pitch share hop=367 in balanced preset
   - Enables resampler reuse - good design
   - Onset isolated with hop=256 for low latency

3. **Resampler Strategy**:
   - Independent per hop size is correct approach
   - Stateful streaming avoids discontinuities
   - 5% tolerance may be too tight for some drivers

### Questions for Investigation

- Why 367 samples hop? (44100/120 ≈ 367.5)
- Is FFT-based autocorrelation faster than time-domain for tempo?
- Do all tempo features contribute equally to accuracy?
- Can we predict optimal FFT size from frequency range analytically?

---

**Last Updated**: 2025-12-01
**Status**: Milestone 1 Complete - Foundation implemented
**Next Action**: Begin Milestone 2 - Preset Validation Tests
