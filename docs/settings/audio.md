# Audio Settings

The audio settings control how LedFx processes audio input for visualization effects.

## Audio Device

Select the audio input device LedFx will use for visualization. Options include:

- **System Audio Loopback**: Captures all audio playing on your computer (recommended)
- **Microphone**: Uses a physical microphone for audio input
- **Web Audio**: Stream audio from another device over the network

## Analysis Settings

### Analysis FPS

Controls how many audio frames are analyzed per second. Default: 120 FPS

Higher values provide smoother visualizations but use more CPU.

### Minimum Volume

Volume threshold below which audio is considered silence. Default: 0.2 (20%)

Effects will not react to audio below this threshold.

### Audio Delay

Add a delay (in milliseconds) to sync LedFx's output with your audio. Useful for:

- Bluetooth speakers/headphones (typically 50-200ms delay)
- Network audio devices
- Projector/TV audio sync

Range: 0-5000ms

## FFT Preset

The FFT (Fast Fourier Transform) preset controls the trade-off between analysis accuracy and latency.

### Balanced (Default)

The recommended preset for most users.

- **Accuracy**: High
- **Latency**: Medium (~8ms)
- **CPU Usage**: Medium

Best for: General music visualization, home use

### Low Latency

Optimized for minimum response time.

- **Accuracy**: Good
- **Latency**: Low (~4ms)
- **CPU Usage**: Low

Best for: Live performances, gaming, DJ sets, real-time interaction

### High Precision

Optimized for maximum accuracy.

- **Accuracy**: Excellent
- **Latency**: Higher (~17ms)
- **CPU Usage**: Higher

Best for: Studio analysis, audiophile setups, professional installations

## Analysis Methods

### Onset Method

Controls how LedFx detects audio transients (beats, drums, attacks).

| Method | Description |
|--------|-------------|
| **hfc** (default) | High Frequency Content - Best for drums and percussion |
| **energy** | Energy-based - Simple and fast |
| **complex** | Complex domain - Good for general audio |
| **specflux** | Spectral flux - Good for tonal changes |

### Pitch Method

Controls how LedFx detects musical pitch/notes.

| Method | Description |
|--------|-------------|
| **yinfft** (default) | Best balance of accuracy and speed |
| **yin** | Slightly more accurate, slower |
| **yinfast** | Faster, less accurate |

### Pitch Tolerance

Controls how sensitive pitch detection is. Range: 0.0-2.0, Default: 0.8

- Lower values: More strict pitch matching
- Higher values: More lenient pitch matching

## Melbank Settings

Melbanks are frequency analysis bands used by many effects.

### Melbank FFT Mode

- **tiered** (default): Uses optimized FFT sizes for different frequency ranges
- **formula**: Calculates FFT size based on frequency range

## Advanced: Custom FFT Overrides

For advanced users, individual FFT configurations can be overridden in `config.json`:

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

Format: `[fft_size, hop_size]` where:
- `fft_size`: Power of 2 (512, 1024, 2048, etc.)
- `hop_size`: Samples per frame (smaller = lower latency)

See the [Multi-FFT Documentation](/developer/multifft) for detailed technical information.
