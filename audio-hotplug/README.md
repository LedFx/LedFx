# audio-hotplug

Cross-platform audio device hotplug detection with debouncing for Windows, macOS, and Linux.

[![PyPI version](https://badge.fury.io/py/audio-hotplug.svg)](https://pypi.org/project/audio-hotplug/)
[![Python versions](https://img.shields.io/pypi/pyversions/audio-hotplug.svg)](https://pypi.org/project/audio-hotplug/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- 🔌 **Cross-platform**: Works on Windows, macOS, and Linux
- ⚡ **Debouncing**: Coalesces rapid device changes to prevent callback storms
- 🔄 **Async-ready**: Supports both sync and async callbacks
- 🎯 **Focused**: Does one thing well - detects audio device topology changes
- 🪶 **Lightweight**: Minimal dependencies, platform-specific imports only when needed

## Installation

```bash
# Install with uv
uv pip install audio-hotplug

# Or with pip
pip install audio-hotplug
```

Platform-specific dependencies are installed automatically based on your OS.

## Quick Start

```python
import asyncio
from audio_hotplug import create_monitor

def on_audio_devices_changed():
    print("Audio devices changed!")

async def main():
    loop = asyncio.get_running_loop()

    # Create monitor with 200ms debounce
    monitor = create_monitor(loop=loop, debounce_ms=200)

    if monitor:
        monitor.start(on_audio_devices_changed)
        # Your application code here...
        await asyncio.sleep(60)
        monitor.stop()

asyncio.run(main())
```

## Usage

### Basic Usage (Sync Callback)

```python
from audio_hotplug import create_monitor

def handle_change():
    # Refresh your audio device list here
    print("Device list changed!")

monitor = create_monitor()
if monitor:
    monitor.start(handle_change)
```

### Async Callback

```python
import asyncio
from audio_hotplug import create_monitor

async def handle_change():
    # Async operations supported
    await notify_websocket_clients()
    print("Device list changed!")

async def main():
    loop = asyncio.get_running_loop()
    monitor = create_monitor(loop=loop)
    if monitor:
        monitor.start(handle_change)
        await asyncio.sleep(3600)
        monitor.stop()

asyncio.run(main())
```

### Custom Debouncing

```python
# Adjust debounce time (milliseconds)
monitor = create_monitor(debounce_ms=500)  # Wait 500ms after last change
```

### Custom Logging

```python
import logging

logger = logging.getLogger("my_app.audio")
monitor = create_monitor(logger=logger)
```

## How It Works

The library monitors OS-level audio device notifications:

- **Windows**: Uses Core Audio API (`IMMNotificationClient`) via `pycaw`
- **macOS**: Uses CoreAudio property listeners via `pyobjc-framework-CoreAudio`
- **Linux**: Uses `udev` subsystem monitoring via `pyudev`

When devices are added, removed, or change state, the library:

1. Detects the OS notification
2. Triggers the debouncer
3. Coalesces multiple rapid changes
4. Invokes your callback once after the debounce period

## API Reference

### `create_monitor()`

Creates a platform-specific audio device monitor.

**Parameters:**
- `loop` (optional): `asyncio.AbstractEventLoop` - Event loop for callback scheduling
- `debounce_ms` (optional): `int` - Milliseconds to wait before invoking callback (default: 200)
- `logger` (optional): `logging.Logger` - Custom logger instance

**Returns:**
- `AudioDeviceMonitor` instance or `None` if platform unsupported

### `AudioDeviceMonitor`

Abstract base class for platform monitors.

**Methods:**
- `start(on_change: Callback)` - Start monitoring, call `on_change` when devices change
- `stop()` - Stop monitoring (safe to call multiple times)

**Callback signature:**
```python
# Sync callback
def on_change() -> None: ...

# Or async callback
async def on_change() -> None: ...
```

## Platform Support

| Platform | Dependency | Auto-installed |
|----------|-----------|----------------|
| Windows  | `pycaw`, `comtypes` | ✅ |
| macOS    | `pyobjc-framework-CoreAudio` | ✅ |
| Linux    | `pyudev` | ✅ |

Platform-specific dependencies are only installed on the relevant OS using package markers.

## Development

This project uses `uv` for development:

```bash
# Clone the repository
git clone https://github.com/LedFx/audio-hotplug.git
cd audio-hotplug

# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run example
uv run python examples/monitor_print.py

# Build package
uv run python -m build
```

## Testing

```bash
# Run all tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=audio_hotplug --cov-report=html

# Run specific test
uv run pytest tests/test_debounce.py
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Extracted from [LedFx](https://github.com/LedFx/LedFx) to provide a reusable, focused library for audio device hotplug detection.

## Related Projects

- [LedFx](https://github.com/LedFx/LedFx) - Real-time LED visualization system
- [sounddevice](https://github.com/spatialaudio/python-sounddevice) - Audio I/O library
- [PortAudio](http://www.portaudio.com/) - Cross-platform audio I/O library
