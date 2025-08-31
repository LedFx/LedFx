# Particle Debug System Implementation

## Summary

Successfully added debug logging to both flame effects to report particle counts on a 1-second interval basis.

## Changes Made

### 1. flame2d.py (Python Implementation)
- **Added imports**: `import time` for time tracking
- **Added debug variables**:
  - `self._debug_last_report = 0.0` - tracks last report time
  - `self._debug_report_interval = 1.0` - report every 1 second
- **Added debug reporting** in `draw()` method:
  - Reports particle counts for Low, Mid, High bands
  - Reports total particle count
  - Only reports every 1 second to avoid spam

### 2. rust_effects/src/lib.rs (Rust Implementation)
- **Added function**: `get_flame_particle_counts()`
  - Returns `Vec<usize>` with counts for [Low, Mid, High] bands
  - Safely accesses the global FLAME_STATE
  - Returns [0, 0, 0] if no state exists
- **Exported function** in `ledfx_rust_effects` module

### 3. rusty2d.py (Python Wrapper for Rust)
- **Added debug variables** in `__init__()`:
  - `self._debug_last_report = 0.0`
  - `self._debug_report_interval = 1.0`
- **Added debug reporting** in `_draw_rust()` method:
  - Only reports for flame effect (not bars effect)
  - Calls `ledfx_rust_effects.get_flame_particle_counts()`
  - Reports every 1 second with error handling

## Debug Output Format

### flame2d.py (Python)
```
DEBUG - Flame2D particles - Low: 424, Mid: 396, High: 433, Total: 1253
```

### rusty2d.py (Rust)
```
DEBUG - RustyFlame particles - Low: 424, Mid: 396, High: 433, Total: 1253
```

## Usage

To see the debug output when running LedFx:

```bash
python -m ledfx -vv --offline --open-ui
```

The `-vv` flag enables DEBUG level logging, which will show the particle count reports every 1 second when either flame effect is active.

## Technical Details

### Python Implementation (flame2d.py)
- Uses existing `self._counts` dictionary to track live particles per band
- Reports are generated after particle processing but before blur/finalization
- Uses `time.time()` to track 1-second intervals

### Rust Implementation (rusty2d.py + lib.rs)
- Rust function safely accesses global `FLAME_STATE` particle storage
- Python wrapper calls Rust function and handles any potential errors
- Particle counts reflect the actual Vec lengths for each band

### Performance Impact
- Minimal: Debug reporting only happens once per second
- No performance impact during normal frame rendering
- Safe error handling prevents crashes if debug functions fail

## Verification

Both systems have been tested and verified to:
1. ✅ Report particle counts correctly
2. ✅ Update counts as particles spawn and die
3. ✅ Report every 1 second (not every frame)
4. ✅ Handle errors gracefully
5. ✅ Show distinct logs for Python vs Rust implementations

The particle debug system is now fully operational for both flame effects!
