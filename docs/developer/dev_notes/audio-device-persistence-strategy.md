# Audio Device Persistence Strategy

**Date:** 2026-04-07
**Status:** Strategy — implemented
**Scope:** `ledfx/effects/audio.py`, `ledfx/api/audio_devices.py`, `ledfx/api/config.py`, `ledfx/config.py`

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
      - If found → use the new index, update audio_device in config, persist
      - If not found → reset audio_device to default_device_index(), clear
        audio_device_name and runtime tracking (_last_device_name, _last_active),
        persist
2. If audio_device_name is empty (legacy config or first run) → use audio_device index as-is
3. Downstream validator / _activate_inner() handles any remaining invalid indices
```

### 3. Files Modified

#### `ledfx/effects/audio.py`

- **`AUDIO_CONFIG_SCHEMA`** — Added `audio_device_name` as an optional string field (default `""`).
- **`_resolve_device_from_name()`** — New method implementing the resolution algorithm from §2. Called from `update_config()` after schema validation, before `activate()`.
- **`_update_device_config()`** — Updated to persist both `audio_device` (index) and `audio_device_name` (string) together, then save to disk.
- **`update_device_tracking()`** (inner function in `_activate_inner()`) — Unchanged; still sets `_last_device_name` at runtime.
- **`persist_device_name_if_needed()`** (inner function in `_activate_inner()`) — Post-activation hook that syncs both config keys (`audio_device`, `audio_device_name`) to match the actually-opened device. Handles legacy upgrade (first activation after upgrade auto-populates name) and fallback-open scenarios (configured device fails, default opens instead).
- **`update_config()`** — Calls `_resolve_device_from_name()` after schema validation, before `activate()`.
- **`_persist_config()`** — Helper that syncs `self._config` to central config and writes to disk. Used by all persistence paths.

#### `ledfx/api/audio_devices.py`

- **PUT handler** — Persists `audio_device_name` alongside `audio_device` when the user selects a device via the API.
- **GET handler** — Returns `active_device_name` in the response alongside `active_device_index`.

#### `ledfx/api/config.py`

- **`update_config()`** — When the incoming payload contains `audio_device`, the stale `audio_device_name` is cleared from the existing config **before** the merge. This prevents `_resolve_device_from_name()` from name-matching back to the old device and overriding the user's selection. See §3.1 below.

#### `ledfx/config.py`

No new migration required. `audio_device_name` defaults to `""` via the schema, so legacy configs load without error.

### 3.1 Config Merge Hazard — `ledfx/api/config.py`

> **Bug found 2026-04-08.** The original implementation missed this path entirely.

The frontend changes audio devices via `PUT /api/config {"audio": {"audio_device": 4}}`, which is handled by `ConfigEndpoint.update_config()` in `ledfx/api/config.py`. This method does a **partial merge**:

```python
self._ledfx.config["audio"].update(audio_config)
```

`.update()` only overwrites keys present in the incoming payload. When the frontend sends `{"audio_device": 4}` (no `audio_device_name`), the stale `audio_device_name` from the prior device selection survives the merge. The merged config is then passed to `AudioInputSource.update_config()`, which calls `_resolve_device_from_name()`. That method sees the stale name, searches by name, finds the **old** device, and overrides the user's new index selection.

**Fix:** Before the merge, if the incoming payload contains `audio_device`, explicitly clear `audio_device_name` in the existing config:

```python
if "audio_device" in audio_config:
    self._ledfx.config["audio"]["audio_device_name"] = ""
```

This causes `_resolve_device_from_name()` to take the "no name stored" path and use the index as-is. The name is then correctly populated by `persist_device_name_if_needed()` after the new device opens.

**Key lesson:** Any code path that can write `audio_device` without simultaneously writing `audio_device_name` must clear the stale name. The dedicated audio devices API (`ledfx/api/audio_devices.py`) writes both together, but the general config API merges partial payloads — a distinction the original strategy failed to account for.

### 4. `_resolve_device_from_name()` Algorithm

See `ledfx/effects/audio.py` for the definitive implementation.

Called from `update_config()` after schema validation, before `activate()`.

**Resolution order:**

1. If `audio_device_name` is empty → return immediately (legacy/first-run path)
2. If the saved index exists in the current device list **and** its name matches → return (fast path, no drift)
3. Search all devices by name via `get_device_index_by_name()` (handles exact + partial/truncated matching):
   - If found → update `audio_device` to the new index, persist
4. Device not found at all:
   - Reset `audio_device` to `default_device_index()`
   - Clear `audio_device_name`
   - Clear runtime tracking (`_last_device_name`, `_last_active`) so hotplug won't attempt recovery to the gone device
   - Persist

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
8. **Key step:** `persist_device_name_if_needed()` detects the name is missing and writes both keys back to config (e.g. `audio_device: 17` + `audio_device_name: "Windows WASAPI: Speakers (Realtek) [Loopback]"`)
9. Config is saved to disk — **config is now upgraded for all future sessions**
10. From the next restart onward, name-based resolution is active

#### Critical Design Constraint

The name must be persisted on the **first successful activation** after upgrade, not only on user-initiated device changes via the API. The `persist_device_name_if_needed()` inner function in `_activate_inner()` handles this — it runs after every successful device open and syncs both config keys if the actual device differs from what's in config. Without this, a user who never touches the audio settings would never get their config upgraded.

#### `persist_device_name_if_needed()` Algorithm

See `ledfx/effects/audio.py` `_activate_inner()` for the definitive implementation.

Called after each successful `try_open_device()` in the startup sequence.

1. Read `_last_device_name` and `_last_active` (the actually-opened device) under class lock
2. If either is unset → return (nothing to persist)
3. Compare against current config values for `audio_device_name` and `audio_device`
4. If either differs → update **both** config keys to match the actual device, then persist
5. This handles three cases:
   - **Legacy upgrade:** config had no name, now it gets one
   - **Fallback open:** configured device failed, default opened — config updated to reflect reality
   - **Normal confirmation:** config already matches, no write needed

#### Summary

- `audio_device_name` defaults to `""` — existing configs load without error
- Legacy index is trusted at face value on first boot after upgrade
- Name is auto-populated on first successful activation
- The integer `audio_device` field is never removed — it remains the fast path and fallback
- Zero user interaction required for the upgrade

### 7. Testing Strategy

All tests should live in `tests/test_audio_device_persistence.py`. Tests mock `AudioInputSource.input_devices()` and `AudioInputSource.default_device_index()` to simulate different device enumeration states without requiring real audio hardware.

#### 7.1 Mock Fixtures

See `tests/test_audio_device_persistence.py` for the definitive fixture definitions.

Tests use mock device dictionaries keyed by index with `"{hostapi}: {name}"` string values, simulating:
- **DEVICES_BEFORE** — Standard device list (baseline state)
- **DEVICES_AFTER_USB_ADDED** — USB device inserted, indices shifted upward
- **DEVICES_AFTER_REMOVAL** — Target device removed entirely
- **DEVICES_TRUNCATED** — PortAudio-truncated long device names
- **DEVICES_SIMILAR_NAMES** — Multiple devices with overlapping name prefixes

#### 7.2 Unit Tests — `_resolve_device_from_name()`

These test the core resolution logic in isolation.

| # | Test Name | Config Input | Mock Devices | Expected Result |
|---|---|---|---|---|
| 1 | `test_resolve_name_matches_at_saved_index` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_BEFORE` | Index stays `17`, no config save |
| 2 | `test_resolve_name_found_at_different_index` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_AFTER_USB_ADDED` | Index updated to `18`, config saved |
| 3 | `test_resolve_name_not_found_device_removed` | `idx=17, name="...Speakers...Loopback"` | `DEVICES_AFTER_REMOVAL` | Index reset to default, name cleared, runtime tracking (`_last_device_name`, `_last_active`) cleared |
| 4 | `test_resolve_empty_name_skips_resolution` | `idx=17, name=""` | `DEVICES_BEFORE` | Index stays `17`, no name search performed |
| 5 | `test_resolve_no_name_key_skips_resolution` | `idx=17` (no name key) | `DEVICES_BEFORE` | Index stays `17` (schema default `""` applied) |
| 6 | `test_resolve_partial_match_truncated_name` | `idx=17, name="...Speakers (Realtek High Def"` | `DEVICES_BEFORE` | Partial match finds index `17` via `get_device_index_by_name` |
| 7 | `test_resolve_prefers_exact_over_partial` | `idx=2, name="...Microphone (Realtek)"` | `DEVICES_SIMILAR_NAMES` | Exact match at `1`, not partial at `2` |
| 8 | `test_resolve_saved_index_invalid_name_found` | `idx=99, name="...Speakers...Loopback"` | `DEVICES_BEFORE` | Name search finds `17`, updates index |
| 9 | `test_resolve_saved_index_invalid_name_not_found` | `idx=99, name="Nonexistent Device"` | `DEVICES_BEFORE` | Index reset to default, name cleared |
| 10 | `test_resolve_index_valid_but_wrong_device` | `idx=17, name="...Speakers...Loopback"` | `{17: "...Microphone...", 18: "...Speakers...Loopback"}` | Name mismatch at `17`, found at `18`, updates index |

#### 7.3 Unit Tests — Legacy Upgrade Path

These verify that upgrading from index-only configs works seamlessly.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 11 | `test_legacy_config_no_name_field` | Config `{"audio_device": 17}` loaded through schema | `audio_device_name` defaults to `""`, index `17` used as-is |
| 12 | `test_legacy_config_empty_audio_dict` | Config `{}` loaded through schema | Default device index chosen, no name resolution attempted |
| 13 | `test_legacy_upgrade_name_persisted_on_activation` | Config `{"audio_device": 17}`, activate succeeds | After activation, config contains `audio_device_name` matching device at index `17` |
| 14 | `test_legacy_upgrade_name_not_persisted_for_invalid_device` | Config `{"audio_device": 17}`, device not in device list | `audio_device_name` remains `""` — don't persist a name for a device we can't identify |
| 15 | `test_legacy_upgrade_second_startup_uses_name` | Simulate: first boot persists name, second boot with shifted indices | Second boot resolves by name to new index |

#### 7.4 Unit Tests — API Endpoint

These verify the REST API correctly persists both fields. Tests must exercise the actual `ConfigEndpoint.update_config()` merge path against pre-existing config state, not just construct new dicts in isolation.

| # | Test Name | Scenario | Expected Result |
|---|---|---|---|
| 16 | `test_api_put_persists_name_and_index` | PUT `{"audio_device": 5}` via audio devices API | Config saved with both `audio_device: 5` and `audio_device_name: "..."` |
| 16b | `test_api_put_device_change_clears_stale_name` | PUT `{"audio": {"audio_device": 5}}` via general config API, existing config has `audio_device: 17` + `audio_device_name: "Loopback"` | Stale name cleared before merge; `update_config()` receives `audio_device: 5` with `audio_device_name: ""` so `_resolve_device_from_name()` does not override the user's selection |
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
| 30 | `test_partial_match_avoids_false_positive` | Stored `"Microphone"` has exact match at index 0 plus longer partial matches at indices 1, 2 | Exact match at index 0 is returned, not a longer partial match (e.g., `"Microphone (Realtek)"`) |

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

### 8. Implementation Order & Progress

**Branch:** `audio_name_2`
**PR:** [#1770 — Feat: Audio device persist by name](https://github.com/LedFx/LedFx/pull/1770)

| # | Task | File(s) | Status |
|---|---|---|---|
| 1 | Add `audio_device_name` to `AUDIO_CONFIG_SCHEMA` | `ledfx/effects/audio.py` | [x] |
| 2 | Add `_resolve_device_from_name()` method | `ledfx/effects/audio.py` | [x] |
| 3 | Call resolver from `update_config()` before `activate()` | `ledfx/effects/audio.py` | [x] |
| 4 | Update `_update_device_config()` to persist name | `ledfx/effects/audio.py` | [x] |
| 5 | Auto-persist name in `_activate_inner()` (legacy upgrade path) | `ledfx/effects/audio.py` | [x] |
| 6 | Update API PUT to persist name | `ledfx/api/audio_devices.py` | [x] |
| 7 | Update API GET to return name | `ledfx/api/audio_devices.py` | [x] |
| 8 | Write unit tests (37 cases from §7) | `tests/test_audio_device_persistence.py` | [x] |
| 9 | Run tests and verify | — | [x] |
| 10 | Fix config merge hazard — clear stale name on API device change | `ledfx/api/config.py` | [x] |
| 11 | Add regression test for config merge hazard (#16b) | `tests/test_audio_device_persistence.py` | [x] |

> **Session recovery:** If a session times out, read this document to restore context. The table above tracks progress. Resume from the first unchecked item.

---

## Appendix: Code References

| Component | File | Symbol |
|---|---|---|
| Config schema | `ledfx/effects/audio.py` | `AUDIO_CONFIG_SCHEMA` |
| Startup resolver | `ledfx/effects/audio.py` | `_resolve_device_from_name()` |
| Index validator | `ledfx/effects/audio.py` | `device_index_validator()` |
| Runtime name tracking | `ledfx/effects/audio.py` | `_last_device_name`, `update_device_tracking()` |
| Post-activation persistence | `ledfx/effects/audio.py` | `persist_device_name_if_needed()` (inner in `_activate_inner`) |
| Device list change handler | `ledfx/effects/audio.py` | `handle_device_list_change()` |
| Name-based search | `ledfx/effects/audio.py` | `get_device_index_by_name()` |
| Config update + save | `ledfx/effects/audio.py` | `_update_device_config()`, `_persist_config()` |
| API device selection | `ledfx/api/audio_devices.py` | `put()`, `get()` |
| General config merge (stale name fix) | `ledfx/api/config.py` | `update_config()` |
| Input device enumeration | `ledfx/effects/audio.py` | `input_devices()` |
| Device activation | `ledfx/effects/audio.py` | `_activate_inner()` |
