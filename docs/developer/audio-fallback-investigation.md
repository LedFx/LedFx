# Audio Fallback Startup Failure Investigation

**Branch:** `audio_fallback`  
**PR:** [#1761 — Fix: audio fallback hardening](https://github.com/LedFx/LedFx/pull/1761)  
**Date:** 2026-04-06  
**Status:** Fix applied, awaiting user validation

---

## Problem Summary

On startup, when the user's config has an audio device that is unavailable (e.g. Oculus WDM-KS device [28]), the fallback to the default WASAPI Loopback device [17] also fails — even though manually selecting device [17] after startup works perfectly.

## Affected User Environment

- Windows, 42 audio devices enumerated
- Configured device: `[28] Windows WDM-KS: Input (OCULUSVAD Wave Speaker Headphone)` — not always available
- Default/fallback device: `[17] Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]`
- Multiple virtuals with active audio effects in config (at least one: `equalizer2d` on `panel`)

## Root Cause Analysis

### The failure sequence (per virtual with an audio effect):

1. `activate()` tries configured device [28] (WDM-KS)
2. **Fails** with `PortAudioError -9996: Invalid device`
3. Falls back to device [17] (WASAPI Loopback)
4. `InputStream()` constructor **succeeds** — "Audio source opened" is logged
5. `.start()` **fails** with: `'Failed to create capture pin: sr=44100,ch=2,bits=8,align=2'`
6. `deactivate()` is called, config unchanged
7. Next virtual's effect repeats the same cycle

### Key evidence — PortAudio state poisoning:

The `.start()` error message contains `bits=8,align=2` — these are **wrong format parameters**. The WASAPI Loopback device should use float32 (bits=32). The `bits=8` value strongly suggests that the failed WDM-KS device open left PortAudio's internal state corrupted, and the subsequent WASAPI stream inherited those poisoned parameters.

This explains why manual selection works: by the time the user manually picks device [17] through the UI, PortAudio has been through a clean reinit cycle (via `update_config()` → `deactivate()` → `activate()`).

### Why it repeats for each virtual:

Each virtual with an active audio effect calls `set_effect()` → `AudioReactiveEffect.activate()` → `subscribe()` → `AudioInputSource.activate()`. Since the stream is not active after the failure, each virtual triggers a fresh attempt. **This is expected and correct behavior** — each virtual legitimately tries to start audio if it's not running. The problem is solely that each attempt hits the same poisoned-state bug.

## Fix Applied

**File:** `ledfx/effects/audio.py`, in `_activate_inner()`

Added `sd._terminate()` / `sd._initialize()` between the primary device failure and the fallback attempt. This clears PortAudio's internal state so the fallback device gets a clean environment, matching what happens during manual device selection.

```python
# After primary device PortAudioError, before fallback:
sd._terminate()
sd._initialize()
```

## What Was NOT Changed

- No retry cap or consecutive failure limiting — the repeated attempts per-virtual are correct behavior, not a retry storm
- No delays added — the issue is state corruption, not timing
- Audio device monitor remains disabled for diagnostics (separate investigation)

## Remaining Questions

1. **Does the reinit fix actually resolve the user's startup failure?** — Needs user testing
2. **Should we also reinit after the OSError path?** — Currently only the PortAudioError path gets reinit before fallback. OSError just deactivates without fallback.
3. **Is there a scenario where `sd._terminate()` / `sd._initialize()` could cause issues if another thread is using sounddevice?** — The `_activating` re-entry guard and the fact that only one stream can be active at a time should protect against this, but worth monitoring.
4. **Should the audio device monitor be re-enabled?** — Currently disabled with `return` at top of `_start_audio_device_monitor()`. Separate from this issue.

## How to Reproduce (approximate)

1. Configure an audio device that will fail to open (e.g. a virtual/Bluetooth device that's sometimes unavailable)
2. Have multiple virtuals with audio-reactive effects in config
3. Start LedFx — all virtuals fail to start audio
4. Manually select the WASAPI Loopback device via UI — it works

## Key Files

- `ledfx/effects/audio.py` — `AudioInputSource._activate_inner()` contains the fix
- `ledfx/virtuals.py` — `create_from_config()` restores effects at startup, triggering audio activation
- `ledfx/core.py` — `async_start()` orchestrates the startup sequence
