# Multi-FFT Audio Analysis Architecture

This document describes LedFx's multi-FFT audio analysis system, which provides independent FFT configurations for different analysis types (tempo tracking, onset detection, pitch detection, and melbank processing).

## Overview

The multi-FFT architecture allows each audio analysis component to use optimal FFT parameters for its specific needs:

- **Onset Detection**: Smaller FFT (512-2048) for low latency transient detection
- **Tempo Tracking**: Medium FFT (1024-4096) for stable beat tracking
- **Pitch Detection**: Larger FFT (2048-8192) for accurate frequency resolution
- **Melbanks**: Tiered FFT sizes based on frequency ranges

## FFT Presets

LedFx provides three built-in presets optimized for different use cases:

### Balanced (Default)

The recommended preset for most users. Provides good accuracy with moderate latency.

| Analysis Type | FFT Size | Hop Size | Latency @ 44.1kHz |
|--------------|----------|----------|-------------------|
| Onset | 1024 | 256 | ~5.8ms |
| Tempo | 2048 | 367 | ~8.3ms |
| Pitch | 4096 | 367 | ~8.3ms |

**Best for**: General music visualization, home use

### Low Latency

Optimized for minimum response time at the cost of some accuracy.

| Analysis Type | FFT Size | Hop Size | Latency @ 44.1kHz |
|--------------|----------|----------|-------------------|
| Onset | 512 | 128 | ~2.9ms |
| Tempo | 1024 | 183 | ~4.1ms |
| Pitch | 2048 | 183 | ~4.1ms |

**Best for**: Live performances, gaming, real-time interaction

### High Precision

Optimized for maximum accuracy with higher computational cost.

| Analysis Type | FFT Size | Hop Size | Latency @ 44.1kHz |
|--------------|----------|----------|-------------------|
| Onset | 2048 | 512 | ~11.6ms |
| Tempo | 4096 | 734 | ~16.6ms |
| Pitch | 8192 | 734 | ~16.6ms |

**Best for**: Studio analysis, professional installations, audiophile setups

## Configuration

### Selecting a Preset

In `config.json` or via the API:

```json
{
  "audio": {
    "fft_preset": "balanced"
  }
}
```

Valid preset values: `"balanced"`, `"low_latency"`, `"high_precision"`

### Custom FFT Overrides

Individual analysis types can be overridden while using a preset:

```json
{
  "audio": {
    "fft_preset": "balanced",
    "fft_onset_override": [1024, 128],
    "fft_tempo_override": [2048, 256],
    "fft_pitch_override": [4096, 512]
  }
}
```

Override format: `[fft_size, hop_size]`

- `fft_size`: Must be a power of 2 (512, 1024, 2048, 4096, 8192, 16384)
- `hop_size`: Must be positive and ≤ fft_size

### Melbank FFT Mode

The melbank FFT sizing can be configured via `melbank_fft_mode`:

- **tiered** (default): Uses preset-defined FFT sizes optimized for different frequency ranges
- **formula**: Calculates FFT size based on max frequency: `2^ceil(log2(max_freq / 10))`

## Technical Architecture

### Resampling Strategy

Each unique hop size gets an independent `samplerate.Resampler` instance:

1. Audio input arrives at the stream sample rate (typically 44100 Hz)
2. Input is resampled once per unique hop size using stateful streaming resamplers
3. Each resampler maintains continuous state across frames for artifact-free audio
4. Resampled audio is shared by all FFTs using that hop size

This approach:
- Avoids zero-padding artifacts
- Enables optimal analysis rates per analysis type
- Minimizes redundant computation through FFT deduplication

### FFT Deduplication

When multiple analysis types share the same FFT configuration (e.g., tempo and pitch both using hop=367 in balanced preset), the FFT is computed once and shared.

### Performance Characteristics

Tested performance on synthetic signals (representative, actual may vary):

| Preset | Mean Frame Time | P95 Frame Time | Memory Estimate |
|--------|-----------------|----------------|-----------------|
| balanced | ~23 µs | ~30 µs | ~144 KB |
| low_latency | ~13 µs | ~17 µs | ~72 KB |
| high_precision | ~47 µs | ~60 µs | ~288 KB |

At 120 FPS analysis rate, frame budget is ~8.3ms. All presets use <1% of frame budget for FFT computation.

## Aubio Analysis Methods

### Onset Detection Methods

Available via `onset_method` configuration:

| Method | Description | Best For |
|--------|-------------|----------|
| `hfc` (default) | High Frequency Content | Percussive/drum sounds |
| `energy` | Energy-based detection | Simple, fast detection |
| `complex` | Complex domain detection | General purpose |
| `phase` | Phase-based detection | Complex signals |
| `wphase` | Weighted phase | Polyphonic content |
| `specdiff` | Spectral difference | Tonal changes |
| `kl` | Kullback-Leibler divergence | Theoretical best |
| `mkl` | Modified KL | Variant of KL |
| `specflux` | Spectral flux | Tonal onsets |

**Recommendation**: `hfc` for most use cases. Consider `energy` for maximum speed.

### Pitch Detection Methods

Available via `pitch_method` configuration:

| Method | Description | Best For |
|--------|-------------|----------|
| `yinfft` (default) | FFT-optimized YIN | Best balance of accuracy/speed |
| `yin` | Original YIN algorithm | Slightly more accurate |
| `yinfast` | Fast YIN approximation | Speed-critical applications |
| `specacf` | Spectral autocorrelation | Harmonic signals |
| `schmitt` | Schmitt trigger | Very fast, less accurate |

**Recommendation**: `yinfft` for most use cases. `yinfast` if pitch accuracy is not critical.

### Tempo Detection

The tempo tracker uses aubio's default algorithm with these enhancements enabled:

- Multi-octave autocorrelation
- Onset enhancement
- FFT-based autocorrelation
- Dynamic tempo tracking
- Adaptive window length
- Tempogram analysis

## Beat Lock System

LedFx implements a beat lock mechanism for stable tempo visualization:

1. **Lock Achievement**: Requires 4 consecutive beats with <15% deviation and minimum confidence
2. **Grace Period**: 2-second protection after lock before unlock conditions are evaluated
3. **Unlock Conditions**: 
   - Low confidence AND high drift (>5%)
   - Very high drift alone (>20%)
   - Missed beats for >4 beat periods
4. **Octave Error Correction**: Automatic compensation for double/half tempo detection

## Validation Test Results

The multi-FFT system has been validated through comprehensive testing with synthetic and realistic audio signals.

### Test Coverage

- **Milestone 1**: Signal generation framework and ground truth schema
- **Milestone 2**: Preset validation across all analysis types (39+ tests)
- **Milestone 3**: Parameter sweep optimization (180+ configurations)
- **Milestone 4**: Real-world validation with drum patterns and music-like signals

### Key Findings

1. **All presets validated** for real-world use with 85-90% correlation between synthetic and realistic performance

2. **Onset detection** performs excellently across all presets (>90% F1 score on synthetic, >80% on realistic)

3. **Pitch detection** achieves >98% detection rate on pure tones, 80-90% on harmonic-rich content

4. **Tempo detection** works best on music-like signals with sustained tonal content; synthetic click tracks show lower accuracy (expected behavior)

5. **Performance scales linearly** with FFT size as expected

### Validated Configurations

| Preset | Tempo | Onset | Pitch | Overall |
|--------|-------|-------|-------|---------|
| balanced | ✓ | ✓ | ✓ | Recommended |
| low_latency | ✓ | ✓ | ✓ | Good for live use |
| high_precision | ✓ | ✓ | ✓ | Best accuracy |

## Dev Mode Profiling

When `dev_mode: true` is enabled:

1. Per-FFT timing is collected with microsecond precision
2. Rolling 120-frame statistics are calculated
3. Every 120 frames (~1 second), performance is logged:

```
FFT performance (last 120 frames):
  (1024,256): mean=5.2µs p95=6.8µs max=12.1µs shared_by=[onset]
  (2048,367): mean=8.7µs p95=11.2µs max=15.3µs shared_by=[tempo,pitch]
  Total: 0.014ms (0.17% of 8.33ms frame budget at 120 FPS)
```

## Troubleshooting

### Tempo Not Locking

- Ensure audio contains clear rhythmic content (not just clicks)
- Try the `high_precision` preset for difficult sources
- Check volume is above `min_volume` threshold

### High Latency Effects

- Switch to `low_latency` preset
- Reduce `fft_onset_override` hop size
- Ensure system CPU is not overloaded

### Inaccurate Pitch Detection

- Use `high_precision` preset for low-frequency content
- Ensure single-note/monophonic content (polyphonic detection is limited)
- Check audio input quality and levels

## API Reference

### AudioAnalysisSource Configuration

```python
AUDIO_CONFIG_SCHEMA = vol.Schema({
    vol.Optional("analysis_fps", default=120): int,
    vol.Optional("input_sample_rate", default=44100): int,
    vol.Optional("min_volume", default=0.2): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
    vol.Optional("fft_preset", default="balanced"): vol.In(["balanced", "low_latency", "high_precision"]),
    vol.Optional("fft_tempo_override"): [int, int],
    vol.Optional("fft_onset_override"): [int, int],
    vol.Optional("fft_pitch_override"): [int, int],
    vol.Optional("melbank_fft_mode", default="tiered"): vol.In(["tiered", "formula"]),
})
```

### Analysis Method Configuration

```python
CONFIG_SCHEMA = vol.Schema({
    vol.Optional("pitch_method", default="yinfft"): vol.In(PITCH_METHODS),
    vol.Optional("tempo_method", default="default"): str,
    vol.Optional("onset_method", default="hfc"): vol.In(ONSET_METHODS),
    vol.Optional("pitch_tolerance", default=0.8): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2)),
})
```

## Further Reading

- [Aubio Documentation](https://aubio.org/doc/latest/)
- [LedFx Audio Effects](../effects/index_effects)
- [Directing Audio to LedFx](../directing_audio)
