# Audio Device Persistence Strategy

**Date:** 2026-04-07
**Status:** Strategy — not yet implemented
**Scope:** `ledfx/effects/audio.py`, `ledfx/api/audio_devices.py`, `ledfx/config.py`

---

## Problem Statement

The audio device is persisted in `config.json` as an integer index only:

```json
{
    "audio": {
        "audio_device": 17
    }
}
```

Device indices are assigned by PortAudio/sounddevice during enumeration and are **not stable** across sessions. If a USB device is plugged in, a Bluetooth device pairs, or a driver updates between LedFx sessions, the enumeration order can shift. The saved index `17` may now point to a completely different device.

### Current Runtime Mitigation (Incomplete)

During a **running session**, `AudioInputSource` tracks the active device by name in the class variable `_last_device_name`. When device hotplug events occur, `handle_device_list_change()` uses `get_device_index_by_name()` to find the device at its new index. This works well within a session.

**The gap:** `_last_device_name` is a runtime-only class variable. It is **never persisted to `config.json`**. When LedFx exits and restarts, `_last_device_name` is `None`, so there is no name to match against. The system falls back to the raw integer index, which may now be wrong.

### Failure Scenario

1. User selects device `[17] Windows WASAPI: Speakers (Realtek) [Loopback]`
2. Config saves `{"audio_device": 17}`
3. LedFx exits
4. User plugs in a USB audio interface (or a Bluetooth device auto-connects)
5. On next enumeration, the USB device gets index 5, shifting everything above it up by 1
6. Index `17` now points to `Windows WASAPI: Microphone (Realtek)` instead of the loopback
7. LedFx starts, reads `audio_device: 17`, opens the wrong device
8. User gets no audio visualization or hears unexpected input

---

## Strategy: Persist Device Name Alongside Index

### Core Principle

Store the device name string as the **primary** identifier and the index as a **hint/cache**. On startup, resolve name → index. The index is only used as a fast path when the name still matches.

### 1. Config Schema Change

Add an `audio_device_name` field to the audio config:

```json
{
    "audio": {
        "audio_device": 17,
        "audio_device_name": "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]"
    }
}
```

The name format matches what `input_devices()` returns: `"{hostapi_name}: {device_name}"`. This is the same format already used by `_last_device_name` in the runtime tracking code (see `update_device_tracking()` in `_activate_inner()`).

### 2. Startup Resolution Logic

Add a new method or extend `device_index_validator()` with this resolution order:

```
1. If audio_device_name is set in config:
   a. If audio_device index is valid AND its name matches audio_device_name → use index (fast path)
   b. Else, search all input devices for audio_device_name using get_device_index_by_name()
      - If found → use the new index, update audio_device in config
      - If not found → fall through to step 2
2. If audio_device index is valid (but no name match) → use index (legacy/fallback)
3. Else → use default_device_index() (existing fallback logic)
```

### 3. Files to Modify

#### `ledfx/effects/audio.py`

**a. `AUDIO_CONFIG_SCHEMA` (line ~379)**
Add `audio_device_name` as an optional string field:
```python
vol.Optional("audio_device_name", default=""): str,
```

**b. `device_index_validator()` (line ~243)**
Expand to accept the full config dict (or create a new startup resolver) so it can read `audio_device_name` and perform name-based resolution before falling back to index validation.

Currently:
```python
@staticmethod
def device_index_validator(val):
    if val in AudioInputSource.valid_device_indexes():
        return val
    else:
        return AudioInputSource.default_device_index()
```

This validator only sees the integer value. The name-based resolution needs access to both `audio_device` and `audio_device_name`. Options:

- **Option A (Recommended):** Add a class method `resolve_device_at_startup(config) -> int` that implements the resolution logic above. Call it from `update_config()` or `__init__()` after schema validation, before `activate()`. Keep the existing validator as a simple range check.

- **Option B:** Use a voluptuous `All()` chain or custom validator that can access sibling config keys. This is more complex with voluptuous.

**c. `_update_device_config()` (line ~126)**
When updating the device index, also update the device name:
```python
def _update_device_config(self, device_idx):
    self._config["audio_device"] = device_idx
    # Also persist the device name for cross-session recovery
    devices = self.input_devices()
    if device_idx in devices:
        self._config["audio_device_name"] = devices[device_idx]
    # ... existing save logic
```

**d. `update_device_tracking()` inner function (line ~586)**
Already sets `_last_device_name` at runtime. No change needed unless we want to also sync to config here (but `_update_device_config` covers this).

**e. `update_config()` (line ~418)**
After schema validation and before `activate()`, call the new startup resolver:
```python
def update_config(self, config):
    if AudioInputSource._audio_stream_active:
        self.deactivate()
    self._config = self.AUDIO_CONFIG_SCHEMA.fget()(config)
    # Resolve device by name if available (handles index drift across restarts)
    self._resolve_device_from_name()
    # ... rest of method
```

#### `ledfx/api/audio_devices.py`

**a. `put()` handler (line ~40)**
When the user selects a device via the API, persist the name alongside the index:
```python
new_config["audio_device"] = int(index)
# Persist device name for cross-session recovery
devices = AudioInputSource.input_devices()
if index in devices:
    new_config["audio_device_name"] = devices[index]
```

**b. `get()` handler**
Optionally include `audio_device_name` in the response for UI display/debugging.

#### `ledfx/config.py`

**Config migration (line ~629)**
The existing migration already handles legacy configs without `audio_device`. No new migration is strictly required since `audio_device_name` defaults to `""`, but consider adding a migration that populates `audio_device_name` if `audio_device` is set but `audio_device_name` is missing (best-effort: look up the name at migration time).

### 4. New Method: `_resolve_device_from_name()`

```python
def _resolve_device_from_name(self):
    """
    Resolve the audio device by name from config.
    Called at startup/config-update to handle index drift.

    Resolution order:
    1. Name match at saved index (fast path, no drift)
    2. Name match at different index (drift detected, update index)
    3. Saved index still valid but name doesn't match (use index, warn)
    4. Default device (nothing valid)
    """
    saved_name = self._config.get("audio_device_name", "")
    saved_idx = self._config.get("audio_device")

    if not saved_name:
        # No name stored (legacy config or first run) — use index as-is
        return

    devices = self.input_devices()

    # Fast path: saved index exists and name matches
    if saved_idx in devices and devices[saved_idx] == saved_name:
        _LOGGER.debug(
            "Audio device '%s' confirmed at index %s",
            saved_name, saved_idx
        )
        return

    # Name-based search (index has drifted)
    found_idx = self.get_device_index_by_name(saved_name)

    if found_idx != -1:
        _LOGGER.info(
            "Audio device '%s' moved from index %s to %s (enumeration changed)",
            saved_name, saved_idx, found_idx
        )
        self._config["audio_device"] = found_idx
        # Persist the corrected index
        if hasattr(self, "_ledfx") and self._ledfx:
            self._ledfx.config["audio"] = self._config
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
        return

    # Device not found by name at all
    _LOGGER.warning(
        "Saved audio device '%s' not found in current device list. "
        "Falling back to index %s if valid, else default.",
        saved_name, saved_idx
    )
    # Clear the stale name so we don't keep warning
    self._config["audio_device_name"] = ""
```

### 5. Edge Cases

| Scenario | Behavior |
|---|---|
| Legacy config (no `audio_device_name`) | Falls through to existing index-based logic. No regression. |
| Device removed permanently | Name search fails, index check fails, falls back to default. Name cleared from config. |
| Device name truncated by PortAudio | `get_device_index_by_name()` already handles partial matching. |
| Multiple devices with similar names | Exact match preferred, then longest partial match (existing logic). |
| User manually edits config.json | Works as long as name string matches `input_devices()` format. |
| WEB AUDIO / SENDSPIN devices | These also use the `"{hostapi}: {name}"` format via `input_devices()`. No special handling needed. |
| Config saved on Windows, loaded on Linux | Host API names differ (`Windows WASAPI` vs `ALSA`). Name won't match, falls back to default. This is expected and correct. |

### 6. Migration Path — Legacy Upgrade Strategy

This is a **non-breaking, additive change**. Users upgrading from any prior version will have configs with only `audio_device` (integer index) and no `audio_device_name` field.

#### Upgrade Flow (Seamless)

1. User upgrades LedFx to the version with this feature
2. LedFx starts, loads `config.json` with `{"audio": {"audio_device": 17}}`
3. Schema validation adds `audio_device_name` with default `""`
4. `_resolve_device_from_name()` sees empty name → **skips name resolution entirely**
5. Existing `device_index_validator` handles index `17` as before — **no change in behavior**
6. Device activates at index `17` (taken at face value)
7. `_activate_inner()` calls `update_device_tracking()` → sets `_last_device_name` at runtime
8. **Key step:** `_update_device_config()` (or post-activation hook) writes the device name back:
   ```json
   {"audio": {"audio_device": 17, "audio_device_name": "Windows WASAPI: Speakers (Realtek) [Loopback]"}}
   ```
9. Config is saved to disk — **config is now upgraded for all future sessions**
10. From the next restart onward, name-based resolution is active

#### Critical Design Constraint

The name must be persisted on the **first successful activation** after upgrade, not only on user-initiated device changes via the API. This means `_update_device_config()` or `update_device_tracking()` must write `audio_device_name` to config and save on every activation where the name is missing or has changed. Without this, a user who never touches the audio settings would never get their config upgraded.

#### Implementation Detail

Add to the end of `_activate_inner()`, after `update_device_tracking()` succeeds:

```python
# Ensure device name is persisted for cross-session recovery
# This also handles seamless upgrade from legacy configs (index-only)
with AudioInputSource._class_lock:
    current_name = AudioInputSource._last_device_name
if current_name and self._config.get("audio_device_name", "") != current_name:
    self._config["audio_device_name"] = current_name
    if hasattr(self, "_ledfx") and self._ledfx:
        self._ledfx.config["audio"] = self._config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        _LOGGER.info(
            "Persisted audio device name '%s' for cross-session recovery",
            current_name,
        )
```

#### Summary

- `audio_device_name` defaults to `""` — existing configs load without error
- Legacy index is trusted at face value on first boot after upgrade
- Name is auto-populated on first successful activation
- The integer `audio_device` field is never removed — it remains the fast path and fallback
- Zero user interaction required for the upgrade

### 7. Testing Strategy

All tests should live in `tests/test_audio_device_persistence.py`. Tests mock `AudioInputSource.input_devices()` and `AudioInputSource.default_device_index()` to simulate different device enumeration states without requiring real audio hardware.

#### 7.1 Mock Fixtures

```python
# Standard device list — the "before" state
DEVICES_BEFORE = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    17: "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]",
    22: "Windows WASAPI: Headset (Bluetooth)",
}

# After a USB device is plugged in — indices shift
DEVICES_AFTER_USB_ADDED = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    3: "Windows WASAPI: USB Audio Interface",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    18: "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]",
    23: "Windows WASAPI: Headset (Bluetooth)",
}

# After device is removed entirely
DEVICES_AFTER_REMOVAL = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    22: "Windows WASAPI: Headset (Bluetooth)",
}

# Truncated names (PortAudio sometimes truncates long names)
DEVICES_TRUNCATED = {
    0: "Windows WASAPI: Microphone (Realtek High Def",
    17: "Windows WASAPI: Speakers (Realtek High Def",
}

# Multiple similar names
DEVICES_SIMILAR_NAMES = {
    0: "Windows WASAPI: Microphone",
    1: "Windows WASAPI: Microphone (Realtek)",
    2: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
}
```

#### 7.2 Unit Tests — `_resolve_device_from_name()`

These test the core resolution logic in isolation.

| # | Test Name | Config Input | Mock Devices | Expected Result |
|---|---|---|---|---|
| 1 | `test_resolve_name_matches_at_saved_index` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_BEFORE` | Index stays `17`, no config save |
| 2 | `test_resolve_name_found_at_different_index` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_AFTER_USB_ADDED` | Index updated to `18`, config saved |
| 3 | `test_resolve_name_not_found_device_removed` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_AFTER_REMOVAL` | Falls to default, name cleared from config |
| 4 | `test_resolve_empty_name_skips_resolution` | `idx=17, name=""` | `DEVICES_BEFORE` | Index stays `17`, no name search performed |
| 5 | `test_resolve_no_name_key_skips_resolution` | `idx=17` (no name key) | `DEVICES_BEFORE` | Index stays `17` (schema default `""` applied) |
| 6 | `test_resolve_partial_match_truncated_name` | `idx=17, name="...Speakers (Realtek High Def"` | `DEVICES_BEFORE` | Partial match finds index `17` via `get_device_index_by_name` |
| 7 | `test_resolve_prefers_exact_over_partial` | `idx=2, name="...Microphone (Realtek)"` | `DEVICES_SIMILAR_NAMES` | Exact match at `1`, not partial at `2` |
| 8 | `test_resolve_saved_index_invalid_name_found` | `idx=99, name="...Speakers...Loopback"` | `DEVICES_BEFORE` | Name search finds `17`, updates index |
| 9 | `test_resolve_saved_index_invalid_name_not_found` | `idx=99, name="Nonexistent Device"` | `DEVICES_BEFORE` | Falls to default device |
| 10 | `test_resolve_index_valid_but_wrong_device` | `idx=17, name="...Speakers...Loopback"` | `{17: "...Microphone...", 18: "...Speakers...Loopback"}` | Name mismatch at `17`, found at `18`, updates index |

#### 7.3 Unit Tests — Legacy Upgrade Path

These verify that upgrading from index-only configs works seamlessly.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 11 | `test_legacy_config_no_name_field` | Config `{"audio_device": 17}` loaded through schema | `audio_device_name` defaults to `""`, index `17` used as-is |
| 12 | `test_legacy_config_empty_audio_dict` | Config `{}` loaded through schema | Default device index chosen, no name resolution attempted |
| 13 | `test_legacy_upgrade_name_persisted_on_activation` | Config `{"audio_device": 17}`, activate succeeds | After activation, config contains `audio_device_name` matching device at index `17` |
| 14 | `test_legacy_upgrade_name_not_persisted_on_activation_failure` | Config `{"audio_device": 17}`, activate fails | `audio_device_name` remains `""` — don't persist a name for a device we couldn't open |
| 15 | `test_legacy_upgrade_second_startup_uses_name` | Simulate: first boot persists name, second boot with shifted indices | Second boot resolves by name to new index |

#### 7.4 Unit Tests — API Endpoint

These verify the REST API correctly persists both fields.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 16 | `test_api_put_persists_name_and_index` | PUT `{"audio_device": 5}` | Config saved with both `audio_device: 5` and `audio_device_name: "..."` |
| 17 | `test_api_put_invalid_index_rejected` | PUT `{"audio_device": 999}` | Error response, config unchanged |
| 18 | `test_api_get_returns_name` | GET with config containing name | Response includes `active_device_index` and `active_device_name` |

#### 7.5 Unit Tests — `_update_device_config()`

These verify the config save helper persists both fields.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 19 | `test_update_device_config_writes_name` | Call with valid `device_idx` | Both `audio_device` and `audio_device_name` set in config |
| 20 | `test_update_device_config_clears_name_for_invalid` | Call with `device_idx` not in `input_devices()` | `audio_device` set, `audio_device_name` cleared or unchanged |
| 21 | `test_update_device_config_saves_to_disk` | Call with `_ledfx` attached | `save_config()` called with updated config |

#### 7.6 Unit Tests — `handle_device_list_change()` Integration

These verify the runtime hotplug recovery still works correctly with the new name field.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 22 | `test_hotplug_recovery_uses_runtime_name` | Device shifts during session | `_last_device_name` used to find new index, config updated with both fields |
| 23 | `test_hotplug_device_removed_clears_name` | Device disappears during session | Falls to default, `_last_device_name` cleared, config name cleared |
| 24 | `test_hotplug_no_active_stream_no_crash` | Device change event with no active stream | No error, device list refreshed only |

#### 7.7 Unit Tests — `get_device_index_by_name()` Edge Cases

These validate the name matching logic that underpins resolution.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 25 | `test_exact_match_preferred` | Exact name exists in device list | Returns exact match index |
| 26 | `test_partial_match_stored_name_is_substring` | Stored name is truncated substring | Returns best (longest) partial match |
| 27 | `test_no_match_returns_negative_one` | Name doesn't match anything | Returns `-1` |
| 28 | `test_empty_string_returns_negative_one` | Empty string passed | Returns `-1` (no false matches) |
| 29 | `test_case_sensitive_matching` | Name differs only in case | Verify current behavior (case-sensitive) |
| 30 | `test_partial_match_avoids_false_positive` | `"Microphone"` should not match `"Microphone (Realtek)"` when stored name is shorter | Only matches when stored name is substring of device name, not reverse |

#### 7.8 Regression Guard Tests

These ensure the new code doesn't break existing behavior.

| # | Test Name | What It Guards |
|---|---|---|
| 31 | `test_schema_accepts_legacy_config_without_name` | Schema validation doesn't reject old configs |
| 32 | `test_schema_allows_extra_keys` | `ALLOW_EXTRA` still works (other audio config fields not lost) |
| 33 | `test_device_index_validator_unchanged_behavior` | Validator still returns default for invalid indices |
| 34 | `test_activate_still_works_without_name` | Full activation path works with `audio_device_name=""` |
| 35 | `test_config_roundtrip_preserves_all_fields` | Save → load cycle preserves both `audio_device` and `audio_device_name` |
| 36 | `test_web_audio_device_name_persisted` | WEB AUDIO virtual devices also get name persisted |
| 37 | `test_sendspin_device_name_persisted` | SENDSPIN devices also get name persisted |

#### 7.9 Test Implementation Notes

- **Mocking pattern:** Use `@patch.object(AudioInputSource, 'input_devices', return_value=DEVICES_BEFORE)` and `@patch.object(AudioInputSource, 'default_device_index', return_value=0)` to control device enumeration without real hardware.
- **Config save assertion:** Mock `save_config` and assert it was called with expected config dict. Use `@patch('ledfx.effects.audio.save_config')` or a mock `_ledfx` object with mock `config` and `config_dir`.
- **Activation mocking:** For tests that touch `activate()`, mock `open_audio_stream` to prevent actual PortAudio calls. Alternatively, test `_resolve_device_from_name()` in isolation (preferred).
- **Fixture for mock ledfx:** Create a simple mock with `config` dict and `config_dir` string to satisfy `_update_device_config()` requirements.
- **No real audio in CI:** All tests must pass without any audio hardware. Never call `sd.query_devices()` in tests.

### 8. Implementation Order

1. Add `audio_device_name` to `AUDIO_CONFIG_SCHEMA`
2. Add `_resolve_device_from_name()` method to `AudioInputSource`
3. Call resolver from `update_config()` before `activate()`
4. Update `_update_device_config()` to persist name
5. Update `audio_devices.py` PUT handler to persist name
6. Write tests
7. Manual verification with real device enumeration changes

---

## Appendix: Current Code References

| Component | File | Key Lines |
|---|---|---|
| Config schema | `ledfx/effects/audio.py` | ~379 (`AUDIO_CONFIG_SCHEMA`) |
| Index validator | `ledfx/effects/audio.py` | ~243 (`device_index_validator`) |
| Runtime name tracking | `ledfx/effects/audio.py` | ~45 (`_last_device_name`), ~586 (`update_device_tracking`) |
| Device list change handler | `ledfx/effects/audio.py` | ~140 (`handle_device_list_change`) |
| Name-based search | `ledfx/effects/audio.py` | ~771 (`get_device_index_by_name`) |
| Config update + save | `ledfx/effects/audio.py` | ~126 (`_update_device_config`) |
| API device selection | `ledfx/api/audio_devices.py` | ~40 (`put`) |
| Audio config in core schema | `ledfx/config.py` | ~145 |
| Audio init in core startup | `ledfx/core.py` | ~500 |
| Input device enumeration | `ledfx/effects/audio.py` | ~365 (`input_devices`) |
| Device activation | `ledfx/effects/audio.py` | ~456 (`_activate_inner`) |
