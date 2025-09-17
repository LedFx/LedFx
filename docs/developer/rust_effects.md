# Rust Effects Developer Guide

This guide explains how to add high-performance Rust effects to LedFx and integrate them into the build process.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Creating a New Rust Effect](#creating-a-new-rust-effect)
5. [Python Integration](#python-integration)
6. [Build Process Integration](#build-process-integration)
7. [Performance Guidelines](#performance-guidelines)
8. [Troubleshooting](#troubleshooting)

## Overview

LedFx uses Rust effects to provide high-performance audio-reactive visualizations. Rust effects are compiled into Python modules using [maturin](https://github.com/PyO3/maturin) and [PyO3](https://github.com/PyO3/pyo3), offering significant performance benefits over pure Python implementations.

LedFx uses **uv workspaces** for streamlined Rust effects development. The Rust effects are built automatically when you sync the project.

## Quick Start

```bash
# From the LedFx root directory - builds everything including Rust effects
uv sync
```

**Testing Rust Effects**:
```bash
# Test that Rust effects are available
uv run python -c "from ledfx.rust import RUST_AVAILABLE; print('Rust effects available:', RUST_AVAILABLE)"
```

**VS Code Tasks**: Use "Build Rust Effects (with Auto-Install)" from Command Palette for automatic setup
- See **[Tasks Documentation](tasks.md)** for comprehensive task information

**Rust Installation**: The VS Code task and workspace sync (`uv sync`) automatically install Rust if missing.

## Prerequisites

### Required Tools
- **Rust**: Install from [rustup.rs](https://rustup.rs/)
- **Python 3.9-3.12**: LedFx supported versions
- **maturin**: Python-Rust build tool (included in dev dependencies)
- **uv**: Package manager (used by LedFx)

### Development Environment Setup
```bash
# Clone the repository
git clone https://github.com/LedFx/LedFx.git
cd LedFx

# Install and build everything (includes Rust effects)
uv sync

# Verify Rust installation (optional)
rustc --version
cargo --version

# Test that Rust effects work
uv run python -c "from ledfx.rust import RUST_AVAILABLE; print(f'Rust available: {RUST_AVAILABLE}')"
```

## Workspace Architecture

LedFx uses **uv workspaces** to manage the Rust effects as an integrated part of the main project:

- **Main Project**: `LedFx` (at repository root)
- **Workspace Member**: `ledfx-rust-effects` (in `ledfx/rust/`)
- **Shared Lockfile**: `uv.lock` (ensures consistent dependencies across workspace)
- **Workspace Dependency**: LedFx depends on `ledfx-rust-effects` via `{ workspace = true }`

Benefits:
- ✅ Single `uv sync` builds everything  
- ✅ Consistent dependency versions across projects
- ✅ Automatic editable installs during development
- ✅ Simplified CI/CD and deployment

## Project Structure

```
LedFx/
├── ledfx/
│   ├── effects/
│   │   ├── flame2_2d.py             # Python wrapper for flame2 effect
│   │   ├── twod.py                  # Base class for 2D effects
│   │   └── ...                      # Other effects
│   ├── rust/                        # Rust subsystem
│   │   ├── Cargo.toml               # Rust package configuration
│   │   ├── pyproject.toml           # Python build configuration for maturin
│   │   ├── src/
│   │   │   ├── lib.rs               # PyO3 module entry point and function exports
│   │   │   ├── common.rs            # Shared utilities (RNG, blur functions)
│   │   │   └── effects/
│   │   │       ├── mod.rs           # Effects module declarations
│   │   │       └── flame2.rs        # Flame2 effect implementation
│   │   ├── target/                  # Rust build artifacts (gitignored)
│   │   └── uv.lock                  # Dependency lock file
│   ├── presets.py                   # Includes flame2_2d presets
│   └── ...
├── pyproject.toml                   # Python package configuration
├── .vscode/                         # VS Code tasks and launch configs
└── .github/workflows/               # CI/CD pipelines
```

## Creating a New Rust Effect

### 1. Create New Effect File `ledfx/rust/src/effects/my_awesome.rs`

```rust
use pyo3::prelude::*;
use numpy::{PyArray3, PyReadonlyArray3, PyReadonlyArray1};
use ndarray::s;

/// Your new Rust effect function
///
/// Parameters:
/// - image_array: 3D array [height, width, 3] representing RGB image
/// - audio_bar: Audio beat/tempo information (0.0-1.0)
/// - audio_pow: Array of frequency powers [lows, mids, highs]
/// - intensity: Effect intensity multiplier (0.0-1.0)
/// - time_passed: Elapsed time in seconds
#[pyfunction]
pub fn my_awesome_effect(
    image_array: PyReadonlyArray3<u8>,
    _audio_bar: f64,
    audio_pow: PyReadonlyArray1<f32>,
    intensity: f64,
    _time_passed: f64,
) -> PyResult<Py<PyArray3<u8>>> {
    Python::with_gil(|py| {
        let array = image_array.as_array();
        let mut output = array.to_owned();
        let freq_powers = audio_pow.as_array();

        // Extract frequency bands
        let lows_power = (freq_powers[0] as f64 * intensity).min(1.0);
        let mids_power = (freq_powers[1] as f64 * intensity).min(1.0);
        let highs_power = (freq_powers[2] as f64 * intensity).min(1.0);

        let (height, width, _channels) = output.dim();

        // Your effect logic here
        // Use efficient ndarray operations for best performance

        // Example: Create a pulsing effect
        let pulse = (lows_power * 255.0) as u8;
        output.slice_mut(s![.., .., 0]).fill(pulse);           // Red
        output.slice_mut(s![.., .., 1]).fill((mids_power * 255.0) as u8);  // Green
        output.slice_mut(s![.., .., 2]).fill((highs_power * 255.0) as u8); // Blue

        Ok(PyArray3::from_owned_array_bound(py, output).into())
    })
}
```

### 2. Update `ledfx/rust/src/effects/mod.rs`

Add your new effect module:

```rust
pub mod flame2;
pub mod my_awesome;  // Add this line
```

### 3. Update `ledfx/rust/src/lib.rs`

Import and register your new effect function:

```rust
use pyo3::prelude::*;

mod common;
mod effects;

use effects::flame2::flame2_process;
use effects::my_awesome::my_awesome_effect;  // Add this import

#[pymodule]
fn ledfx_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(flame2_process, m)?)?;
    m.add_function(wrap_pyfunction!(my_awesome_effect, m)?)?;  // Add this line
    Ok(())
}
```

### 4. Update `Cargo.toml` (only if you need additional dependencies)

If your effect requires additional crates beyond the existing ones:

```toml
[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
numpy = "0.22"
ndarray = "0.16"

# Add additional dependencies here if needed for your specific effect
# rayon = "1.10"  # For parallel processing
# image = "0.25"  # For image processing utilities
# rand = "0.8"    # For additional randomization
```

## Python Integration

### Import Patterns

LedFx uses a consistent import pattern for Rust effects:

```python
# ✅ Recommended pattern - use this in your effects
try:
    from ledfx.rust import RUST_AVAILABLE, flame2_process, my_awesome_effect
except ImportError:
    RUST_AVAILABLE = False
    flame2_process = None
    my_awesome_effect = None
```

**Key Points:**
- Always import from `ledfx.rust` (not `ledfx_rust` directly)
- Import specific functions you need alongside `RUST_AVAILABLE`
- Use try/except to handle cases where Rust effects aren't available
- Set function variables to `None` on import failure for safe checking

**Why this pattern?**
- Consistent with LedFx's import conventions
- Provides clean abstraction over the compiled Rust module
- Allows graceful degradation when Rust effects aren't built
- Makes it easy to add new Rust functions without changing import style

### 1. Create Python Effect Wrapper

Create or modify `ledfx/effects/my_effect.py`:

```python
import logging
import numpy as np
import voluptuous as vol
from PIL import Image

from ledfx.effects.twod import Twod

try:
    from ledfx.rust import RUST_AVAILABLE, my_awesome_effect
except ImportError:
    RUST_AVAILABLE = False
    my_awesome_effect = None
    logging.warning("Rust effects module not available")

_LOGGER = logging.getLogger(__name__)

class MyAwesome(Twod):
    """My Awesome Rust Effect"""

    NAME = "My Awesome Effect"
    CATEGORY = "Matrix"
    # add keys you want hidden or in advanced here
    HIDDEN_KEYS = Twod.HIDDEN_KEYS + []
    ADVANCED_KEYS = Twod.ADVANCED_KEYS + []

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("intensity", description="Effect intensity", default=1.0):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        vol.Optional("custom_param", description="Custom parameter", default=0.5):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        # Add your custom parameters here
    })

    def __init__(self, ledfx, config):
        # Set any default values first, as config_updated will be called
        # from the super().__init__() which may depend on them
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust effects module not available")

        super().__init__(ledfx, config)

        _LOGGER.info("My Awesome Rust Effect initialized successfully")

    def config_updated(self, config):
        super().config_updated(config)
        # Copy over your configs here into variables
        self.intensity = self._config["intensity"]
        self.custom_param = self._config["custom_param"]

    def audio_data_updated(self, data):
        """Called when new audio data is available"""
        super().audio_data_updated(data)

        # Update your audio-related attributes here
        # These will be passed to the Rust function
        self.audio_bar = data.bar_oscillator()
        self.audio_pow = np.array(
            [
                data.lows_power(),
                data.mids_power(),
                data.high_power(),
            ],
            dtype=np.float32,
        )

    def draw(self):
        """Main drawing function called every frame"""
        if not RUST_AVAILABLE:
            return self._fill_red_error()

        try:
            # Prepare image array (height, width, 3) for RGB
            img_array = np.zeros((self.matrix_height, self.matrix_width, 3), dtype=np.uint8)

            # Call your Rust function
            result = my_awesome_effect(
                img_array,
                self.audio_bar,          # Beat/tempo info
                self.audio_pow,          # [lows, mids, highs] frequency powers
                self.intensity,          # Effect intensity from config
                self.passed             # Time passed
            )

            # Convert result to PIL Image and return
            return Image.fromarray(result, mode='RGB')

        except Exception as e:
            _LOGGER.error(f"Error in My Awesome Effect: {e}")
            return self._fill_red_error()
```

### 2. Effect Registration

Effects in LedFx are automatically discovered and registered when they:

1. **Inherit from the appropriate base class** (e.g., `Twod` for 2D effects)
2. **Set the `NAME` class variable** - This is the display name in the UI
3. **Set the `CATEGORY` class variable** - Groups effects in the UI (e.g., "Matrix", "Classic")
4. **Are placed in the `ledfx/effects/` directory**

**No additional registration is required** - LedFx automatically discovers effects that follow this pattern. The effect will appear in the UI once LedFx is restarted.

### 3. Real-World Example: Flame2 Effect

For a complete working example, see the Flame2 effect implementation:

**Python side**: `ledfx/effects/flame2_2d.py`
- Shows proper Rust import pattern with fallbacks
- Demonstrates configuration schema with validation
- Includes error handling and graceful degradation
- Example of correct data types for Rust function calls

**Rust side**: `ledfx/rust/src/effects/flame2.rs`
- Complete particle simulation system
- Audio-reactive parameters
- Efficient ndarray operations
- Performance optimizations

**Key patterns demonstrated:**
- Import handling: `try/except ImportError` for Rust availability
- Error boundaries: `_fill_red_error()` fallback for failures
- Data flow: Audio data → Rust processing → PIL Image output
- Configuration: Schema validation with proper types and ranges

## Build Process Integration

### VS Code Integration (Recommended)

The project includes comprehensive VS Code tasks and launch configurations for Rust development - this is the easiest way to get started:

#### VS Code Task: "Build Rust"

```json
{
    "label": "Build Rust",
    "detail": "Build Rust subsystem with automatic Rust installation",
    "type": "shell",
    "command": "${workspaceFolder}/.vscode/build-rust-auto.cmd",
    "options": {
        "cwd": "${workspaceFolder}"
    },
    "group": {
        "kind": "build",
        "isDefault": false
    },
    "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "shared"
    },
    "problemMatcher": ["$rustc"]
}
```

This task:
- Automatically installs Rust if missing
- Stops running LedFx processes before building
- Builds using `uv sync` (modern workspace approach)
- Can be run via Command Palette: "Tasks: Run Task" → "Build Rust"

#### VS Code Launch Configuration

```json
{
    "name": "LedFx (Rust Build, No Sentry, Open UI)",
    "type": "debugpy",
    "request": "launch",
    "program": "${workspaceFolder}/ledfx/__main__.py",
    "args": ["-vv", "--offline", "--open-ui"],
    "console": "integratedTerminal",
    "justMyCode": false,
    "preLaunchTask": "Build Rust",
    "presentation": {
        "group": "2 Rust Dev",
        "order": 0
    },
    "env": {
        "RUST_LOG": "debug",
        "RUST_BACKTRACE": "1"
    }
}
```

This launch configuration:
- Automatically builds Rust effects before launching LedFx
- Opens the UI automatically
- Enables Rust debug logging and backtraces
- Runs offline (no Sentry reporting)
- Available in the "2 Rust Dev" group in the debug panel

#### Windows Build Automation Script

The `.vscode/build-rust-auto.cmd` script handles:
- Automatic Rust installation via rustup
- Stopping running LedFx processes before building
- Building via `uv sync` (the modern workspace approach)

### Standard Build Commands

The standard approach uses uv workspace commands:

```bash
# Build entire workspace including Rust effects (from project root)
uv sync

# Test that the build works
uv run python -c "from ledfx.rust import RUST_AVAILABLE; print('Rust effects available:', RUST_AVAILABLE)"
```

## Performance Guidelines

### 1. Use Efficient ndarray Operations

```rust
// ❌ Slow - individual pixel access
for y in 0..height {
    for x in 0..width {
        output[(y, x, 0)] = value;
    }
}

// ✅ Fast - bulk operations
output.slice_mut(s![.., .., 0]).fill(value);

// ✅ Fast - parallel operations (with rayon)
output.axis_iter_mut(Axis(0))
    .into_par_iter()
    .enumerate()
    .for_each(|(y, mut row)| {
        // Process row
    });
```

### 2. Minimize Memory Allocations

```rust
// ✅ Reuse existing array
let array = image_array.as_array();
let mut output = array.to_owned(); // Single allocation

// ❌ Multiple allocations
let mut output = Array3::zeros((height, width, 3));
let temp_array = Array2::zeros((height, width)); // Unnecessary
```

### 3. Use Appropriate Data Types

```rust
// ✅ Use u8 for color values (0-255)
let color: u8 = (intensity * 255.0) as u8;

// ✅ Use f32 for calculations when possible
let result = value1 * value2; // Both f32

// ❌ Unnecessary precision
let result = value1 as f64 * value2 as f64; // If f32 is sufficient
```

### 4. Bounds Checking

```rust
// ✅ Safe bounds checking
if height > low_height {
    let start_y = height - low_height;
    output.slice_mut(s![start_y..height, .., 0]).fill(255);
}

// ❌ Potential panic
let start_y = height - low_height; // Could underflow
```

### 5. Thread Safety (for global state)

```rust
use std::sync::{Mutex, OnceLock};
use std::collections::HashMap;

// ✅ Thread-safe global state
static GLOBAL_STATE: OnceLock<Mutex<HashMap<u64, MyState>>> = OnceLock::new();

fn get_state(id: u64) -> MyState {
    let states = GLOBAL_STATE.get_or_init(|| Mutex::new(HashMap::new()));
    let mut states = states.lock().unwrap();
    states.get(&id).cloned().unwrap_or_default()
}

// ❌ Unsafe global state
static mut UNSAFE_STATE: HashMap<u64, MyState> = HashMap::new(); // Don't use this
```

## Troubleshooting

### Common Issues

1. **ImportError: No module named 'ledfx.rust' or import from ledfx.rust fails**

   This indicates the Rust effects module isn't built.

   Solution - use workspace build:
   ```bash
   # Use VS Code task "Build Rust Effects (with Auto-Install)" 
   # OR run from command line:
   uv sync
   ```

   Or use the VS Code task "Build Rust" for automatic installation.

2. **Compilation errors**
   ```bash
   # Update Rust
   rustup update

   # Check Cargo.toml dependencies
   # Ensure PyO3 and numpy versions are compatible
   # Current versions: PyO3 0.22, numpy 0.22, ndarray 0.16
   ```

3. **Runtime panics**
   - Add bounds checking in your Rust code
   - Use `saturating_sub()` for unsigned arithmetic
   - Validate input dimensions
   - Use thread-safe patterns for global state (OnceLock<Mutex<T>>)

4. **Performance issues**
   - Profile with `cargo bench` (if benchmarks are added)
   - Use `--release` builds for production  
   - Avoid unnecessary allocations
   - Build in release mode: Use VS Code task or `uv sync`

### Debugging

1. **Enable debug logging in Python**:
   ```python
   import logging
   logging.getLogger('ledfx.effects').setLevel(logging.DEBUG)
   ```

2. **Use Rust debugging**:
   ```rust
   #[cfg(debug_assertions)]
   eprintln!("Debug info: {}", value);
   ```

3. **VSCode debugging**:
   - Install rust-analyzer extension
   - Set breakpoints in Rust code
   - Use "Debug Python File" with Rust effects

### Getting Help

- **LedFx Discord**: Join for community support
- **GitHub Issues**: Report bugs or request features
- **Rust Documentation**: https://doc.rust-lang.org/
- **PyO3 Documentation**: https://pyo3.rs/

## Quick Reference

### Common Commands

```bash
# Build entire workspace including Rust effects (from project root)
uv sync

# Rebuild only Rust effects after changes (from project root)
uv run maturin develop --release --manifest-path ledfx/rust/Cargo.toml

# Test import
uv run python -c "from ledfx.rust import RUST_AVAILABLE; print('Rust effects available:', RUST_AVAILABLE)"

# Clean build artifacts
cd ledfx/rust && cargo clean

# Run LedFx with Rust effects (from project root)
uv run python -m ledfx --open-ui
```

### Directory Structure

```
LedFx/
├── ledfx/
│   ├── effects/
│   │   ├── flame2_2d.py             # Python wrapper for flame2 effect
│   │   ├── twod.py                  # Base class for 2D effects
│   │   └── ...                      # Other effects
│   ├── rust/                        # Rust effects module
│   │   ├── Cargo.toml               # Rust package configuration
│   │   ├── pyproject.toml           # Python build configuration for maturin
│   │   ├── src/
│   │   │   ├── lib.rs               # Main Rust effects library
│   │   │   ├── common.rs            # Shared utilities (RNG, blur functions)
│   │   │   └── effects/
│   │   │       ├── mod.rs           # Effects module declarations
│   │   │       └── flame2.rs        # Flame2 effect implementation
│   │   ├── target/                  # Rust build artifacts (gitignored)
│   │   └── uv.lock                  # Dependency lock file
│   ├── presets.py                   # Includes flame2_2d presets
│   └── ...
└── .github/workflows/               # CI/CD with Rust build steps
```

### Troubleshooting Quick Fixes

- **Module import error**: Run `uv sync` for fresh setup
- **Build errors**: Check if Rust is installed (`rustc --version`), or use `uv sync` for auto-install
- **Permission errors on Windows**: Stop any running LedFx instances
- **Missing dependencies**: Run `uv sync` (includes everything) or `uv sync --group dev`

## Example: Complete Effect Implementation

See the existing `flame2_2d.py` and `ledfx/rust/src/effects/flame2.rs` for a complete working example of a realistic flame effect with particle physics.

## Contributing

When contributing Rust effects:

1. Follow Rust naming conventions (snake_case)
2. Add comprehensive documentation
3. Include unit tests
4. Update this guide if you add new patterns
5. Test on multiple platforms if possible

## License

Rust effects are part of LedFx and are licensed under GPL-3.0.
