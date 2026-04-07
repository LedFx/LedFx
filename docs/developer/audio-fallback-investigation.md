# Audio Fallback Startup Failure Investigation

**Branch:** `audio_fallback`
**PR:** [#1761 — Fix: audio fallback hardening](https://github.com/LedFx/LedFx/pull/1761)
**Date:** 2026-04-06
**Status:** Fix v3 confirmed working — no delays needed, reinit only (2026-04-06)

---

## Problem Summary

On startup, the WASAPI Loopback audio device [17] fails to start — even though manually selecting the same device from the UI after startup works perfectly. PortAudio's internal state appears poisoned at application startup, likely by problematic WDM-KS devices (Oculus, Bluetooth) interfering during initial device enumeration.

## Affected User Environment

- Windows, 42 audio devices enumerated
- Includes problematic WDM-KS devices: OCULUSVAD, Bluetooth HF Audio (Galaxy Tab E, iPhone, Dads iPhone)
- Configured/default device: `[17] Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]`
- Multiple virtuals with active audio effects in config (at least: `equalizer2d` on `panel`)

## Log Evidence

### Log 1 (2026-04-06 16:02) — Original code, configured=[28] WDM-KS

1. Device [28] (WDM-KS OCULUSVAD) fails: `PortAudioError -9996: Invalid device`
2. Fallback to [17] (WASAPI Loopback): `InputStream()` succeeds, `.start()` fails with `bits=8,align=2`
3. `bits=8` = wrong format (should be float32=bits=32) → WDM-KS poisoned PortAudio state
4. Repeats per virtual, all fail identically

### Log 2 (2026-04-06 20:10) — After reinit fix, configured=[17] WASAPI Loopback

**Critical new finding**: User has since changed config to device [17] directly. No WDM-KS device [28] is involved at all.

1. Device [17] is tried as first/only device (configured == default == 17)
2. `InputStream()` succeeds ("Audio source opened") but `.start()` fails
3. Error: `'GetNameFromCategory: usbTerminalGUID = 7D1E' [Windows WDM-KS error -9999]`
4. A WASAPI device is failing with a **WDM-KS** error — PortAudio is already poisoned at startup
5. Our fallback reinit code was never reached (early-exit: `device_idx == default_device`)
6. Repeats per virtual, all fail identically, no reinit ever attempted

## Root Cause Analysis

PortAudio's initial `_initialize()` enumerates all system devices. On this user's machine, problematic WDM-KS devices (Oculus virtual audio, Bluetooth HF devices) poison the internal state during this enumeration. The `usbTerminalGUID = 7D1E` error string confirms WDM-KS is leaking into WASAPI operations.

**Why manual selection works**: By the time a user interacts with the UI, the `update_config()` path calls `deactivate()` → `activate()`. The deactivate/activate cycle, combined with the time delay, allows PortAudio to recover. The key insight is that the state is poisoned from PortAudio's very first initialization, not from a prior failed device open.

### Why it repeats for each virtual:

Each virtual with an audio effect calls `subscribe()` → `activate()`. Since the stream is not active after the failure, each virtual triggers a fresh attempt. **This is expected and correct behavior** — each virtual legitimately tries to start audio if it's not running.

## Fix Applied (v2)

**File:** `ledfx/effects/audio.py`, in `_activate_inner()`

Two PortAudio reinit points added:

### 1. When configured == default device fails (NEW — addresses Log 2)
```python
if device_idx == default_device:
    self.deactivate()
    sd._terminate()
    sd._initialize()
    # Retry same device after reinit
    open_audio_stream(device_idx)
```

### 2. Between primary failure and fallback attempt (addresses Log 1)
```python
# configured != default, configured fails, try fallback after reinit
sd._terminate()
sd._initialize()
open_audio_stream(default_device)
```

## Startup vs Manual Selection — Path Comparison

### Startup path (fails):

1. `virtuals.create_from_config()` → `set_effect()` → `AudioReactiveEffect.activate()`
2. Creates `AudioAnalysisSource(ledfx, config)` → `__init__` → `update_config(config)`
3. `update_config`: `_callbacks` is empty, so **`activate()` is NOT called**
4. `AudioAnalysisSource.__init__` calls `subscribe()` 6 times for analysis functions
5. First `subscribe()` sees `_callbacks > 0`, `_audio_stream_active == False` → calls `activate()`
6. `activate()` tries device → fails (PortAudio poisoned from init) → `deactivate()`
7. Each subsequent `subscribe()` and virtual's effect repeats the same cycle

### Manual API path (works):

1. `PUT /api/audio/devices` with `audio_device=17`
2. Calls `self._ledfx.audio.update_config(new_config)`
3. `update_config()`: **`deactivate()` is called first** — cleans up state
4. Time has passed since startup — WDM-KS resources released
5. `activate()` tries device [17] → succeeds from clean state

### Critical differences:

1. **PortAudio state at startup is poisoned from initial enumeration** — WDM-KS devices interfere during `sd._initialize()`. Manual path runs later when state has recovered.
2. **`deactivate()` before `activate()`**: `update_config()` always calls `deactivate()` first. Startup's first `subscribe()` → `activate()` has no prior `deactivate()`.
3. **Timing**: Manual selection happens seconds/minutes after startup, giving PortAudio/WDM-KS time to fully release resources.

## What Was NOT Changed

- No retry cap or consecutive failure limiting — repeated per-virtual attempts are correct behavior
- `core.py` and `virtuals.py` — zero diff vs main (all diagnostic changes reverted)
- Audio device monitor — re-enabled (was temporarily disabled for diagnostics)

## Confirmed Results (Log 3: 2026-04-06 20:43)

The fix works:

1. **20:43:46.538** — Device [17] fails on first attempt: `usbTerminalGUID = 7D1E` (same poisoned state)
2. **20:43:46.540** — Reinit triggered: `sd._terminate()` → `sd._initialize()`
3. **20:43:48.610** — Retry succeeds: "Device opened successfully after reinit"
4. **All subsequent virtuals** (panel-mask, panel-background, panel-foreground, ceiling) restore effects with no further audio failures

**Key**: `sd._terminate()` → `sd._initialize()` alone is sufficient — no `time.sleep()` calls needed.

## Remaining Questions

1. **Should the audio device monitor be re-enabled?** — Separate from this issue

## Fix v3 — Delays Removed, Confirmed Working (2026-04-06)

Removed all four `time.sleep(1)` calls from both reinit paths. The `sd._terminate()` → `sd._initialize()` cycle alone is sufficient — no artificial delays needed. User testing confirmed successful.

### Sleep calls — proven unnecessary

The initial v2 fix included `time.sleep(1)` after both `sd._terminate()` and `sd._initialize()` (4 calls total across both reinit paths). Testing proved these are not required:

- The PortAudio reinit (`_terminate` → `_initialize`) synchronously resets internal state
- No asynchronous OS-level cleanup requires waiting
- Removing all sleeps had no effect on fix reliability
- All 773 tests pass without any sleep calls

### Diagnostic code — reverted

All `[AUDIO-DIAG]` diagnostic logging and temporary changes in `core.py` and `virtuals.py` have been reverted:

- Removed `_audio_startup_phase` and `_startup_mono` tracking attributes from `LedFxCore.__init__`
- Re-enabled the audio device monitor in `_start_audio_device_monitor()` (was disabled with early `return`)
- Removed `[AUDIO-DIAG]` log from `_on_audio_devices_changed()`
- Removed startup phase completion log after `create_from_config()`
- Removed `[AUDIO-DIAG]` effect restore logging from `virtuals.py`

These files now have zero diff vs main — only `ledfx/effects/audio.py` contains the actual fix.

### Final PR candidate:
- Stripped all `[AUDIO-DIAG]` diagnostic logging
- Removed `describe_device()` utility (only used by diagnostics)
- Removed all `time.sleep()` calls (proven unnecessary)
- Reverted all diagnostic changes in `core.py` and `virtuals.py`
- Kept: re-entry guard, both reinit paths, improved error messages, device name tracking

## Key Files

- `ledfx/effects/audio.py` — `AudioInputSource._activate_inner()` contains the fix
- `ledfx/virtuals.py` — `create_from_config()` restores effects at startup
- `ledfx/core.py` — `async_start()` orchestrates startup
- `ledfx/api/audio_devices.py` — Manual device selection API (the path that works)
