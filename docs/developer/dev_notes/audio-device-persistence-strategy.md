# Audio Device Selection and Recovery

**Scope:** Audio preference persistence, explicit selection, startup resolution, and device hotplug recovery.

---

## Configuration Model

LedFx stores both a device index and a device name in `config.json`:

```json
{
    "audio": {
        "audio_device": 17,
        "audio_device_name": "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]"
    }
}
```

`audio_device_name` is the persistent preferred-device identity when non-empty.
`audio_device` is the numeric index currently resolved from enumeration; indices
can change across refreshes and application restarts, so an index is not
authoritative when a preferred name exists. Names use the format returned by
`AudioInputSource.input_devices()`: `"{hostapi_name}: {device_name}"`.

`_last_device_name` and `_last_active` track the active stream at runtime. They
may describe a temporary fallback and do not replace the saved preference.

## Resolution Lifecycle

### Startup and Configuration Updates

`AudioInputSource.update_config()` merges partial updates with the current audio
config, validates the result, then calls `_resolve_device_from_name()` before
activation. Resolution follows these rules:

- If the saved index still maps to the preferred name, it is retained.
- Otherwise, the device list is searched by name, using exact matching first
    and partial matching for truncated names. A match updates the index.
- If a regular preferred device is unavailable, the index is set to the current
    default fallback. The preferred name is retained and saved.
- If a `SENDSPIN:` preferred source is unavailable, LedFx reports the source as
    unavailable and does not choose a physical-device fallback.
- If no preferred name is stored, the legacy numeric index is used as the
    starting selection.

Runtime index validation may substitute a usable default index, but it does not
change `audio_device_name`. Name resolution then gets the opportunity to restore
the preferred device.

### Activation and Persistence

After a stream opens, `_persist_active_device_config()` updates the active
numeric index. It populates `audio_device_name` only when the config has no
preferred name, which upgrades legacy index-only configurations after a
successful activation. When a named preference is unavailable and a fallback
opens, the active index may be saved, but the fallback name never replaces the
preference.

`_persist_config()` synchronizes the audio model to central config and requests
a disk save. `_update_device_config()` uses this persistence path to update the
runtime index without modifying the preferred name.

### Hotplug Recovery

`handle_device_list_change()` refreshes the device list and chooses the saved
preferred name before consulting the last active name. The latter is used only
when no preference exists (legacy configuration). On a normal device
disconnection, LedFx resolves the preference again, stores a fallback index,
and reactivates only if a stream had been active. If the preferred device
returns, it is found by name and restored even when its index changed. An
inactive source has its index resolved without opening a stream.

### Explicit Selection

An explicit device selection must update both the numeric index and preferred name. Partial changes to unrelated audio settings must preserve both existing values.

The audio devices endpoint, general config endpoint, and MQTT selector record
the selected device's current name. The general config endpoint handles
`PUT /api/config {"audio": {"audio_device": 4}}` by resolving that index before
passing the merged model to `AudioInputSource.update_config()`:

```python
audio["audio_device_name"] = AudioInputSource.input_devices().get(device, "")
candidate.audio = AudioConfig.model_validate({**cfg.audio.model_dump(), **audio})
```

Direct `update_config()` callers that supply a changed index without a name are
also treated as explicit selection and have the name resolved from the device
list. Runtime fallback updates use `_update_device_config()` instead and never
change the preferred name.

### Edge Cases

| Scenario | Behavior |
|---|---|
| Legacy config (no `audio_device_name`) | Falls through to existing index-based logic. No regression. |
| Preferred device temporarily unavailable | Name search fails; a fallback index is used, but the preferred name remains in config for restart/hotplug recovery. |
| Device name truncated by PortAudio | `get_device_index_by_name()` already handles partial matching. |
| Multiple devices with similar names | Exact match preferred, then longest partial match (existing logic). |
| User manually edits config.json | Works as long as name string matches `input_devices()` format. |
| WEB AUDIO devices | These also use the `"{hostapi}: {name}"` format via `input_devices()`. |
| SENDSPIN devices | Resolve by name and never silently fall back to a physical device. |
| Config saved on Windows, loaded on Linux | Host API names differ (`Windows WASAPI` vs `ALSA`). Name won't match, falls back to default. This is expected and correct. |

## Compatibility

Configurations without `audio_device_name` remain valid. An empty name means
the saved index is the only available selection; after a successful activation,
LedFx stores that device's name for future resolution. No configuration
migration step is required. When a preferred name exists, runtime validation
may adjust the numeric index but must not replace the name.

## Regression Coverage

`tests/test_audio_device_persistence.py` mocks device enumeration and stream
activation so the recovery cases do not require audio hardware. Coverage
includes index drift, missing-device fallbacks, restoring a device at its
original or a changed index, repeated disconnect cycles, explicit selection,
unrelated config updates during fallback, legacy index-only configs, and
Sendspin's no-physical-fallback behavior.

## Code References

| Component | File | Symbol |
|---|---|---|
| Responsibility | File | Symbols |
|---|---|---|
| Audio config model | `ledfx/configuration/models.py` | `AudioInputConfig`, `AudioConfig` |
| Runtime index validation | `ledfx/effects/audio.py` | `device_index_validator()` |
| Startup/config resolution | `ledfx/effects/audio.py` | `update_config()`, `_resolve_device_from_name()` |
| Hotplug recovery | `ledfx/effects/audio.py` | `handle_device_list_change()` |
| Active index persistence | `ledfx/effects/audio.py` | `_update_device_config()`, `_persist_active_device_config()`, `_persist_config()` |
| Device-name matching | `ledfx/effects/audio.py` | `input_devices()`, `get_device_index_by_name()` |
| Stream activation | `ledfx/effects/audio.py` | `_activate_inner()` |
| REST selection | `ledfx/api/audio_devices.py` | `put()`, `get()` |
| General config selection | `ledfx/api/config.py` | `apply_patch()` |
| MQTT selection | `ledfx/integrations/mqtt_hass.py` | audio selector handler |
