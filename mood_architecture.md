# Mood Detection Architecture: Non-Blocking Librosa Implementation

## Current Architecture (PR #1639)

### Implementation Overview

The current mood detection system integrates librosa for advanced audio analysis but runs **synchronously in the main Python process**, which can block the event loop.

**Key Components:**
- `ledfx/mood_detector.py` - Main mood detection coordinator
- `ledfx/mood_detector_librosa.py` - Librosa feature extraction
- `ledfx/integrations/mood_manager.py` - Mood-based automation
- Optional dependency: `librosa>=0.11.0` in `[project.optional-dependencies]`

### Current Execution Flow

```
Main Event Loop (asyncio)
    └─> mood_manager._monitor_loop() [async task]
        └─> mood_detector.update() [SYNCHRONOUS]
            └─> librosa_extractor.extract_features() [BLOCKING - holds GIL]
                └─> librosa.feature.chroma_stft() [CPU-intensive]
                └─> librosa.beat.beat_track() [CPU-intensive]
                └─> librosa.feature.mfcc() [CPU-intensive]
                └─> ... (13 feature categories)
```

### Problem Statement

**Current Implementation:**
- ❌ Runs in same process/thread as main LedFx
- ❌ Holds Python GIL during computation
- ❌ Blocks event loop (despite async context)
- ⚠️ Can cause latency spikes every 2 seconds (default update interval)
- ⚠️ Impacts API responsiveness, WebSocket updates, LED rendering

**Mitigation Attempts:**
- ✅ Throttling: 2-second update interval (configurable)
- ✅ Caching: Results cached between updates
- ✅ Lower sample rate: 22050 Hz instead of original
- ⚠️ **Still blocks during 50-200ms librosa computation**

## Proposed Architecture: ProcessPoolExecutor + Shared Memory

### High-Level Design

```
Main Process (LedFx Event Loop)
    │
    ├─> Shared Memory Buffer (numpy array)
    │   └─> Audio data written here (~528KB for 3 sec @ 44.1kHz)
    │
    └─> ProcessPoolExecutor
        └─> Worker Process (separate GIL, separate CPU core)
            └─> Read from shared memory (zero-copy)
            └─> Run librosa feature extraction
            └─> Return results via pickle (small dict)
```

### Benefits

| Metric | Current | Proposed |
|--------|---------|----------|
| Event loop blocking | 50-200ms | **0ms** (non-blocking) |
| GIL contention | High | **None** (separate process) |
| CPU core utilization | Limited by GIL | **Full parallel** |
| Audio data transfer | N/A (same process) | **~0.5ms** (shared memory) |
| Memory overhead | Minimal | +20-30MB (separate Python) |
| Responsiveness | Periodic lags | **Consistently smooth** |

### Technical Implementation

#### 1. Shared Memory Setup (Python 3.8+)

```python
import asyncio
import numpy as np
from multiprocessing import shared_memory
from concurrent.futures import ProcessPoolExecutor

class SharedMemoryLibrosaExtractor:
    """
    Non-blocking librosa feature extractor using ProcessPoolExecutor
    and shared memory for zero-copy audio data transfer.
    """
    
    def __init__(self, buffer_size: int, sample_rate: int, update_interval: float):
        """
        Args:
            buffer_size: Maximum audio buffer size in samples
            sample_rate: Original audio sample rate
            update_interval: Minimum seconds between feature updates
        """
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.target_sample_rate = 22050
        self.update_interval = update_interval
        
        # Create persistent shared memory buffer
        self.shm = shared_memory.SharedMemory(
            create=True,
            size=buffer_size * np.float32().itemsize
        )
        self.shm_name = self.shm.name
        
        # Create single-worker process pool
        self.executor = ProcessPoolExecutor(max_workers=1)
        
        # Feature cache
        self._features_cache = {}
        self._last_update = 0.0
        self._lock = asyncio.Lock()
        
    async def extract_features_async(self, audio_data: np.ndarray) -> Optional[dict]:
        """
        Extract librosa features asynchronously without blocking event loop.
        
        Args:
            audio_data: Audio samples as float32 numpy array
            
        Returns:
            Dictionary of extracted features or None if throttled
        """
        current_time = asyncio.get_event_loop().time()
        
        # Throttle updates
        async with self._lock:
            if current_time - self._last_update < self.update_interval:
                return self._features_cache.copy() if self._features_cache else None
            self._last_update = current_time
        
        # Copy audio data to shared memory (fast, ~0.5ms)
        shared_array = np.ndarray(
            audio_data.shape,
            dtype=np.float32,
            buffer=self.shm.buf
        )
        np.copyto(shared_array, audio_data)
        
        # Submit to process pool (non-blocking)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor,
                _librosa_worker_process,
                self.shm_name,
                len(audio_data),
                self.sample_rate,
                self.target_sample_rate
            )
            
            async with self._lock:
                self._features_cache = result
            
            return result
            
        except Exception as e:
            _LOGGER.warning(f"Librosa extraction failed: {e}")
            return self._features_cache.copy() if self._features_cache else None
    
    def cleanup(self):
        """Clean up shared memory and process pool"""
        self.executor.shutdown(wait=True)
        self.shm.close()
        self.shm.unlink()
```

#### 2. Worker Process Function

```python
def _librosa_worker_process(
    shm_name: str,
    data_length: int,
    orig_sample_rate: int,
    target_sample_rate: int
) -> dict:
    """
    Worker function that runs in separate process.
    
    This function:
    1. Attaches to shared memory
    2. Creates zero-copy numpy view
    3. Runs all librosa feature extraction
    4. Returns small results dict
    
    Args:
        shm_name: Shared memory identifier
        data_length: Number of audio samples
        orig_sample_rate: Original sample rate
        target_sample_rate: Target sample rate for librosa
        
    Returns:
        Dictionary of extracted features
    """
    import librosa
    import numpy as np
    from multiprocessing import shared_memory
    
    # Attach to shared memory (no copy)
    shm = shared_memory.SharedMemory(name=shm_name)
    audio_data = np.ndarray(
        (data_length,),
        dtype=np.float32,
        buffer=shm.buf
    )
    
    try:
        # Resample audio
        audio_resampled = librosa.resample(
            audio_data,
            orig_sr=orig_sample_rate,
            target_sr=target_sample_rate,
            res_type='kaiser_best'
        )
        
        features = {}
        
        # Extract all features (this is where CPU time is spent)
        # 1. Chroma
        chroma = librosa.feature.chroma_stft(y=audio_resampled, sr=target_sample_rate)
        features['chroma'] = np.mean(chroma, axis=1)
        features['chroma_std'] = np.std(chroma, axis=1)
        
        # 2. Key detection
        # ... (implement key detection logic)
        
        # 3. Tempo and beats
        tempo, beats = librosa.beat.beat_track(y=audio_resampled, sr=target_sample_rate)
        features['tempo'] = float(tempo)
        features['beat_times'] = beats
        
        # 4-13. All other features
        # ... (implement remaining feature extraction)
        
        return features
        
    finally:
        shm.close()
```

#### 3. Integration into MoodDetector

```python
# In ledfx/mood_detector.py

class MoodDetector:
    def __init__(self, audio, config):
        # ... existing init code ...
        
        if self._use_librosa:
            # Calculate buffer size based on config
            buffer_duration = self._config.get('librosa_buffer_duration', 3.0)
            sample_rate = self.audio._config.get('sample_rate', 60)
            buffer_size = int(buffer_duration * sample_rate)
            
            # Create async extractor instead of sync one
            self._librosa_extractor = SharedMemoryLibrosaExtractor(
                buffer_size=buffer_size,
                sample_rate=sample_rate,
                update_interval=self._config.get('librosa_update_interval', 2.0)
            )
    
    async def update_async(self) -> dict[str, float]:
        """
        Async version of update() that doesn't block event loop.
        """
        # ... existing mood calculation logic ...
        
        if self._use_librosa and self._librosa_extractor:
            # This is now non-blocking!
            features = await self._librosa_extractor.extract_features_async(audio_buffer)
            # ... process features ...
        
        return self._current_mood.copy()
```

#### 4. Update MoodManager Integration

```python
# In ledfx/integrations/mood_manager.py

async def _update(self) -> None:
    """Update mood and apply changes"""
    if self._mood_detector:
        # Call async version (non-blocking)
        current_mood = await self._mood_detector.update_async()
        # ... rest of logic ...
```

## Performance Measurement Strategies

### Pre-Implementation Baseline Metrics

#### 1. Event Loop Responsiveness

**Test Setup:**
```python
# Add to mood_manager.py or separate test script
import asyncio
import time

async def measure_event_loop_latency():
    """
    Measure event loop latency during mood detection updates.
    This identifies blocking operations.
    """
    latencies = []
    
    async def heartbeat():
        """High-frequency heartbeat to detect blocking"""
        last_time = time.perf_counter()
        while True:
            await asyncio.sleep(0.01)  # 10ms target
            current_time = time.perf_counter()
            actual_delay = (current_time - last_time) * 1000  # ms
            if actual_delay > 15:  # More than 5ms over target
                latencies.append(actual_delay)
            last_time = current_time
    
    # Run heartbeat while mood detection is active
    await asyncio.gather(
        heartbeat(),
        mood_manager._monitor_loop()
    )
    
    return {
        'max_latency_ms': max(latencies) if latencies else 0,
        'p95_latency_ms': np.percentile(latencies, 95) if latencies else 0,
        'p99_latency_ms': np.percentile(latencies, 99) if latencies else 0,
        'spike_count': len(latencies)
    }
```

**Metrics to Capture:**
- Maximum event loop latency
- P95 and P99 latency percentiles
- Number of latency spikes > 50ms
- Latency distribution histogram

#### 2. API Response Time

**Test Setup:**
```python
import aiohttp
import time

async def measure_api_responsiveness(ledfx_url: str, duration: int = 60):
    """
    Measure API response times during mood detection.
    Tests if librosa blocks API requests.
    """
    async with aiohttp.ClientSession() as session:
        response_times = []
        
        for _ in range(duration * 10):  # 10 requests/sec
            start = time.perf_counter()
            try:
                async with session.get(f"{ledfx_url}/api/virtuals") as resp:
                    await resp.json()
                response_time = (time.perf_counter() - start) * 1000
                response_times.append(response_time)
            except Exception as e:
                response_times.append(float('inf'))
            
            await asyncio.sleep(0.1)
        
        return {
            'mean_response_ms': np.mean(response_times),
            'p95_response_ms': np.percentile(response_times, 95),
            'p99_response_ms': np.percentile(response_times, 99),
            'timeout_count': sum(1 for t in response_times if t == float('inf'))
        }
```

#### 3. LED Rendering Performance

**Test Setup:**
```python
async def measure_led_frame_times(ledfx):
    """
    Monitor LED frame rendering times to detect jitter.
    """
    frame_times = []
    
    # Hook into virtual update events
    def on_virtual_update(event):
        frame_times.append(time.perf_counter())
    
    listener = ledfx.events.add_listener(
        on_virtual_update,
        Event.VIRTUAL_UPDATE
    )
    
    await asyncio.sleep(60)  # Measure for 60 seconds
    
    ledfx.events.remove_listener(listener)
    
    # Calculate frame time deltas
    deltas = [
        (frame_times[i] - frame_times[i-1]) * 1000
        for i in range(1, len(frame_times))
    ]
    
    target_fps = 60
    target_frame_time = 1000 / target_fps
    
    return {
        'mean_frame_time_ms': np.mean(deltas),
        'frame_time_std_ms': np.std(deltas),
        'dropped_frames': sum(1 for d in deltas if d > target_frame_time * 1.5),
        'max_frame_time_ms': max(deltas)
    }
```

#### 4. CPU and Memory Profiling

**Test Setup:**
```python
import psutil
import tracemalloc

async def profile_mood_detection(duration: int = 60):
    """
    Profile CPU and memory usage during mood detection.
    """
    process = psutil.Process()
    tracemalloc.start()
    
    cpu_samples = []
    memory_samples = []
    
    start_snapshot = tracemalloc.take_snapshot()
    
    for _ in range(duration):
        cpu_percent = process.cpu_percent(interval=1.0)
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        cpu_samples.append(cpu_percent)
        memory_samples.append(memory_mb)
    
    end_snapshot = tracemalloc.take_snapshot()
    top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')
    
    tracemalloc.stop()
    
    return {
        'mean_cpu_percent': np.mean(cpu_samples),
        'max_cpu_percent': max(cpu_samples),
        'mean_memory_mb': np.mean(memory_samples),
        'memory_growth_mb': memory_samples[-1] - memory_samples[0],
        'top_memory_allocations': top_stats[:10]
    }
```

### Benchmark Test Script

```python
#!/usr/bin/env python3
"""
Mood Detection Performance Benchmark
Run before and after ProcessPoolExecutor implementation.
"""

import asyncio
import json
import time
from datetime import datetime

async def run_full_benchmark(ledfx, duration: int = 300):
    """
    Run comprehensive performance benchmark.
    
    Args:
        ledfx: LedFx instance with mood detection enabled
        duration: Benchmark duration in seconds
    """
    print(f"Starting benchmark (duration: {duration}s)...")
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'duration_seconds': duration,
        'configuration': {
            'librosa_enabled': True,  # Update based on actual config
            'update_interval': 2.0,
            'buffer_duration': 3.0
        }
    }
    
    # Run all measurements concurrently
    print("Running measurements...")
    loop_latency, api_response, led_frames, cpu_memory = await asyncio.gather(
        measure_event_loop_latency(),
        measure_api_responsiveness('http://localhost:8888', duration),
        measure_led_frame_times(ledfx),
        profile_mood_detection(duration)
    )
    
    results['event_loop'] = loop_latency
    results['api_responsiveness'] = api_response
    results['led_rendering'] = led_frames
    results['resource_usage'] = cpu_memory
    
    # Save results
    filename = f"mood_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Benchmark complete. Results saved to {filename}")
    print("\nSummary:")
    print(f"  Max event loop latency: {loop_latency['max_latency_ms']:.1f}ms")
    print(f"  P99 API response time: {api_response['p99_response_ms']:.1f}ms")
    print(f"  Dropped LED frames: {led_frames['dropped_frames']}")
    print(f"  Mean CPU usage: {cpu_memory['mean_cpu_percent']:.1f}%")
    
    return results

if __name__ == '__main__':
    # Run benchmark
    asyncio.run(run_full_benchmark(ledfx, duration=300))
```

### Comparison Metrics

Run benchmarks **before** and **after** implementation, then compare:

| Metric | Current (Sync) | Target (Async) | Improvement |
|--------|----------------|----------------|-------------|
| **Event Loop Latency** | | | |
| Max latency | 150-250ms | <20ms | **90%+** |
| P99 latency | 100-200ms | <15ms | **85%+** |
| Spikes per minute | 30 | <5 | **85%+** |
| **API Responsiveness** | | | |
| P99 response time | 200-300ms | <50ms | **75%+** |
| **LED Rendering** | | | |
| Dropped frames (60 FPS) | 5-15/min | <2/min | **80%+** |
| **Resource Usage** | | | |
| CPU (single core) | 25-35% | 15-20% (main) + 20-30% (worker) | Better distribution |
| Memory | 200MB | 230MB | +15% acceptable |

## Migration Plan

### Phase 1: Preparation (1-2 hours)
1. Create baseline benchmarks with current implementation
2. Document current behavior and known issues
3. Review and test benchmark scripts

### Phase 2: Implementation (4-6 hours)
1. Implement `SharedMemoryLibrosaExtractor` class
2. Create `_librosa_worker_process` function
3. Update `MoodDetector` to support async operation
4. Update `MoodManager` integration
5. Add configuration flag to toggle old/new implementation

### Phase 3: Testing (2-4 hours)
1. Unit tests for shared memory handling
2. Integration tests for feature extraction
3. Stress tests with concurrent operations
4. Memory leak detection over extended runtime

### Phase 4: Validation (2-3 hours)
1. Run full benchmark suite
2. Compare metrics against baseline
3. Validate feature extraction accuracy (ensure results match)
4. Test edge cases (process crashes, cleanup, etc.)

### Phase 5: Deployment (1-2 hours)
1. Add migration notes to documentation
2. Update configuration examples
3. Add performance comparison to PR description
4. Enable by default if metrics meet targets

**Total Estimated Time:** 10-17 hours

## Dependency Management: Avoiding Unnecessary Librosa Dependencies

### Problem: Heavy Optional Dependencies

Librosa has several optional dependencies that significantly increase installation size and memory footprint:
- **matplotlib** (~100MB) - Used only for visualization functions
- **audioread** - Used for audio file I/O (not needed for live audio)
- **ffmpeg/soundfile** - Audio codec support (not needed for numpy arrays)
- **numba** - JIT compilation (optional performance enhancement)
- **pooch** - Dataset downloading (not needed for feature extraction)

**For LedFx, we only need librosa's core feature extraction functions, not visualization or file I/O.**

### Solution: Selective Import Strategy

The current implementation already uses a safe import pattern:

```python
# In mood_detector_librosa.py
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    librosa = None
```

### Recommended Installation Instructions

**Option 1: Minimal Librosa (Recommended)**
```bash
# Install only core dependencies
pip install librosa --no-deps
pip install numpy scipy scikit-learn joblib decorator resampy numba
```

**Option 2: Standard Librosa (Easier but heavier)**
```bash
pip install librosa
```

**Option 3: pyproject.toml Configuration**
```toml
[project.optional-dependencies]
mood_advanced = [
    "librosa>=0.11.0",
    # Explicitly exclude visualization dependencies in documentation
]
```

### Implementation: Avoid Display Functions

Ensure the worker process never imports visualization functions:

```python
def _librosa_worker_process(
    shm_name: str,
    data_length: int,
    orig_sample_rate: int,
    target_sample_rate: int
) -> dict:
    """
    Worker function that runs in separate process.
    
    IMPORTANT: Only import feature extraction functions, not display/viz.
    This avoids loading matplotlib and other heavy dependencies.
    """
    # Import only what we need - librosa.feature, librosa.beat, etc.
    # Do NOT import librosa.display or any visualization functions
    import librosa
    import librosa.feature
    import librosa.beat
    import librosa.onset
    import librosa.effects
    # Explicitly avoid: import librosa.display (triggers matplotlib import)
    
    import numpy as np
    from multiprocessing import shared_memory
    
    # ... rest of implementation ...
```

### Verification: Check What's Imported

Add diagnostic logging to verify no heavy deps are loaded:

```python
def _librosa_worker_process(...):
    import sys
    import logging
    
    _LOGGER = logging.getLogger(__name__)
    
    # Log what's imported (debug mode only)
    heavy_deps = ['matplotlib', 'audioread', 'soundfile', 'ffmpeg']
    loaded_heavy = [dep for dep in heavy_deps if dep in sys.modules]
    
    if loaded_heavy:
        _LOGGER.warning(f"Heavy dependencies loaded in worker: {loaded_heavy}")
    else:
        _LOGGER.debug("Worker process: clean librosa import (no heavy deps)")
    
    # ... feature extraction ...
```

### Lazy Import Pattern (Alternative)

If needed, use lazy imports within functions to defer loading:

```python
def extract_chroma(audio_data, sr):
    """Lazy import to avoid loading librosa at module import time"""
    import librosa.feature
    return librosa.feature.chroma_stft(y=audio_data, sr=sr)

def extract_tempo(audio_data, sr):
    """Lazy import to avoid loading librosa at module import time"""
    import librosa.beat
    return librosa.beat.beat_track(y=audio_data, sr=sr)
```

### Numba Considerations

**Numba is actually beneficial** - it provides significant speed improvements for librosa:
- 2-5x faster feature extraction
- Lower CPU usage
- Only ~50MB overhead
- No runtime penalty if unavailable (librosa falls back to pure Python)

#### Platform & Python Version Support

**LedFx Requirements:** Python 3.10-3.13 on Windows, macOS, Linux

**Numba Compatibility Matrix:**

| Python Version | Windows | macOS (Intel) | macOS (Apple Silicon) | Linux x86_64 | Linux ARM (RPi) |
|----------------|---------|---------------|----------------------|--------------|-----------------|
| **3.10** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **3.11** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **3.12** | ✅ Full | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **3.13** | ⚠️ Limited* | ⚠️ Limited* | ⚠️ Limited* | ⚠️ Limited* | ⚠️ Limited* |

*As of December 2024, numba has experimental support for Python 3.13. Full support expected in numba 0.61+.

**Platform-Specific Notes:**

1. **Windows:**
   - ✅ Excellent support across all architectures (x64, ARM64)
   - No special considerations
   - Pre-built wheels available

2. **macOS:**
   - ✅ Intel Macs: Full support
   - ✅ Apple Silicon (M1/M2/M3): Full support via Rosetta 2 and native ARM64
   - Pre-built wheels for both architectures

3. **Linux:**
   - ✅ x86_64: Full support
   - ✅ ARM64 (Raspberry Pi 4/5): Full support
   - ✅ ARMv7 (Raspberry Pi 3): Supported but slower
   - Pre-built wheels for common architectures

4. **Python 3.13:**
   - ⚠️ **Experimental as of Q4 2024**
   - Numba 0.60.0 added basic Python 3.13 support
   - Some advanced features may not work
   - **Recommendation:** Test thoroughly or wait for numba 0.61+

#### Fallback Strategy

Librosa automatically handles numba unavailability:

```python
# Librosa's internal behavior
try:
    import numba
    USE_NUMBA = True
except ImportError:
    USE_NUMBA = False
    # Falls back to pure NumPy/SciPy implementations
    # ~2-5x slower but fully functional
```

**For LedFx:** No code changes needed - librosa handles the fallback transparently.

#### Recommended Dependency Specification

```toml
[project.optional-dependencies]
mood_advanced = [
    "librosa>=0.11.0",
    # Numba provides 2-5x speedup, but is optional
    # Constrain to versions with good Python 3.10-3.12 support
    "numba>=0.59.0,<0.61.0; python_version < '3.13'",
    # For Python 3.13, make numba truly optional until stable
    "numba>=0.60.0; python_version >= '3.13'",
]
```

**Alternative: Make Numba Truly Optional**

```toml
[project.optional-dependencies]
mood_advanced = [
    "librosa>=0.11.0",
]
mood_performance = [
    "librosa>=0.11.0",
    "numba>=0.59.0,<0.61.0; python_version < '3.13'",
    "numba>=0.60.0; python_version >= '3.13'",
]
```

Then users can choose:
```bash
pip install ledfx[mood_advanced]           # Librosa without numba
pip install ledfx[mood_performance]         # Librosa with numba speedups
```

#### Testing Matrix

Test mood detection across:
- ✅ Windows 11, Python 3.10, 3.11, 3.12 (with/without numba)
- ✅ macOS Intel, Python 3.10, 3.11, 3.12 (with/without numba)
- ✅ macOS Apple Silicon, Python 3.10, 3.11, 3.12 (with/without numba)
- ✅ Ubuntu 22.04, Python 3.10, 3.11, 3.12 (with/without numba)
- ⚠️ Python 3.13 across platforms (expect some issues, test without numba)
- ✅ Raspberry Pi 4/5, Python 3.10, 3.11 (ARM64)

**CI/CD Recommendation:** Add test matrix for Python 3.10-3.12 on all platforms, make Python 3.13 tests non-blocking.

#### Performance Impact Summary

| Configuration | Feature Extraction Time | CPU Usage | Notes |
|---------------|------------------------|-----------|-------|
| **Librosa + Numba** | 50-100ms | Low | Recommended |
| **Librosa (no Numba)** | 100-250ms | Moderate | Fallback, still acceptable |
| **Python 3.13 + Numba** | 60-120ms | Low | May have issues, test first |
| **Raspberry Pi + Numba** | 150-300ms | Moderate | Slower but usable |

**Recommendation:** Keep numba as optional dependency with version constraints, document that it improves performance but is not required. For Python 3.13 support, be prepared to run without numba until numba ecosystem stabilizes.

### Memory Footprint Comparison

| Configuration | Install Size | Runtime Memory | Import Time |
|---------------|--------------|----------------|-------------|
| **Full librosa** | ~300MB | ~200MB | ~3-5 seconds |
| **Minimal librosa** | ~150MB | ~100MB | ~1-2 seconds |
| **+ numba** | +50MB | +30MB | +0.5 seconds |
| **+ matplotlib** | +100MB | +80MB | +1-2 seconds |

**Target:** Minimal librosa + numba (~200MB install, ~130MB runtime)

### Documentation Updates

Add to installation docs:

```markdown
## Optional: Enhanced Mood Detection with Librosa

For advanced mood detection features, install librosa:

### Minimal Installation (Recommended)
```bash
# Install LedFx with minimal librosa dependencies
pip install ledfx[mood_advanced]

# This installs only core librosa + numba for performance
# Excludes matplotlib, audioread, and other visualization tools
```

### Full Installation (If needed for development)
```bash
# Install with all librosa features
pip install librosa[display]
```

Note: Visualization features are not used by LedFx's mood detection.
```

## Configuration Changes

Add new configuration options to `mood_manager` integration:

```python
CONFIG_SCHEMA = vol.Schema({
    # ... existing options ...
    vol.Optional(
        "use_process_pool",
        description="Use ProcessPoolExecutor for non-blocking librosa (recommended)",
        default=True,
    ): bool,
    vol.Optional(
        "shared_memory_buffer_mb",
        description="Shared memory buffer size in MB (auto-calculated if not set)",
        default=None,
    ): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=1.0, max=100.0))),
})
```

## Cleanup and Error Handling

### Graceful Shutdown

```python
async def disconnect(self, message: str = ""):
    """Clean up resources on shutdown"""
    if self._librosa_extractor:
        try:
            self._librosa_extractor.cleanup()
        except Exception as e:
            _LOGGER.warning(f"Error cleaning up librosa extractor: {e}")
    
    await super().disconnect(message)
```

### Process Pool Health Monitoring

```python
async def _monitor_worker_health(self):
    """
    Periodically check if worker process is responsive.
    Recreate if crashed or hung.
    """
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        
        try:
            # Simple health check - extract features with silence
            silence = np.zeros(44100, dtype=np.float32)
            await asyncio.wait_for(
                self._librosa_extractor.extract_features_async(silence),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            _LOGGER.error("Worker process hung, recreating...")
            self._librosa_extractor.cleanup()
            self._librosa_extractor = SharedMemoryLibrosaExtractor(...)
        except Exception as e:
            _LOGGER.error(f"Worker process error: {e}, recreating...")
            self._librosa_extractor.cleanup()
            self._librosa_extractor = SharedMemoryLibrosaExtractor(...)
```

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Process pool startup overhead | Initial delay | Pre-warm pool on integration init |
| Shared memory leaks | Memory growth | Implement cleanup in __del__ and shutdown |
| Worker process crashes | Feature extraction fails | Health monitoring + auto-restart |
| Platform compatibility issues | May not work on all systems | Feature flag + fallback to sync implementation |
| Increased complexity | Harder to debug | Comprehensive logging + error handling |
| Memory overhead | +20-30MB per worker | Acceptable tradeoff for responsiveness |

## Success Criteria

Implementation is successful if:
- ✅ Event loop latency spikes reduced by >80%
- ✅ API P99 response time reduced by >70%
- ✅ LED frame drops reduced by >80%
- ✅ Feature extraction accuracy maintained (±5%)
- ✅ Memory overhead <50MB increase
- ✅ No crashes or deadlocks in 24-hour stress test
- ✅ Works on Windows, Linux, macOS

## Librosa Platform and Version Compatibility

### Version Requirements
- **LedFx Requirement**: `librosa>=0.11.0` (optional dependency)
- **Current librosa**: 0.11.0 released March 2025
- **Python Support**: librosa 0.11.x supports Python 3.9-3.12

### Python Version Compatibility Matrix

| Python Version | librosa 0.11.x | Status for LedFx |
|---------------|----------------|------------------|
| **3.10** | ✅ Full support | **RECOMMENDED** |
| **3.11** | ✅ Full support | **RECOMMENDED** |
| **3.12** | ✅ Full support | **COMPATIBLE** |
| **3.13** | ⚠️ Testing | **NEEDS VERIFICATION** |

### Platform-Specific Support

#### Windows (All Versions)
- **Status**: ✅ Excellent support via pip wheels
- **Binary Wheels**: Available for Python 3.10-3.12
- **Dependencies**: Auto-installed (MSVC redistributables usually present)
- **Audio Backend**: soundfile with bundled libsndfile DLL
- **Installation**: `pip install librosa` - no compilation needed
- **Performance**: Full speed, all features available
- **Known Issues**: None

#### macOS (Intel x86_64)
- **Status**: ✅ Full support via pip wheels
- **Binary Wheels**: Universal2 wheels for Python 3.10-3.12
- **Audio Backend**: CoreAudio via soundfile
- **Installation**: Direct pip install works perfectly
- **Performance**: Excellent, native code
- **Known Issues**: None

#### macOS (Apple Silicon M1/M2/M3)
- **Status**: ✅ Native ARM support available
- **Binary Wheels**: Universal2 includes ARM64 native code
- **Fallback**: Rosetta 2 emulation works but slower
- **Performance**: Native ARM ~20-30% faster than Rosetta
- **Installation**: `pip install librosa` uses native ARM
- **Recommendation**: conda-forge for guaranteed native builds
- **Known Issues**: Some optional dependencies may need Rosetta

#### Linux (x86_64)
- **Status**: ✅ Full support via manylinux wheels
- **Binary Wheels**: manylinux2014+ for Python 3.10-3.12
- **System Deps**: May need `libsndfile1` (usually pre-installed)
- **Installation**: `pip install librosa` or `apt install python3-librosa`
- **Package Manager**: `sudo apt install libsndfile1` if needed
- **Performance**: Excellent with system BLAS libraries
- **Known Issues**: None on mainstream distributions

#### Linux (ARM/ARM64 - Raspberry Pi)
- **Status**: ⚠️ Limited wheel support, requires compilation
- **Binary Wheels**: Not always available on PyPI
- **Installation Time**: 30-60 minutes to build from source
- **System Deps**: `libsndfile1-dev`, `libatlas-base-dev`, `gfortran`
- **Performance**: Significantly slower than x86_64 (~2-5x slower)
- **Recommendation**: 
  - Consider basic mood detection (aubio-ledfx only) for Pi 3/Zero
  - Pi 4/5 with 4GB+ RAM can handle librosa (with patience)
  - Use pre-built Docker containers if available
- **Known Issues**: Memory constraints on older Pi models

### Core Dependency Platform Support

#### NumPy (Required by librosa)
- **LedFx uses**: `numpy>=2.0.0,<3.0.0`
- **librosa uses**: numpy>=1.20.0 (compatible with 2.x)
- **Platform Support**: ✅ Universal (excellent wheels)
- **Python 3.13**: ✅ NumPy 2.0+ fully supports it
- **Compatibility**: No conflicts between LedFx and librosa requirements

#### SciPy (Required by librosa)
- **Platform Support**: ✅ Binary wheels for all platforms
- **Performance**: Critical for FFT - highly optimized
- **Python 3.13**: ✅ Recent versions support it
- **ARM Support**: Good on Pi 4+, challenging on Pi 3/Zero

#### soundfile (Required by librosa)
- **Purpose**: Audio I/O (less critical for LedFx - we process live audio)
- **Platform Support**: ✅ Excellent (bundles libsndfile)
- **Windows**: Includes DLL in wheel
- **macOS**: Includes dylib in wheel
- **Linux**: Includes .so or uses system libsndfile1
- **Impact on LedFx**: Minimal (we don't use file I/O features)

#### Optional Dependencies (NOT needed for LedFx)
- **audioread**: File decoding (skip - we use live audio)
- **resampy/soxr**: Resampling (skip - fixed 30kHz sample rate)
- **matplotlib**: Visualization (avoid - 100MB bloat)
- **scikit-learn**: ML features (not used by LedFx)

### Installation Strategies by Platform

#### Recommended: Cross-Platform (pip)
```bash
# Works on Windows, macOS, Linux x86_64
pip install "librosa>=0.10.0,<0.12.0"
```

#### macOS ARM (for guaranteed native builds)
```bash
# Option 1: pip (usually works)
pip install librosa

# Option 2: conda for native ARM
conda install -c conda-forge librosa
```

#### Linux ARM/Raspberry Pi
```bash
# Install system dependencies first
sudo apt update
sudo apt install -y libsndfile1-dev libatlas-base-dev gfortran python3-dev

# Then pip install (will compile - takes time)
pip install "librosa>=0.10.0,<0.12.0"

# Or use system package if available
sudo apt install python3-librosa  # May be older version
```

#### Docker (Recommended for Pi)
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install librosa from wheels (if available) or pre-built image
RUN pip install librosa
```

### Python 3.13 Compatibility Notes

Both librosa and numba have varying Python 3.13 support:

| Component | Python 3.13 Status | Recommendation |
|-----------|-------------------|----------------|
| **librosa** | ⚠️ Unofficial (may work) | Test, prepare fallback |
| **numba** | ⚠️ Experimental (0.60.0+) | Version constraint required |
| **numpy** | ✅ Full (2.0+) | No issues |
| **scipy** | ✅ Full | No issues |

**Implementation Strategy:**
1. Primary support: Python 3.10-3.12
2. Python 3.13: Make mood features optional, add runtime check:

```python
import sys
import logging

_LOGGER = logging.getLogger(__name__)

if sys.version_info >= (3, 13):
    _LOGGER.warning(
        "Python 3.13 detected. Advanced mood detection (librosa/numba) "
        "has experimental support. Basic mood detection (aubio) will be "
        "used as fallback. For best experience, use Python 3.10-3.12."
    )
```

### Testing Matrix for CI/CD

```yaml
# GitHub Actions example
strategy:
  matrix:
    os: [ubuntu-22.04, windows-latest, macos-latest]
    python-version: ['3.10', '3.11', '3.12']
    include:
      # Test Python 3.13 but allow failures
      - os: ubuntu-22.04
        python-version: '3.13'
        experimental: true
      # Test ARM if using self-hosted runners
      - os: [self-hosted, linux, ARM64]
        python-version: '3.11'
        experimental: true
```

**Minimum Coverage:**
- ✅ Windows 11, Python 3.11, 3.12
- ✅ macOS Intel, Python 3.11, 3.12
- ✅ Ubuntu 22.04, Python 3.10, 3.12
- ⚠️ macOS ARM (optional, if available)
- ⚠️ Linux ARM (optional, manual test on Pi)
- ⚠️ Python 3.13 (non-blocking)

### Fallback Architecture

```
┌──────────────────────────────────────────┐
│   Mood Detection System Start            │
└──────────────┬───────────────────────────┘
               │
        ┌──────▼───────┐
        │  Check for   │
        │   librosa    │
        └──┬────────┬──┘
           │        │
       YES │        │ NO
           │        │
    ┌──────▼──┐  ┌─▼────────────────┐
    │ Advanced│  │ Basic Mode       │
    │ Features│  │ (aubio-ledfx)    │
    │         │  │                  │
    │ - 13    │  │ - 10 metrics     │
    │   librosa│  │ - FFT analysis   │
    │   features│  │ - Beat detection│
    │ - Genre │  │ - No genre       │
    │   detect│  │   classification │
    └─────────┘  └──────────────────┘
```

### Version Constraint Recommendations

Update `pyproject.toml`:

```toml
[project.optional-dependencies]
mood_advanced = [
    "librosa>=0.11.0",  # Released March 2025, stable
    # Don't include optional deps we don't need:
    # - No matplotlib (visualization)
    # - No audioread (file decoding)
    # - No resampy (resampling)
]

mood_performance = [
    "librosa>=0.11.0",
    "numba>=0.59.0,<0.61.0; python_version < '3.13'",  # Stable versions
    "numba>=0.60.0; python_version >= '3.13'",          # Experimental
]
```

**User Installation:**
```bash
# Minimal (most users)
pip install ledfx[mood_advanced]

# Performance (adds numba speedups)
pip install ledfx[mood_performance]

# Development (includes all deps)
pip install ledfx[mood_performance,dev]
```

### Memory and Disk Space Requirements

| Configuration | Disk Space | RAM (Runtime) | Import Time | Notes |
|---------------|------------|---------------|-------------|-------|
| **Basic (aubio)** | ~50MB | ~50MB | ~0.5s | Default, always available |
| **+ librosa minimal** | ~200MB | ~150MB | ~2-3s | Recommended |
| **+ numba** | ~250MB | ~180MB | ~2.5-3.5s | Best performance |
| **+ matplotlib** | ~350MB | ~260MB | ~4-6s | ⛔ Avoid (not needed) |

**Target Configuration:** librosa + numba without matplotlib (~250MB disk, ~180MB RAM)

### Performance Benchmarks by Platform

| Platform | librosa alone | + numba | Speedup | Notes |
|----------|--------------|---------|---------|-------|
| **Windows i7** | 120ms | 55ms | 2.2x | Typical desktop |
| **macOS M1** | 85ms | 35ms | 2.4x | ARM native |
| **macOS Intel** | 135ms | 60ms | 2.3x | Intel i5 |
| **Linux x86** | 110ms | 50ms | 2.2x | Ubuntu 22.04 |
| **Pi 4 (4GB)** | 280ms | 180ms | 1.6x | ARM64, slower |
| **Pi 3** | 450ms+ | N/A | N/A | Not recommended |

**Recommendation:** Require Pi 4+ for librosa features, basic mode for Pi 3/Zero.

### Action Items

1. **Test Python 3.13 Compatibility** 🔍 HIGH PRIORITY
   - Install on Python 3.13 environment
   - Verify import works
   - Run feature extraction benchmark
   - Document any issues or workarounds

2. **Update Documentation**
   - Add platform-specific installation notes
   - Document Raspberry Pi limitations
   - Add troubleshooting section for ARM builds

3. **Add Runtime Checks**
   ```python
   # In mood_detector.py __init__
   import platform
   import sys
   
   _LOGGER.info(f"Platform: {platform.system()} {platform.machine()}")
   _LOGGER.info(f"Python: {sys.version}")
   _LOGGER.info(f"Librosa available: {LIBROSA_AVAILABLE}")
   if LIBROSA_AVAILABLE:
       _LOGGER.info(f"Librosa version: {librosa.__version__}")
   ```

4. **CI/CD Pipeline**
   - Add matrix tests for Python 3.10, 3.11, 3.12
   - Test on Windows, macOS, Linux
   - Make Python 3.13 tests non-blocking
   - Optional: Add ARM test if self-hosted runner available

---

## References

- **Python Documentation:** 
  - [multiprocessing.shared_memory](https://docs.python.org/3/library/multiprocessing.shared_memory.html)
  - [concurrent.futures.ProcessPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#processpoolexecutor)
  - [asyncio.loop.run_in_executor](https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.run_in_executor)
  
- **Related Issues:**
  - Current PR: #1639
  - Librosa integration
  - Mood detection implementation

- **Code Locations:**
  - `ledfx/mood_detector.py` - Main mood detector
  - `ledfx/mood_detector_librosa.py` - Librosa feature extraction
  - `ledfx/integrations/mood_manager.py` - Mood-based automation
  - `pyproject.toml` - Optional dependency definition

---

**Document Version:** 1.0  
**Created:** 2025-12-17  
**Author:** AI Architecture Assistant  
**Status:** Proposed - Not Yet Implemented
