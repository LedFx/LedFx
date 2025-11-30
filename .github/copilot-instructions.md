# Copilot Instructions for LedFx

## Project Overview

LedFx is a real-time LED visualization system that synchronizes LED lighting with audio input. It processes audio signals and translates them into colorful light patterns that can be displayed on network-connected LED devices like ESP8266/ESP32, WLED, and other compatible hardware.

### Key Architecture Components

1. **Core System** (`ledfx/core.py`): Main application orchestrator
2. **Effects** (`ledfx/effects/`): 50+ visual effect implementations
3. **Devices** (`ledfx/devices/`): Hardware device integrations
4. **Virtuals** (`ledfx/virtuals.py`): Virtual LED strip abstractions
5. **Audio Processing**: Real-time audio analysis and FFT
6. **Web API** (`ledfx/api/`): REST API and WebSocket interface
7. **Integrations** (`ledfx/integrations/`): External service connections

## Development Environment

- **Python Version**: 3.10-3.13 supported (requires-python = ">=3.10,<3.14")
- **Build System**: `uv` workspace with `pyproject.toml`
- **License**: GPL-3.0
- **Dependencies**: Audio processing (aubio-ledfx, sounddevice), LED control (openrgb-python, sacn), web framework (aiohttp)
- **Development Tools**: pre-commit hooks (black, flake8, isort, pyupgrade), VS Code integration

### Workspace Structure
```
ledfx/                    # Main package
├── api/                 # REST API endpoints
├── devices/             # Device drivers (WLED, E1.31, DDP, etc.)
├── effects/             # Effect implementations (50+ files)
├── integrations/        # External service integrations
├── libraries/           # Shared libraries (cache, lifxdev)
├── tools/               # Development tools (TypeScript generator, etc.)
├── color.py             # Color manipulation utilities
├── config.py            # Configuration management
├── core.py              # Application core
├── events.py            # Event system
├── utils.py             # Utility functions and BaseRegistry
└── virtuals.py          # Virtual LED strip management
```

## Effect System Architecture

### Effect Base Class (`ledfx/effects/__init__.py`)
All effects inherit from the `Effect` base class (which extends `BaseRegistry` from `utils.py`) which provides:
- **Pixel Management**: `self.pixels` array for RGB values
- **Configuration**: Voluptuous schema validation
- **Rendering**: `render()` method for effect computation
- **Post-processing**: blur, flip, mirror, brightness, background color
- **Threading**: Thread-safe with `self.lock`

### Effect Categories
1. **Audio Effects**: Spectrum analyzers, beat detection, tempo sync
2. **2D Effects**: Matrix-based effects for LED panels
3. **1D Effects**: Linear strip effects
4. **Temporal Effects**: Time-based animations

### Common Effect Patterns
```python
class MyEffect(Effect):
    NAME = "My Effect"
    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("speed", default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10.0)),
        vol.Optional("color", default="#ff0000"): validate_color,
    })

    def render(self):
        # Effect computation here
        # Modify self.pixels array
        pass
```

## Device Integration

### Device Types
- **WLED**: WiFi LED controllers (DDP/UDP protocols)
- **E1.31**: DMX over Ethernet (sACN protocol)
- **ArtNet**: Professional lighting protocol
- **DDP**: Display Data Protocol
- **Serial**: Adalight/TPM2 serial devices
- **OpenRGB**: RGB peripheral control
- **OSC**: Open Sound Control protocol

### Device Base Classes
All devices inherit from `BaseRegistry` (from `utils.py`):
- `Device`: Base device class with CONFIG_SCHEMA
- `NetworkedDevice`: IP-based devices with address resolution
- `UDPDevice`: UDP-based network devices
- `SerialDevice`: Serial port devices

## Virtual LED Strips

Virtuals abstract physical LED hardware, allowing:
- **Segments**: Map virtual pixels to device pixel ranges
- **Effects**: Apply effects to virtual strips
- **Mapping**: Span effects across segments or copy per segment
- **Transitions**: Smooth effect changes
- **Matrix Support**: 2D LED panel configurations

## Audio Processing Pipeline

1. **Audio Input**: Capture from system audio devices
2. **FFT Analysis**: Real-time frequency domain analysis
3. **Mel Scale**: Perceptually uniform frequency bins
4. **Beat Detection**: Onset detection and tempo analysis
5. **Effect Parameters**: Audio drives effect parameters

## Configuration System

- **JSON Configuration**: User settings stored in JSON
- **Schema Validation**: Voluptuous for type safety
- **Runtime Updates**: Hot-reload configuration changes
- **Presets**: Save/load effect configurations
- **Scenes**: Coordinate multiple virtual strips

## API Design

### REST Endpoints
Key API endpoints include:
- `/api/virtuals` - Virtual strip control
- `/api/effects` - Effect library
- `/api/devices` - Device management
- `/api/config` - Configuration management
- `/api/scenes` - Scene coordination
- `/api/integrations` - External service connections
- `/api/cache/images` - Image cache management
- `/api/assets` - Secure asset storage and management 

### REST API Implementation Standards

**CRITICAL**: Each API file in `ledfx/api/` must contain exactly ONE `RestEndpoint` class. The RegistryLoader auto-discovery pattern requires one endpoint class per file for proper registration. If you need multiple related endpoints (e.g., main endpoint + download endpoint), create separate files following the naming pattern seen in cache API (`cache_images.py` + `cache_images_refresh.py`).

**IMPORTANT**: Always use `RestEndpoint` base class helper methods instead of direct `web.json_response()` calls for consistent response formatting and frontend snackbar notifications.

#### Helper Methods
- **`await self.request_success(type, message, data=None)`** - Operations needing user feedback (type: "success", "info", "warning", "error")
- **`await self.bare_request_success(data)`** - Operations without snackbar notifications
- **`await self.invalid_request(message, type="error")`** - Validation errors and failures (returns HTTP 200 with status:"failed" for frontend compatibility)
- **`await self.json_decode_error()`** - JSON parsing errors (use in try/except with JSONDecodeError)

Do NOT use `web.json_response()` directly.

### WebSocket Events
- Real-time pixel updates
- Configuration changes
- Audio analysis data
- Device status updates

## Development Guidelines

### Code Style
- **Black**: Code formatting
- **flake8**: Linting with E501 line length relaxed
- **isort**: Import organization
- **Type Hints**: Use where beneficial

### Path Handling Standards

**IMPORTANT**: Always use `os.path` module for path operations, NOT `pathlib`. This is the established codebase convention with 20+ uses throughout the project.

Use `os.path.join()` for path construction, `os.path.exists()` for checks, `os.makedirs()` for directory creation, and `os.remove()` for file deletion. Do NOT use pathlib's `Path()` or `/` operator.

### Performance Considerations
- **NumPy**: Use vectorized operations for pixel manipulation
- **Threading**: Protect shared state with locks
- **Caching**: Cache expensive computations

### Error Handling
- **Graceful Degradation**: Continue operation when devices fail
- **Logging**: Comprehensive logging with appropriate levels
  - Use `_LOGGER.warning()` for expected client errors (invalid requests, missing resources)
  - Reserve `_LOGGER.error()` for actual system errors to avoid Sentry noise
  - Follow pattern from `scenes.py` and `config.py` for API error handling
- **Validation**: Validate all user inputs
- **Recovery**: Attempt reconnection for network devices

## Testing Patterns

- **Effect Testing**: Unit tests for effect rendering
- **Device Mocking**: Mock network devices for testing
- **Configuration Validation**: Test schema validation
- **API Testing**: Integration tests for REST endpoints
- **Security Testing**: Use big-list-of-naughty-strings patterns for input validation

### Security Testing Guidelines

When testing input validation, especially for file paths and URLs, use patterns from the big-list-of-naughty-strings project to test:

1. **Path Traversal**: `../`, encoded variants, null bytes, mixed separators
2. **URL Injection**: Protocol injection, IP obfuscation, localhost variants
3. **Special Filenames**: Reserved names (CON, PRN, NUL), control characters, homoglyphs
4. **SSRF Protection**: Loopback addresses, private networks, metadata endpoints

## Common Tasks

### Adding New API Endpoints
1. Create new file in `ledfx/api/` with ONE `RestEndpoint` class per file
2. Use `RestEndpoint` helper methods (`request_success`, `bare_request_success`, `invalid_request`)
3. Never use `web.json_response()` directly
4. Use `_LOGGER.warning()` for client errors, not `_LOGGER.error()` (avoid Sentry noise)
5. Follow security patterns: path validation, input sanitization, content validation
6. Write integration tests in `tests/test_api_*.py`
7. Document in `docs/apis/*.md`

### Adding New Effects
1. Create effect class inheriting from `Effect`
2. Define `CONFIG_SCHEMA` with Voluptuous
3. Implement `render()` method
4. Add to effect registry
5. Write tests

### Adding Device Types
1. Inherit from appropriate base class
2. Define device-specific configuration schema
3. Implement `flush()` method for data transmission
4. Handle connection/disconnection
5. Add device discovery if applicable

### Performance Optimization
- Profile with `cProfile` for CPU bottlenecks
- Use `numpy` operations instead of Python loops
- Leverage vnoise for performance-critical noise generation
- Cache expensive calculations
- Optimize network transmission

## Domain Knowledge

### LED Physics
- **Color Spaces**: RGB, HSV color manipulation
- **Gamma Correction**: Perceptual brightness correction
- **Power Management**: Current limiting for LED strips

### Audio DSP
- **Frequency Analysis**: FFT, mel scale, frequency bins
- **Beat Detection**: Onset detection algorithms
- **Audio Latency**: Real-time processing constraints

### Network Protocols
- **UDP**: Connectionless, low-latency transmission
- **E1.31**: DMX512 over Ethernet standard
- **DDP**: High-performance pixel protocol
- **Multicast**: Efficient network distribution

## Troubleshooting Guide

### Common Issues
1. **Audio Device Problems**: Check system audio permissions
2. **Network Device Offline**: Verify IP addresses and network connectivity
3. **High CPU Usage**: Profile effects and optimize rendering
4. **Color Accuracy**: Check gamma correction and color calibration

### Debugging Tools
- **Effect Diagnostics**: Enable `diag` option for detailed logging
- **Performance Analysis**: Built-in timing and profiling
- **Network Testing**: Device discovery and ping utilities
- **Audio Visualization**: Real-time audio analysis display

## Integration Points

### External Services
- **Spotify**: Music synchronization
- **Home Assistant**: Smart home integration
- **MQTT**: IoT messaging protocol
- **QLC+**: Professional lighting control

### Hardware Compatibility
- **ESP8266/ESP32**: WiFi microcontrollers
- **Raspberry Pi**: Single-board computers
- **Arduino**: Microcontroller platforms
- **Professional DMX**: Stage lighting equipment

This comprehensive guide should help AI assistants understand LedFx's architecture, development patterns, and domain-specific requirements for LED visualization systems.