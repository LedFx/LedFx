# LedFx Rust Effects Developer Guide

This guide explains how to add high-performance Rust effects to LedFx and integrate them into the build process.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Creating a New Rust Effect](#creating-a-new-rust-effect)
5. [Python Integration](#python-integration)
6. [Build Process Integration](#build-process-integration)
7. [Testing Your Effect](#testing-your-effect)
8. [Distribution and CI/CD](#distribution-and-cicd)
9. [Performance Guidelines](#performance-guidelines)
10. [Troubleshooting](#troubleshooting)

## Overview

LedFx uses Rust effects to provide high-performance audio-reactive visualizations. Rust effects are compiled into Python modules using [maturin](https://github.com/PyO3/maturin) and [PyO3](https://github.com/PyO3/pyo3), offering significant performance benefits over pure Python implementations.

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

# Install development dependencies (includes maturin)
uv sync --dev

# Verify Rust installation
rustc --version
cargo --version
```

## Project Structure

```
LedFx/
├── rust_effects/                    # Rust effects module
│   ├── Cargo.toml                   # Rust package configuration
│   ├── src/
│   │   └── lib.rs                   # Main Rust effects library
│   └── target/                      # Rust build artifacts
├── ledfx/
│   ├── effects/
│   │   └── rusty2d.py              # Python wrapper for Rust effects
│   └── ...
├── pyproject.toml                   # Python package configuration
└── .github/workflows/               # CI/CD pipelines
```

## Creating a New Rust Effect

### 1. Add Function to `rust_effects/src/lib.rs`

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
fn my_awesome_effect(
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

        Ok(PyArray3::from_owned_array(py, output).to_owned())
    })
}

// Register your function in the module
#[pymodule]
fn ledfx_rust_effects(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rusty_effect_process, m)?)?;
    m.add_function(wrap_pyfunction!(my_awesome_effect, m)?)?;  // Add this line
    Ok(())
}
```

### 2. Update `Cargo.toml` (if needed)

```toml
[package]
name = "ledfx-rust-effects"
version = "0.1.0"
edition = "2021"

[lib]
name = "ledfx_rust_effects"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
numpy = "0.22"
ndarray = "0.16"

# Add additional dependencies here if needed
# rayon = "1.10"  # For parallel processing
# image = "0.25"  # For image processing utilities
```

## Python Integration

### 1. Create Python Effect Wrapper

Create or modify `ledfx/effects/my_effect.py`:

```python
import logging
import numpy as np
from PIL import Image

from ledfx.effects.twod import Twod2Effect

try:
    import ledfx_rust_effects
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust effects module not available")

_LOGGER = logging.getLogger(__name__)

@Effect.no_registration
class MyAwesome(Twod2Effect):
    """My Awesome Rust Effect"""

    NAME = "My Awesome Effect"
    CATEGORY = "Matrix"
    HIDDEN = not RUST_AVAILABLE

    CONFIG_SCHEMA = vol.Schema({
        vol.Optional("intensity", description="Effect intensity", default=1.0):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
        vol.Optional("rust_param", description="Custom parameter", default=0.5):
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
        # Add your custom parameters here
    })

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust effects module not available")

        # Initialize your effect-specific attributes
        self.rust_param = self._config.get("rust_param", 0.5)

        _LOGGER.info("My Awesome Rust Effect initialized successfully")

    def audio_data_updated(self, data):
        """Called when new audio data is available"""
        super().audio_data_updated(data)

        # Update your audio-related attributes here
        # These will be passed to the Rust function

    def draw(self):
        """Main drawing function called every frame"""
        if not RUST_AVAILABLE:
            return self._fill_red_error()

        try:
            # Prepare image array (height, width, 3) for RGB
            img_array = np.zeros((self.matrix_height, self.matrix_width, 3), dtype=np.uint8)

            # Call your Rust function
            result = ledfx_rust_effects.my_awesome_effect(
                img_array,
                self.audio_bar,          # Beat/tempo info
                self.audio_pow,          # [lows, mids, highs] frequency powers
                self._config.get("intensity", 1.0),
                self.passed             # Time passed
            )

            # Convert result to PIL Image and return
            return Image.fromarray(result, mode='RGB')

        except Exception as e:
            _LOGGER.error(f"Error in My Awesome Effect: {e}")
            return self._fill_red_error()
```

### 2. Register Your Effect

Add your effect to `ledfx/effects/__init__.py` if it's not auto-discovered.

## Build Process Integration

### Development Build

```bash
# Navigate to rust_effects directory
cd rust_effects

# Build and install the Rust module for development
maturin develop

# Or build in release mode for better performance
maturin develop --release
```

### Production Build

The production build process needs to be integrated into the existing CI/CD pipeline.

#### Update `pyproject.toml`

Ensure maturin is in the dev dependencies:

```toml
[dependency-groups]
dev = [
    # ... existing dependencies
    "maturin>=1.9.4",
    # ... other dependencies
]
```

#### Update GitHub Actions Workflows

##### 1. Update `.github/workflows/ci-build.yml`

Add Rust installation and build steps:

```yaml
jobs:
  build-ledfx-linux:
    name: Build LedFx (Ubuntu)
    runs-on: ubuntu-latest
    # ... existing configuration
    steps:
      - name: Check out code from GitHub
        uses: actions/checkout@v4

      # Add Rust installation
      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
          override: true
          components: rustfmt, clippy

      - name: Install build dependencies
        run: |
          sudo apt-get update && sudo apt-get install -y \
          gcc libatlas3-base portaudio19-dev

      # ... existing steps

      - name: Install LedFx
        run: |
          export CFLAGS="-Wno-incompatible-function-pointer-types"
          uv sync --all-extras --dev

      # Add Rust effects build
      - name: Build Rust Effects
        run: |
          cd rust_effects
          uv run maturin develop --release

      # ... rest of existing steps
```

##### 2. Update `.github/workflows/test-build-binaries.yml`

Add Rust build steps to all platform builds:

```yaml
  build-ledfx-windows:
    name: Build LedFx (Windows)
    runs-on: windows-latest
    steps:
      # ... existing steps

      # Add Rust installation
      - name: Install Rust
        uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
          override: true

      - name: Install LedFx
        run: |
          uv sync --python ${{ env.DEFAULT_PYTHON }} --extra hue --dev

      # Add Rust effects build
      - name: Build Rust Effects
        run: |
          cd rust_effects
          uv run maturin develop --release

      # ... rest of existing steps
```

#### Add New VSCode Task

Update `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        // ... existing tasks
        {
            "label": "Build Rust Effects",
            "detail": "Build Rust effects module",
            "type": "shell",
            "command": "uv",
            "args": ["run", "maturin", "develop", "--release"],
            "group": "build",
            "options": {
                "cwd": "${workspaceFolder}/rust_effects"
            },
            "presentation": {
                "reveal": "always",
                "focus": false
            },
            "problemMatcher": ["$rustc"]
        },
        {
            "label": "Build Rust Effects (Debug)",
            "detail": "Build Rust effects module in debug mode",
            "type": "shell",
            "command": "uv",
            "args": ["run", "maturin", "develop"],
            "group": "build",
            "options": {
                "cwd": "${workspaceFolder}/rust_effects"
            },
            "presentation": {
                "reveal": "always",
                "focus": false
            },
            "problemMatcher": ["$rustc"]
        }
    ]
}
```

## Testing Your Effect

### 1. Build and Test Locally

```bash
# Build the Rust module
cd rust_effects
maturin develop

# Run LedFx
cd ..
uv run python -m ledfx --open-ui

# Your effect should appear in the effects list
```

### 2. Testing Framework

Create tests in `tests/test_rust_effects.py`:

```python
import pytest
import numpy as np

try:
    import ledfx_rust_effects
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust effects not available")
def test_my_awesome_effect():
    """Test the Rust effect function directly"""
    # Create test data
    height, width = 32, 64
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    audio_pow = np.array([0.5, 0.3, 0.7], dtype=np.float32)

    # Call the function
    result = ledfx_rust_effects.my_awesome_effect(
        img_array, 0.5, audio_pow, 1.0, 0.0
    )

    # Verify the result
    assert result.shape == (height, width, 3)
    assert result.dtype == np.uint8

    # Add specific assertions for your effect
    assert np.any(result > 0)  # Effect should produce some output
```

## Distribution and CI/CD

### Binary Distribution

For distribution, Rust effects need to be pre-compiled for each platform:

#### Option 1: Include in Main Build (Recommended)

Modify the existing binary build process to include Rust effects:

1. **Update PyInstaller specs** (`windows-binary.spec`, `osx-binary.spec`):
   ```python
   # Add to hidden imports
   hiddenimports=['ledfx_rust_effects']
   ```

2. **Pre-build Rust wheels** in CI before PyInstaller:
   ```yaml
   - name: Build Rust Wheels
     run: |
       cd rust_effects
       uv run maturin build --release --interpreter python
   ```

#### Option 2: Separate Rust Wheels (Advanced)

Create separate wheel distributions for the Rust module:

```yaml
# New workflow: .github/workflows/build-rust-wheels.yml
name: Build Rust Wheels

on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build-wheels:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - uses: PyO3/maturin-action@v1
        with:
          working-directory: rust_effects
          target: ${{ matrix.target }}
          args: --release --out dist --interpreter 3.9 3.10 3.11 3.12
      - uses: actions/upload-artifact@v4
        with:
          name: rust-wheels-${{ matrix.os }}
          path: rust_effects/dist
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

## Troubleshooting

### Common Issues

1. **ImportError: No module named 'ledfx_rust_effects'**
   ```bash
   cd rust_effects
   maturin develop
   ```

2. **Compilation errors**
   ```bash
   # Update Rust
   rustup update

   # Check Cargo.toml dependencies
   # Ensure PyO3 and numpy versions are compatible
   ```

3. **Runtime panics**
   - Add bounds checking in your Rust code
   - Use `saturating_sub()` for unsigned arithmetic
   - Validate input dimensions

4. **Performance issues**
   - Profile with `cargo bench`
   - Use `--release` builds for production
   - Avoid unnecessary allocations

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

## Example: Complete Effect Implementation

See the existing `rusty2d.py` and `rust_effects/src/lib.rs` for a complete working example of a three-bar frequency visualizer.

## Contributing

When contributing Rust effects:

1. Follow Rust naming conventions (snake_case)
2. Add comprehensive documentation
3. Include unit tests
4. Update this guide if you add new patterns
5. Test on multiple platforms if possible

## License

Rust effects are part of LedFx and are licensed under GPL-3.0.
