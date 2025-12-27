# LedFx Librosa Engine Integration Architecture

## Purpose

This document captures the design, implementation, and usage of the LedFx Engine integration that uses librosa for advanced audio analysis. The integration provides real-time mood detection, tempo tracking, and musical feature extraction to drive automated scene changes and effect parameters.

## Overview

The Engine integration analyzes audio in real-time to detect musical characteristics like tempo, energy, and mood states. It uses a multi-process architecture to avoid GIL contention and provides event-based notifications when mood states change.

**Key Capabilities:**
- **8 Mood States**: silence, ambient, breakdown, chill, groove, build, peak, intense
- **Tempo Detection**: BPM and beat tracking
- **Section Detection**: Identify verse/chorus/drop transitions
- **Event Broadcasting**: `MoodChangedEvent` fires when mood changes
- **Configurable Sensitivity**: User-adjustable thresholds for mood classification
- **Effect Integration**: Number effect can display current mood

## Architecture Overview

### Multi-Process Design

The integration uses separate processes to avoid Python GIL contention:

1. **Main Process (LedFx)**: Runs `Engine` integration class
2. **Worker Process**: Runs librosa analysis with dedicated GIL
3. **IPC Communication**: Binary protocol over stdin/stdout pipes

```
┌─────────────────────────────────────────────────┐
│ Main Process (LedFx)                            │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Engine Integration (engine.py)           │  │
│  │  - Audio subscription                    │  │
│  │  - Event broadcasting                    │  │
│  │  - Config management                     │  │
│  └──────────┬──────────────────────┬────────┘  │
│             │                      │            │
│             v                      v            │
│  ┌──────────────────┐   ┌─────────────────┐   │
│  │ Audio Queue      │   │ MoodChangedEvent│   │
│  │ (asyncio.Queue)  │   │ Broadcasting    │   │
│  └──────────┬───────┘   └─────────────────┘   │
│             │                                   │
└─────────────┼───────────────────────────────────┘
              │ IPC (stdin/stdout)
              v
┌─────────────────────────────────────────────────┐
│ Worker Process (analysis_worker.py)             │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ AudioAnalyzer                            │  │
│  │  - 8-second sliding buffer               │  │
│  │  - Feature extraction (librosa)          │  │
│  │  - Mood classification                   │  │
│  │  - Section detection                     │  │
│  └──────────────────────────────────────────┘  │
│                                                 │
│  Output: JSON feature messages (stdout)         │
└─────────────────────────────────────────────────┘
```

### Component Structure

```
ledfx/integrations/
├── engine.py                      # Main Engine integration
│   └── Engine class              # Manages lifecycle, events, audio
└── librosa_worker/
    ├── protocol.py               # IPC message format constants
    ├── librosaEngineClient.py    # IPC client, subprocess manager
    └── analysis_worker.py        # Worker subprocess analyzer
```

## Audio Pipeline

### Audio Flow

```
Audio Device (44.1kHz)
    │
    v
AudioInputSource (60 Hz callbacks)
    │  ~735 samples/block
    v
Engine.audio_callback()
    │  Thread-safe enqueue
    v
asyncio.Queue (main event loop)
    │
    v
_audio_sender_loop() task
    │  MSG_TYPE_AUDIO
    v
Worker stdin (IPC)
    │
    v
AudioAnalyzer.process_audio_block()
    │  Accumulate in buffer
    v
Sliding Buffer (8 seconds)
    │  Analyze every 2 seconds
    v
_analyze_and_emit()
    │  Librosa feature extraction
    v
JSON on stdout
    │
    v
Engine._on_worker_features()
    │  Parse features
    v
MoodChangedEvent fired (if changed)
```

### Timing Characteristics

- **Audio Callback Rate**: 60 Hz (~16.7ms intervals)
  - Block size: 735 samples (44100 Hz ÷ 60)
  - Sample rate from `MIC_RATE` constant
- **Buffer Size**: 8 seconds (configurable via `sample_window`)
- **Analysis Rate**: Every 2 seconds (throttled to reduce CPU)
- **Feature Latency**: ~2-2.2 seconds from audio input to feature output
- **Mood Event Latency**: ~2 seconds (only fires on actual mood changes)

### Threading Model

- **Audio Capture**: Dedicated audio thread (outside Python)
- **Callback Execution**: Audio thread context (non-blocking required)
- **Queue Bridge**: `call_soon_threadsafe()` bridges to event loop
- **IPC Sending**: Asyncio task on main event loop
- **Analysis**: Worker process with dedicated GIL (no contention)

## Mood Detection System

### Mood States

The system classifies music into 8 distinct mood states based on energy, onset density, tempo, and brightness:

| Mood | Energy | Density | Tempo | Brightness | Musical Context |
|------|--------|---------|-------|------------|------------------|
| **silence** | Near Zero | Near Zero | Any | Any | True silence, pauses between songs |
| **ambient** | Very Low | Very Low | Slow (<90 BPM) | Any | Atmospheric intros, ambient sections |
| **breakdown** | Very Low | Very Low | Fast (>130 BPM) | Any | EDM breakdowns, build-up preparation |
| **chill** | Low | Low | Any | Any | Verses, relaxed sections |
| **groove** | Moderate | Moderate | Any | Any | Steady rhythmic sections, verses |
| **build** | Rising | Rising | Any | Any | Pre-chorus, build-ups, tension |
| **peak** | High | High | Any | Bright | Chorus, drops (bright/energetic) |
| **intense** | High | High | Any | Dark | Heavy sections, bass drops |

### Classification Algorithm

**Feature Extraction:**
```python
tempo = librosa.beat.tempo()                    # BPM
rms = librosa.feature.rms()                     # Energy
onset_env = librosa.onset.onset_strength()      # Onset density
centroid = librosa.feature.spectral_centroid()  # Brightness
```

**Z-Score Normalization:**
- Running mean and variance tracked with exponential moving average
- `z_energy = (rms - mean) / std`
- `z_density = (onset_mean - mean) / std`
- `z_brightness = (centroid - 2000) / 1000`

**Configurable Thresholds:**
- `silence_threshold` (default: -1.5): Extremely low energy/density (below ambient)
- `ambient_threshold` (default: -0.8): Very low energy/density
- `chill_threshold` (default: -0.3): Below average energy
- `build_threshold` (default: 0.3): Rising energy/density
- `peak_threshold` (default: 0.7): High energy/density

**Classification Logic:**
```python
# Silence detection (extremely low z-scores)
if z_energy < silence_z and z_density < silence_z:
    mood = "silence"
elif z_energy < ambient_z and z_density < ambient_z:
    mood = "ambient" if tempo < 90 else "breakdown"
elif z_energy > peak_z and z_density > peak_z:
    mood = "peak" if z_brightness > 0.5 else "intense"
elif z_energy > peak_z or z_density > peak_z:
    mood = "build"
elif z_energy > build_z and z_density > build_z:
    mood = "build"
elif z_energy > 0.0 or z_density > 0.0:
    mood = "groove"
elif z_energy < chill_z or z_density < chill_z:
    mood = "chill"
else:
    mood = "groove"
```

### Section Detection

Identifies transitions between song sections (verse→chorus, build→drop) using two methods:

1. **Feature Distance**: Measures change in spectral characteristics
   - Distance threshold: 0.4 (configurable)
   - Features: spectral centroid, bandwidth, flatness, onset envelope, chroma
   - Normalized by running mean

2. **Energy Jumps**: Detects sudden energy changes
   - Energy jump threshold: 1.5 standard deviations
   - Tracks `z_energy` delta between analysis windows

**Cooldown:** 4 seconds between section changes (prevents flicker)

### Event Broadcasting

When mood changes, the Engine fires a `MoodChangedEvent`:

```python
class MoodChangedEvent(Event):
    def __init__(self, mood, previous_mood=None):
        super().__init__(Event.MOOD_CHANGED)
        self.mood = mood              # Current mood state
        self.previous_mood = previous_mood  # Previous mood (for transitions)
```

**Usage Example:**
```python
def on_mood_change(event):
    print(f"Mood changed: {event.previous_mood} → {event.mood}")

ledfx.events.add_listener(on_mood_change, Event.MOOD_CHANGED)
```

## Configuration

### Integration Config Schema

```python
CONFIG_SCHEMA = vol.Schema({
    vol.Required("name"): str,
    vol.Required("description"): str,
    vol.Optional("sample_window", default=8): vol.Range(min=2, max=30),
    vol.Optional("ambient_threshold", default=-0.8): vol.Range(min=-1.5, max=-0.3),
    vol.Optional("peak_threshold", default=0.7): vol.Range(min=0.3, max=1.5),
    vol.Optional("build_threshold", default=0.3): vol.Range(min=0.1, max=0.8),
    vol.Optional("chill_threshold", default=-0.3): vol.Range(min=-0.8, max=0.0),
    vol.Optional("diag", default=False): bool,
    vol.Optional("debug", default=False): bool,
})
```

### Configuration Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `sample_window` | 8 | 2-30 | Audio buffer size in seconds |
| `ambient_threshold` | -0.8 | -1.5 to -0.3 | Z-score for ambient/breakdown states |
| `peak_threshold` | 0.7 | 0.3 to 1.5 | Z-score for peak/intense states |
| `build_threshold` | 0.3 | 0.1 to 0.8 | Z-score for build state |
| `chill_threshold` | -0.3 | -0.8 to 0.0 | Z-score for chill state |
| `diag` | false | boolean | Enable Teleplot diagnostics |
| `debug` | false | boolean | Enable detailed debug logging |

**Tuning Guidelines:**
- **More sensitive** (frequent mood changes): Lower thresholds (e.g., peak_threshold=0.5)
- **More stable** (fewer changes): Raise thresholds (e.g., peak_threshold=1.0)
- **Larger buffer** (sample_window=12): More accurate but slower response
- **Smaller buffer** (sample_window=4): Faster response but less accurate

## IPC Protocol

### Message Format

Binary header + raw payload:
```
<msg_type: uint8><payload_len: uint32 little-endian><payload bytes>
```

Defined in `protocol.py` using `struct.Struct('<BI')`.

### Message Types

**MSG_TYPE_CONFIG (2)**: Configuration at startup
```json
{
  "sample_rate": 22050,
  "sample_window": 8,
  "ambient_z": -0.8,
  "peak_z": 0.7,
  "build_z": 0.3,
  "chill_z": -0.3
}
```

**MSG_TYPE_AUDIO (1)**: Raw float32 PCM samples
```python
payload = audio_block.astype(np.float32).tobytes()
```

**MSG_TYPE_SHUTDOWN (255)**: Graceful shutdown signal

### Feature Output Format

Worker emits JSON lines on stdout:
```json
{
  "type": "feature_update",
  "tempo": 124.7,
  "mood": "build",
  "section_change": false,
  "z_energy": 0.45,
  "z_density": 0.32,
  "section_distance": 0.18
}
```

## Effect Integration

### Number Effect - Mood Display

The `Number` effect can display the current mood state on LED matrices:

**Configuration:**
```python
{
  "value_source": "Mood",
  "font": "Arial",
  "text_color": "#FF0000"
}
```

**Implementation:**
- Subscribes to `MoodChangedEvent` when `value_source="Mood"`
- Updates `display_value` with mood string on events
- Unsubscribes when value_source changes
- Uses longest mood name ("breakdown") for font sizing

**Usage:**
1. Create virtual with 2D matrix device
2. Add Number effect
3. Select "Mood" from value_source dropdown
4. Enable Engine integration
5. Mood text updates automatically every 2 seconds

## Lifecycle Management

### Startup Sequence

1. User enables Engine integration in UI
2. `Engine.__init__()` creates instance, validates librosa available
3. `Engine.connect()` called:
   - Creates `LibrosaEngineClient` instance
   - Spawns worker subprocess: `python analysis_worker.py`
   - Sends `MSG_TYPE_CONFIG` with thresholds and settings
   - Creates asyncio Queue for audio buffering
   - Starts async tasks: `_listen_loop()`, `_log_stderr()`, `_audio_sender_loop()`
   - Subscribes to audio via `self._ledfx.audio.subscribe(self.audio_callback)`
   - Initializes `_previous_mood` tracking

**Runtime:**
- Audio callback enqueues blocks to queue
- Sender loop drains queue, sends to worker stdin
- Worker accumulates audio in sliding buffer
- Worker analyzes every 2 seconds, emits features
- `_on_worker_features()` receives JSON messages
- If mood changed, fires `MoodChangedEvent`
- Effects/scenes can listen to mood events

**Shutdown:**
1. User disables/deletes integration
2. `on_delete()` or `disconnect()` called
3. Audio subscription cancelled
4. Tasks cancelled and awaited
5. `MSG_TYPE_SHUTDOWN` sent to worker
6. Worker exits gracefully (or killed after 5s timeout)
7. Resources cleaned up

**Singleton Enforcement:**
- API checks for existing Engine integration before creating new one
- Calls `on_delete()` on existing instance
- Ensures clean transition between configs

## Performance Metrics

### CPU Usage
- **Main Process**: <1% overhead (queue, IPC, events)
- **Worker Process**: 5-15% (varies with buffer size and features)
- **No GIL Contention**: Separate process architecture

### Memory Usage
- **Audio Queue**: ~100 KB (60 blocks × 735 samples × 4 bytes)
- **Worker Buffer**: ~1.4 MB (8 seconds × 22050 Hz × 4 bytes)
- **Total Overhead**: ~2 MB

### Latency
- **Audio → Queue**: <1ms (thread-safe enqueue)
- **Queue → Worker**: ~16ms (asyncio task wakeup)
- **Analysis Time**: 50-200ms (librosa processing)
- **Total Latency**: ~2.2 seconds (includes 2s throttle period)

### Throughput
- **Audio Data Rate**: ~176 KB/s (22050 samples/s × 4 bytes × 2 channels)
- **Feature Update Rate**: 0.5 Hz (every 2 seconds)
- **Event Fire Rate**: Variable (only when mood changes)

## Development and Debugging

### VS Code Debugging Setup

The worker runs in a separate subprocess, so standard breakpoints require debugpy attachment.

**Prerequisites:**
```powershell
uv pip install debugpy
```

**Launch Configuration** (`.vscode/launch.json`):
```json
{
    "name": "Attach to Worker Process",
    "type": "debugpy",
    "request": "attach",
    "connect": {
        "host": "localhost",
        "port": 5679
    },
    "justMyCode": false
}
```

**Debugging Workflow:**
1. Start LedFx with normal debug config
2. Enable Engine integration (worker starts with debugpy listening on 5679)
3. In VS Code, select "Attach to Worker Process" and start debugging
4. Set breakpoints in `analysis_worker.py`
5. Breakpoints hit during normal operation

**Key Breakpoint Locations:**
- `handle_config()` - Configuration received
- `process_audio_block()` - Each audio block processed
- `_analyze_and_emit()` - Analysis runs (every 2 seconds)
- Mood classification logic - Around line 240

### Teleplot Integration

Enable diagnostics to monitor performance:
```json
{
  "diag": true,
  "debug": true
}
```

**Metrics Exported:**
- `tempo` - Current BPM
- `z_energy` - Energy z-score
- `z_density` - Onset density z-score
- `section_distance` - Feature distance for section detection
- `section_change` - 0/1 indicator
- `mood` - Current mood state (text telemetry)

**View in Teleplot:**
```
teleplot serve
# Open http://localhost:8080
```

### Debugging Without Debugpy

**Stderr Logging:**
```python
sys.stderr.write(f"Debug: mood={mood}, z_energy={z_energy}\n")
sys.stderr.flush()
```

**Feature Inspection:**
```python
# In _on_worker_features()
_LOGGER.warning(f"Features: {msg}")
```

**Monitor Logs:**
- Worker stderr appears in main LedFx console
- Look for `[Worker]` prefix in logs

### Production Considerations

**Remove Debug Code:**
- Comment out debugpy block in `analysis_worker.py`
- Or add environment variable check: `if os.environ.get("DEBUG_WORKER")`

**Optimize Settings:**
- Larger `sample_window` = more accurate, slower response
- Smaller `sample_window` = faster response, less accurate
- Adjust thresholds based on music genre preferences

## Known Issues and Limitations

1. **No Worker Auto-Restart**: Worker crash requires manual integration restart
2. **Unbounded Queue Growth**: If worker stalls completely, queue could grow indefinitely
3. **No Feature History**: Previous analysis not accessible, only current state
4. **Section Detection Sensitivity**: May trigger too often or miss transitions depending on music
5. **Debugpy Always Enabled**: Debug code present in production (TODO: remove)
6. **No Health Monitoring**: Cannot detect stuck worker until feature timeout
7. **Single Integration Instance**: Only one Engine can run (by design, but limits flexibility)

## Future Enhancements

### Planned Features
- [ ] Worker auto-restart on crash with exponential backoff
- [ ] Configurable analysis features (disable unused features)
- [ ] Scene automation based on mood transitions
- [ ] Beat-synced effect parameters
- [ ] Chroma-based major/minor tonality detection
- [ ] Hysteresis for mood transitions (prevent flickering)
- [ ] Configurable tempo thresholds (fast/slow BPM)
- [ ] Worker health monitoring and status reporting
- [ ] Feature history buffer for trend analysis
- [ ] Multiple simultaneous Engine instances (parallel analysis)
- [ ] Real-time beat tracking with frame-accurate timing
- [ ] Audio visualization forwarding to frontend
- [ ] Performance dashboard in UI

### Architecture Improvements
- [ ] Worker → Main process RPC for bidirectional communication
- [ ] Protobuf or MessagePack for more efficient serialization
- [ ] Shared memory for audio transfer (eliminate IPC copies)
- [ ] Worker thread pool for parallel feature extraction
- [ ] Incremental analysis (update features per block, not per window)
- [ ] Adaptive throttling based on CPU load

## Testing Strategy

### Manual Testing Checklist
- [ ] Enable integration, verify worker starts
- [ ] Play music, verify mood changes in logs/Teleplot
- [ ] Number effect displays correct mood state
- [ ] Disable integration, verify clean shutdown
- [ ] Update config, verify worker receives new thresholds
- [ ] Delete integration, verify resources released
- [ ] Create second Engine, verify first deleted automatically
- [ ] Attach debugger, verify breakpoints hit
- [ ] Mood changes fire events (check event listeners)
- [ ] Section detection triggers appropriately

### Automated Tests Needed
- **Unit Tests:**
  - Protocol serialization/deserialization
  - AudioAnalyzer buffer management
  - Mood classification logic
  - Z-score calculation
  - Section detection algorithm

- **Integration Tests:**
  - Audio flow end-to-end (callback → worker → features)
  - Worker lifecycle (startup, shutdown, restart)
  - IPC robustness (malformed messages, disconnection)
  - Event firing and listener notification

- **Performance Tests:**
  - Latency measurement (audio → event)
  - CPU profiling under load
  - Memory leak detection (long-running)
  - Throughput testing (burst audio blocks)

- **Stress Tests:**
  - High audio rate (burst blocks, check queue depth)
  - Worker slowdown (artificial delay, verify backpressure)
  - Rapid enable/disable (toggle integration repeatedly)
  - Long-running stability (24+ hours)

- **Recovery Tests:**
  - Worker crash (kill process, verify detection)
  - IPC failure (close pipes unexpectedly)
  - Invalid messages (malformed JSON, wrong types)
  - Resource exhaustion (low memory/CPU)

## Appendix: Feature Extraction Details

### Librosa Features Used

**Tempo and Beat:**
```python
tempo, beats = librosa.beat.beat_track(y=buffer, sr=sample_rate)
```

**Energy:**
```python
rms = librosa.feature.rms(y=buffer)
```

**Onset Detection:**
```python
onset_env = librosa.onset.onset_strength(y=buffer, sr=sample_rate)
onset_mean = np.mean(onset_env)
```

**Spectral Features:**
```python
centroid = librosa.feature.spectral_centroid(y=buffer, sr=sample_rate)
bandwidth = librosa.feature.spectral_bandwidth(y=buffer, sr=sample_rate)
flatness = librosa.feature.spectral_flatness(y=buffer)
```

**Chroma (Harmonic Content):**
```python
chroma = librosa.feature.chroma_stft(y=buffer, sr=sample_rate)
```

### Z-Score Normalization

**Exponential Moving Average:**
```python
beta = 0.97  # Smoothing factor for variance
alpha = 0.8  # Smoothing factor for feature mean

# Energy stats
delta_e = rms - self._energy_mean
self._energy_mean += (1.0 - beta) * delta_e
self._energy_var = beta * self._energy_var + (1.0 - beta) * (delta_e ** 2)
energy_std = max(self._energy_var ** 0.5, 1e-6)
z_energy = (rms - self._energy_mean) / energy_std
```

**Why Exponential Moving Average:**
- Adapts to changing music over time
- Prevents sudden jumps from corrupting statistics
- Beta=0.97 means ~30 window memory
- Alpha=0.8 means ~5 window memory for features

### Section Detection Algorithm

**Feature Vector:**
```python
curr_feat = np.concatenate([
    np.mean(centroid, axis=1),
    np.mean(bandwidth, axis=1),
    np.mean(flatness, axis=1),
    np.array([onset_mean]),
    np.mean(chroma, axis=1)
])
```

**Distance Calculation:**
```python
diff = curr_feat - self._feat_prev
norm = self._feat_mean + 1e-8
dist = np.linalg.norm(diff / norm)
```

**Trigger Conditions:**
1. Feature distance > 0.4 (spectral change)
2. OR energy jump > 1.5 std (sudden volume change)
3. AND cooldown expired (4 seconds since last section change)

---

**Last Updated:** December 26, 2025
**LedFx Version:** engine1 branch
**Integration Version:** 1.0 (initial mood detection)
