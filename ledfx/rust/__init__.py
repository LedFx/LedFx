"""
LedFx Rust Effects Module

This module provides access to high-performance Rust-based effects.
"""

# Import the compiled Rust module and expose its functionality
try:
    import ledfx_rust as _ledfx_rust_backend

    # Expose all functions from the Rust backend
    flame2_process = _ledfx_rust_backend.flame2_process

    # Check if flame2_release is available (it might not be exported)
    if hasattr(_ledfx_rust_backend, "flame2_release"):
        flame2_release = _ledfx_rust_backend.flame2_release

    # Module is available
    RUST_AVAILABLE = True

except ImportError:
    # Rust module not available, provide None placeholders
    flame2_process = None
    flame2_release = None
    RUST_AVAILABLE = False

__all__ = ["flame2_process", "flame2_release", "RUST_AVAILABLE"]
