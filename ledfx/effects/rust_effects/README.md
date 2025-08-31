# LedFx Rust Effects

High-performance audio-reactive effects for LedFx written in Rust.

## Quick Start

```bash
# Build the module
maturin develop

# Or build optimized version
maturin develop --release
```

## Current Effects

### `rusty_effect_process`
A three-bar frequency visualizer that displays:
- **Red bar** (left): Low frequencies
- **Green bar** (middle): Mid frequencies
- **Blue bar** (right): High frequencies

Each bar's height corresponds to the audio power in that frequency range.

## Adding New Effects

1. Add your function to `src/lib.rs`
2. Register it in the `ledfx_rust_effects` module
3. Create a Python wrapper in `../`
4. Rebuild with `maturin develop`

See the [main Rust Effects Guide](../../../docs/developer/rust_effects.md) for detailed instructions.

## Development

```bash
# Check code
cargo check

# Run tests
cargo test

# Format code
cargo fmt

# Lint code
cargo clippy
```

## Performance

This module uses optimized ndarray operations for maximum performance:
- Bulk array operations instead of pixel-by-pixel loops
- Efficient memory access patterns
- Minimal allocations

## Dependencies

- [PyO3](https://pyo3.rs/): Python-Rust bindings
- [numpy](https://github.com/PyO3/rust-numpy): NumPy array support
- [ndarray](https://docs.rs/ndarray/): N-dimensional arrays
