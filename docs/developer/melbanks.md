# Melbanks Architecture

## Overview

Melbanks are the core audio processing component in LedFx that transform audio frequency data into a format optimized for LED visualizations. They convert FFT (Fast Fourier Transform) frequency domain data into perceptually-weighted frequency bins that better match human audio perception and create more responsive LED effects.

## What are Melbanks?

A melbank (mel-frequency filterbank) is a bank of triangular filters spaced according to the mel scale - a perceptual scale of pitches that approximates human hearing. Unlike linear frequency spacing, the mel scale uses narrower bands at low frequencies (where human hearing is more sensitive) and wider bands at high frequencies.

**Key Benefit**: This perceptual weighting makes LED effects more responsive to bass frequencies and musical elements that humans naturally focus on, rather than giving equal weight to all frequencies.

## Architecture

LedFx uses a multi-resolution melbank system with two main classes:

### `Melbank` Class (Single Melbank)
- Represents a single filterbank covering a specific frequency range
- Configurable min/max frequency bounds
- Multiple coefficient types for different weighting curves
- Built-in filtering and peak isolation for smoother visual response

### `Melbanks` Class (Multiple Melbanks)
- Manages a collection of melbanks at different resolutions
- Default configuration creates 3 cumulative melbanks (all sharing the same 20Hz minimum frequency):
  - **Low**: 20Hz - 350Hz (bass/sub-bass focused)
  - **Mid**: 20Hz - 2000Hz (bass through midrange coverage)
  - **High**: 20Hz - 15000Hz (full spectrum coverage)
- Each melbank provides a different resolution view of the same frequency space
- Shared melbank instances across all virtuals for performance
- Single configuration affects all instances

## Core Constants

```
FFT_SIZE = 4096      # FFT window size
MIC_RATE = 30000     # Effective sample rate (Hz)
MAX_FREQ = 15000     # Maximum frequency (MIC_RATE / 2)
MIN_FREQ = 20        # Minimum frequency (Hz)
MEL_MAX_FREQS = [350, 2000, MAX_FREQ]  # Default melbank boundaries
```

**Why 30000Hz sample rate?**
While microphones may capture at ~40000Hz, LedFx processes audio at 30000Hz to:
- Increase frequency resolution for bass (where Hz differences are smaller)
- Focus processing power on the audible range humans care about

**Why FFT_SIZE = 4096?**
Larger FFT window provides:
- Better frequency resolution: ~7.3Hz per bin (30000 / 4096)
- Critical for distinguishing bass notes (e.g., 40Hz vs 50Hz)
- Trade-off: Slightly higher latency (~137ms window)

## Frequency Bins per Melbank

Based on the default configuration (`samples=24`, `coeffs_type="matt_mel"`), each melbank creates **24 frequency bins**. The actual frequencies covered by each bin depend on:

1. **Coefficient type** - Different mel-scale curves (matt_mel, scott_mel, htk, etc.)
2. **Min/max frequency** - The range covered by that melbank
3. **Number of samples** - How many bins to divide the range into

### Standard Bin Distribution (Default Config: 20Hz - 15000Hz)

The following table shows the actual frequency bins for a full-range melbank using the default **matt_mel** configuration (24 samples, 20Hz-15000Hz):

| Bin | Min Hz  | Center Hz | Max Hz   | Approx Range Description |
|-----|---------|-----------|----------|--------------------------|
| 0   | 20      | 64        | 91       | Sub-bass |
| 1   | 91      | 117       | 148      | Bass fundamentals |
| 2   | 148     | 179       | 216      | Bass |
| 3   | 216     | 252       | 295      | Low bass |
| 4   | 295     | 338       | 389      | Bass/kick drum |
| 5   | 389     | 440       | 500      | Lower midrange |
| 6   | 500     | 560       | 631      | Midrange |
| 7   | 631     | 701       | 784      | Midrange |
| 8   | 784     | 867       | 965      | Upper midrange |
| 9   | 965     | 1063      | 1179     | Upper midrange |
| 10  | 1179    | 1294      | 1431     | Presence |
| 11  | 1431    | 1567      | 1728     | Presence |
| 12  | 1728    | 1888      | 2077     | Presence/sibilance |
| 13  | 2077    | 2266      | 2490     | Brilliance |
| 14  | 2490    | 2713      | 2976     | Brilliance |
| 15  | 2976    | 3238      | 3548     | High frequency |
| 16  | 3548    | 3858      | 4224     | High frequency |
| 17  | 4224    | 4589      | 5020     | High frequency |
| 18  | 5020    | 5450      | 5957     | Very high frequency |
| 19  | 5957    | 6464      | 7063     | Very high frequency |
| 20  | 7063    | 7661      | 8366     | Ultra high |
| 21  | 8366    | 9070      | 9901     | Ultra high |
| 22  | 9901    | 10732     | 11712    | Ultra high/air |
| 23  | 11712   | 12691     | 15000    | Air/sparkle |

**Key observations:**
- Bins are **not evenly spaced** - they follow the mel-scale perceptual curve
- Lower bins are narrower (20-150Hz range) for better bass resolution
- Higher bins are wider (3000-4000Hz range) matching human hearing sensitivity
- The widest bin (23) covers nearly 3300Hz of range at the top end
- The narrowest bins (0-2) each cover ~50-70Hz for precise bass tracking

### Bin Distribution for Individual Melbanks

The default LedFx configuration creates 3 cumulative melbanks at different resolutions, all sharing the same minimum frequency (20Hz) but with different maximum frequencies:

**Melbank 0 (Low: 20Hz - 350Hz)** - 24 bins focused on bass
- Covers sub-bass, bass, and low midrange
- Very fine resolution: ~10-20Hz per bin
- Critical for kick drums, bass lines, sub frequencies
- Narrowest frequency range for maximum bass detail

**Melbank 1 (Mid: 20Hz - 2000Hz)** - 24 bins for bass through midrange  
- Covers all of melbank 0 PLUS vocals, guitars, snares, melodic content
- Moderate resolution: broader bins than melbank 0
- Cumulative coverage from bass through midrange
- Useful for effects needing both bass and midrange response

**Melbank 2 (High: 20Hz - 15000Hz)** - 24 bins for full spectrum
- Covers all of melbanks 0 and 1 PLUS cymbals, hi-hats, brilliance, air
- Coarsest resolution: widest bins spanning the entire audible range
- Full spectrum coverage from sub-bass to high frequencies
- Effects use this when they need the complete frequency picture

> **Note**: Because melbanks are cumulative (all start at 20Hz), they provide nested views of the same audio data at different resolutions. Melbank 0 gives fine detail on bass, melbank 1 gives moderate detail across bass and mids, and melbank 2 gives coarse detail across the full spectrum. Effects automatically select the most appropriate melbank based on their configured frequency range.

## Coefficient Types

LedFx supports multiple mel-scale algorithms, each with different frequency weighting:

| Type | Description | Bass Response | High Response | Use Case |
|------|-------------|---------------|---------------|----------|
| `matt_mel` | **Default**. Modified scott_mel optimized for LedFx | Excellent | Good | General purpose, best all-around |
| `mel` | Standard mel scale | Good | Good | Traditional audio analysis |
| `htk` | HTK (Hidden Markov Model Toolkit) mel | Weak | Weak | Not recommended |
| `scott_mel` | Scott's audio reactive LED algorithm | Good | Weak | Bass-focused effects |
| `scott` | Scott's algorithm with different weighting | Good | Moderate | Alternative bass focus |
| `triangle` | Simple triangular filters | Moderate | Moderate | Simple/experimental |
| `bark` | Bark scale (alternative perceptual scale) | Good | Good | Experimental |

**Why matt_mel is default**: It provides the best balance of bass responsiveness and high-frequency detail for LED visualizations.

## How Effects Access Melbanks

Effects that inherit from `AudioReactiveEffect` can access melbank data through the `melbank()` method:

```
# Get melbank data for the effect's configured frequency range
melbank_data = self.melbank(filtered=False, size=self.pixel_count)

# filtered=True: Use smoothed attack/decay filtering
# size: Interpolate to match pixel count
```

### Automatic Melbank Selection

Effects don't manually select melbanks. The system automatically:
1. Checks the virtual's configured frequency range (min/max)
2. Selects the smallest melbank that covers that range
3. Extracts only the relevant frequency bins
4. Optionally interpolates to match pixel count

**Example**:
- Virtual configured for 100Hz - 1000Hz
- System selects melbank 1 (20Hz - 2000Hz) - the smallest melbank covering the requested range
- Extracts bins covering 100Hz - 1000Hz
- Interpolates to effect's pixel count

### Cached Properties

For performance, melbank selection uses cached properties:
- `_selected_melbank` - Which melbank index to use
- `_melbank_min_idx` - First bin index in frequency range
- `_melbank_max_idx` - Last bin index in frequency range
- `_input_mel_length` - Number of bins in range

**Important**: When virtual frequency range changes, call `clear_melbank_freq_props()` to invalidate caches.

## Performance Considerations

### Why Shared Melbanks?

All virtuals share the same melbank instances to:
- **Avoid redundant processing**: Audio is analyzed once, used by all effects
- **Prevent performance degradation**: Many virtuals don't multiply CPU load
- **Ensure consistency**: All effects see the same audio analysis

### Memory Layout

Melbank data is stored in NumPy arrays for fast access:
```
self.melbanks = tuple(
    np.zeros(self.mel_len) for _ in range(self.mel_count)
)
self.melbanks_filtered = tuple(
    np.zeros(self.mel_len) for _ in range(self.mel_count)
)
```

Direct tuple access avoids dictionary overhead for real-time processing.

## When Do Melbank Bins Change?

Melbank frequency bins are **static after initialization** and only change when:

1. **Global melbank configuration changes**:
   - `samples` (number of bins)
   - `coeffs_type` (mel scale algorithm)
   - `max_frequencies` (melbank boundaries)
   - `min_frequency` (global minimum)

2. **LedFx restarts** with a different configuration

Melbank bins **do NOT change** when:
- Effects are activated/deactivated
- Virtual frequency ranges are modified
- Audio input changes
- Effects are switched

### Likelihood of Change

**Very Low** - Melbank global settings are typically set once during initial configuration and rarely modified. The bins themselves are deterministic based on the configuration and don't adapt dynamically.

The only "dynamic" aspect is which bins an effect uses - effects select different subsets of bins based on their virtual's frequency range.

## Configuration

### Global Melbank Settings

Located in config.json under `"melbanks"`:

```json
{
  "melbanks": {
    "samples": 24,
    "peak_isolation": 0.4,
    "coeffs_type": "matt_mel",
    "max_frequencies": [350, 2000, 15000],
    "min_frequency": 20
  }
}
```

### Individual Melbank Settings

Individual melbanks can have custom min/max frequencies while inheriting global settings for samples, peak_isolation, and coeffs_type.

## Advanced Topics

### Peak Isolation

`peak_isolation` (default: 0.4) applies non-linear power scaling to emphasize peaks:
- 0.0 = Linear response (no isolation)
- 0.4 = Balanced (default)
- 1.0 = Maximum isolation (infinite power)

Higher values make bright regions brighter and dim regions dimmer, creating more "punchy" visuals.

### Filtering

Each melbank has built-in exponential filters for smoothing:
- `mel_gain`: Automatic gain control (AGC)
- `mel_smoothing`: Temporal smoothing
- `common_filter`: Common mode filtering
- `diff_filter`: Difference filtering

Effects can choose between raw (`filtered=False`) or smoothed (`filtered=True`) melbank data.

## Related Files

- **Implementation**: `ledfx/effects/melbank.py`
- **Mel scale math**: `ledfx/effects/mel.py`
- **Audio effects base**: `ledfx/effects/audio.py`
- **Virtual integration**: `ledfx/virtuals.py`

## Summary

Melbanks transform raw audio FFT data into perceptually-weighted frequency bins optimized for LED visualizations. The multi-resolution system provides both fine detail for bass and broad coverage for full-spectrum effects, while shared instances ensure performance remains consistent regardless of the number of active virtuals.
