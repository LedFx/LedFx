# Audio Device Monitoring

## Overview

LedFx includes automatic detection of system-level audio device changes (devices being added or removed) using native OS event systems. This feature is **enabled by default** on all platforms and uses platform-specific libraries that are automatically installed based on your operating system.

## Implementation

### Architecture

The audio device monitoring system consists of:

1. **Platform-specific monitors** ([audio_device_monitor.py](../../ledfx/audio_device_monitor.py))
   - Windows: Core Audio API's `IMMNotificationClient`
   - macOS: CoreAudio property listeners
   - Linux: udev device events

2. **Event system** ([events.py](../../ledfx/events.py))
   - New event: `AUDIO_DEVICE_LIST_CHANGED`
   - Event class: `AudioDeviceListChangedEvent`

3. **Device list refresh** ([audio.py](../../ledfx/effects/audio.py))
   - `AudioInputSource.refresh_device_list()` reinitializes PortAudio
   - Automatically called when device change event fires

4. **Core integration** ([core.py](../../ledfx/core.py))
   - Monitor started during `async_start()`
   - Event listener registered to trigger device list refresh
   - Monitor stopped during `async_stop()`

5. **WebSocket broadcasting**
   - Automatically broadcasts to subscribed clients via existing event system
   - No additional websocket code required

### How It Works

1. **Startup**: When LedFx starts, it initializes a platform-specific audio device monitor
2. **Monitoring**: The monitor listens to OS-level events using native APIs
3. **Event firing**: When a device is added/removed, the monitor fires an `AudioDeviceListChangedEvent`
4. **Automatic refresh**: The event triggers `AudioInputSource.refresh_device_list()` which reinitializes PortAudio to rescan devices
5. **WebSocket broadcast**: Connected clients subscribed to this event receive a notification
6. **Frontend update**: Frontend can re-fetch the device list via `/api/audio/devices` to get the updated list

**Note**: The device list is automatically refreshed when the event fires, so `/api/audio/devices` will always return current devices after a change is detected.

### Platform-Specific Details

#### Windows (Core Audio API)

Uses `pycaw` (Python Core Audio Windows) to register an `IMMNotificationClient`:

```python
from pycaw.pycaw import IMMDeviceEnumerator, IMMNotificationClient
```

**Monitors:**
- `OnDeviceAdded()` - New audio device connected
- `OnDeviceRemoved()` - Audio device disconnected
- `OnDeviceStateChanged()` - Device state changed (e.g., enabled/disabled)

**Thread model:** Runs in separate thread with COM initialization

#### macOS (CoreAudio)

Uses `pyobjc-framework-CoreAudio` to listen to property changes:

```python
from CoreAudio import AudioObjectAddPropertyListener, kAudioHardwarePropertyDevices
```

**Monitors:**
- `kAudioHardwarePropertyDevices` property changes

**Thread model:** Callback-based, executes in main CoreAudio thread

#### Linux (udev)

Uses `pyudev` to monitor kernel device events:

```python
import pyudev
```

**Monitors:**
- Subsystem: `sound`
- Actions: `add`, `remove`

**Thread model:** Runs in separate thread with blocking poll loop

### Device List Refresh Mechanism

**Problem**: PortAudio (underlying library for `sounddevice`) caches the device list at initialization and doesn't automatically update when devices are added/removed.

**Solution**: When an `AudioDeviceListChangedEvent` is fired, LedFx automatically calls `AudioInputSource.refresh_device_list()` which:

1. Calls `sd._terminate()` to shut down PortAudio
2. Calls `sd._initialize()` to reinitialize PortAudio
3. Clears internal device list cache
4. Forces PortAudio to rescan all audio devices

This ensures that subsequent calls to `/api/audio/devices` return the current device list.

**Implementation** ([core.py](../../ledfx/core.py)):
```python
def _start_audio_device_monitor(self):
    """Start the audio device monitor for the current platform."""
    # ... monitor initialization ...

    # Register event listener to refresh device list when devices change
    self.events.add_listener(
        self._on_audio_device_list_changed,
        Event.AUDIO_DEVICE_LIST_CHANGED
    )

def _on_audio_device_list_changed(self, event):
    """Handle audio device list changes by refreshing the cached device list."""
    from ledfx.effects.audio import AudioInputSource
    AudioInputSource.refresh_device_list()
```

**Thread safety**: The refresh happens synchronously in the event callback, which runs in the main event loop thread.

## Installation

Audio device monitoring is **enabled by default** on all platforms with the appropriate platform-specific dependencies installed automatically:

- **Windows**: `pycaw` (Core Audio API)
- **macOS**: `pyobjc-framework-CoreAudio`
- **Linux**: `pyudev`

### Standard Installation

```bash
pip install ledfx
```

This will automatically install the correct monitoring library for your platform.

### For Development

```bash
uv sync
```

## Usage

### Backend (Python)

The monitor starts automatically when LedFx starts. No additional code needed.

To manually fire the event:

```python
from ledfx.events import AudioDeviceListChangedEvent
ledfx.events.fire_event(AudioDeviceListChangedEvent())
```

### Frontend (JavaScript)

Subscribe to the event via websocket:

```javascript
// Subscribe to audio device list changes
websocket.send(JSON.stringify({
    id: 1,
    type: "subscribe_event",
    event_type: "audio_device_list_changed"
}));

// Handle the event
websocket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.event_type === "audio_device_list_changed") {
        // Device list has been automatically refreshed by LedFx
        // Re-fetch to update the UI
        fetch('/api/audio/devices')
            .then(response => response.json())
            .then(data => {
                // Update UI with new device list
                console.log("Audio devices updated:", data.devices);
                updateAudioDeviceDropdown(data.devices);
            });
    }
};
```

**Note**: You don't need to manually refresh the backend device list - LedFx automatically calls `refresh_device_list()` when the event fires.

## Testing

### Manual Testing

1. **Start LedFx** with audio monitoring enabled
2. **Check logs** for: `"Audio device monitor enabled"`
3. **Plug in/remove** a USB audio device or headphones
4. **Verify event** fires in logs: `"Audio device list changed - firing event"`
5. **Verify refresh** in logs: `"Audio device list refreshed"` and `"Audio device list updated in response to system change"`
6. **Check API**: Call `/api/audio/devices` to verify the new device list is returned
7. **Check frontend** receives websocket event (if subscribed)

### Automated Testing

```python
# tests/test_audio_device_monitor.py
import pytest
from ledfx.audio_device_monitor import create_audio_device_monitor
from ledfx.events import Event

@pytest.mark.asyncio
async def test_device_monitor_creation(ledfx_instance, event_loop):
    monitor = create_audio_device_monitor(ledfx_instance, event_loop)
    assert monitor is not None

@pytest.mark.asyncio
async def test_device_list_changed_event(ledfx_instance, event_loop):
    events_received = []

    def event_callback(event):
        events_received.append(event)

    ledfx_instance.events.add_listener(
        event_callback,
        Event.AUDIO_DEVICE_LIST_CHANGED
    )

    # Simulate device change (platform-specific)
    # ...

    assert len(events_received) > 0
```

## Graceful Degradation

The feature is designed to fail gracefully. If the platform-specific dependency fails to import for any reason (corrupted installation, incompatible architecture, etc.):

1. **Warning logged**: `"pycaw/pyudev/pyobjc not available - cannot monitor audio device changes"`
2. **Feature disabled**: No monitoring occurs, no errors raised
3. **Fallback**: Users can manually refresh by navigating away/back or refreshing the page
4. **Still functional**: Device enumeration still works via static `query_devices()` calls

This ensures LedFx starts and functions normally even if audio device monitoring isn't available.

## Performance Considerations

- **No polling**: Event-driven, zero CPU overhead when idle
- **Lightweight threads**: Monitor threads are daemon threads with minimal overhead
- **Async-safe**: Events properly scheduled on main asyncio loop
- **No blocking**: All operations are non-blocking

## Troubleshooting

### Monitor Not Starting

**Check logs for:**
```
Audio device monitor enabled
```

**If missing:**
- Verify LedFx installation completed successfully
- Check for import errors in logs
- Ensure LedFx has proper permissions (Linux: udev access)
- Platform-specific dependency may have failed to install (check pip output)

### Events Not Firing

1. **Verify subscription**: Check websocket subscriptions
2. **Test manually**: Try `ledfx.events.fire_event(AudioDeviceListChangedEvent())`
3. **Check platform**: Some VMs/containers may not propagate device events
4. **Permissions**: Linux may require user in `audio` group

### Windows-Specific Issues

- **COM initialization errors**: Usually transient, restart LedFx
- **Thread errors**: Check Windows audio service is running

### Linux-Specific Issues

- **udev access**: User may need to be in `plugdev` or `audio` group
- **Container restrictions**: Docker/containers may not receive udev events

### macOS-Specific Issues

- **Permission dialogs**: macOS may require permission to access audio devices
- **Code signing**: Pyobjc may require specific entitlements in packaged apps

## Future Enhancements

Possible improvements:

1. **Debouncing**: Add small delay before firing event (avoids rapid-fire during device initialization)
2. **Device details**: Include added/removed device info in event payload
3. **Default device changes**: Option to also monitor default device changes
4. **Hot-swapping**: Automatically switch to newly connected devices (opt-in)
5. **Health checks**: Periodic validation that monitor thread is alive

## API Reference

### Event: `AUDIO_DEVICE_LIST_CHANGED`

**Type:** `"audio_device_list_changed"`

**Payload:**
```json
{
    "id": 123,
    "type": "event",
    "event_type": "audio_device_list_changed"
}
```

**Use case:** Frontend subscribes to this event to know when to refresh the audio device list.

### Class: `AudioDeviceListChangedEvent`

Inherits from `Event`, no additional properties.

```python
class AudioDeviceListChangedEvent(Event):
    """Event emitted when the system audio device list changes (devices added/removed)"""

    def __init__(self):
        super().__init__(Event.AUDIO_DEVICE_LIST_CHANGED)
```

### Function: `create_audio_device_monitor(ledfx_instance, loop)`

Factory function to create platform-specific monitor.

**Parameters:**
- `ledfx_instance`: LedFx core instance
- `loop`: asyncio event loop

**Returns:**
- `AudioDeviceMonitor` subclass instance, or `None` if platform unsupported

**Example:**
```python
monitor = create_audio_device_monitor(self._ledfx, self.loop)
if monitor:
    monitor.start_monitoring()
```

### Function: `AudioInputSource.refresh_device_list()`

Forces PortAudio to rescan audio devices by reinitializing.

**Parameters:** None

**Returns:** None

**Side effects:**
- Terminates and reinitializes PortAudio
- Clears internal device list cache
- Logs info message on success, warning on error

**Example:**
```python
from ledfx.effects.audio import AudioInputSource

# Manually refresh the device list
AudioInputSource.refresh_device_list()

# Now query_devices() will return updated list
devices = AudioInputSource.input_devices()
```

**Note**: This is automatically called when `AUDIO_DEVICE_LIST_CHANGED` event fires.

## Contributing

When adding support for new platforms or improving existing monitors:

1. **Follow the pattern**: Inherit from `AudioDeviceMonitor`
2. **Handle errors gracefully**: Wrap imports in try/except
3. **Log appropriately**: Use `_LOGGER.info()` for startup, `_LOGGER.debug()` for events
4. **Test on target platform**: Verify device add/remove detection
5. **Update docs**: Document platform-specific requirements and limitations
