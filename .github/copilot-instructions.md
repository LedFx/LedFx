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

- **Python Version**: 3.10-3.13 supported
- **Build System**: `uv` workspace with `pyproject.toml`
- **License**: GPL-3.0
- **Dependencies**: Audio processing (aubio-ledfx, sounddevice), LED control (openrgb-python, sacn), web framework (aiohttp)
- **Development Tools**: pre-commit hooks (black, flake8, isort, pyupgrade), VS Code integration

### Workspace Structure
```
ledfx/                    # Main package
├── effects/             # Effect implementations (50+ files)
├── devices/             # Device drivers (WLED, E1.31, DDP, etc.)
├── api/                 # REST API endpoints
├── integrations/        # External service integrations
├── rust/               # Rust-accelerated effects
├── core.py             # Application core
├── virtuals.py         # Virtual LED strip management
└── config.py           # Configuration management
```

## Effect System Architecture

### Effect Base Class (`ledfx/effects/__init__.py`)
All effects inherit from the `Effect` base class which provides:
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
5. **Rust Effects**: Performance-critical effects in Rust

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
- `Device`: Base device class
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
- `/api/devices` - Device management
- `/api/virtuals` - Virtual strip control
- `/api/effects` - Effect library
- `/api/config` - Configuration management
- `/api/audio` - Audio device settings

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

### Performance Considerations
- **NumPy**: Use vectorized operations for pixel manipulation
- **Threading**: Protect shared state with locks
- **Caching**: Cache expensive computations
- **Rust Extensions**: Use for CPU-intensive effects

### Error Handling
- **Graceful Degradation**: Continue operation when devices fail
- **Logging**: Comprehensive logging with appropriate levels
- **Validation**: Validate all user inputs
- **Recovery**: Attempt reconnection for network devices

## Testing Patterns

- **Effect Testing**: Unit tests for effect rendering
- **Device Mocking**: Mock network devices for testing
- **Configuration Validation**: Test schema validation
- **API Testing**: Integration tests for REST endpoints

## Common Tasks

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
- Consider Rust extensions for critical paths
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