#!/bin/bash

# LedFx Rust Effects Builder
# Cross-platform script to build Rust-based effects for LedFx

set -e  # Exit on any error

echo "🦀 LedFx Rust Effects Builder"
echo "================================"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install Rust on Unix-like systems
install_rust_unix() {
    echo "📦 Installing Rust toolchain..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
    echo "✅ Rust installed successfully!"
}

# Function to install Rust on Windows (requires PowerShell)
install_rust_windows() {
    echo "📦 Installing Rust toolchain for Windows..."
    powershell -Command "Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe; .\rustup-init.exe -y; Remove-Item rustup-init.exe"
    export PATH="$PATH:$USERPROFILE/.cargo/bin"
    echo "✅ Rust installed successfully!"
}

# Check operating system
OS=$(uname -s)
case "$OS" in
    Linux*|Darwin*)
        PLATFORM="unix"
        ;;
    CYGWIN*|MINGW*|MSYS*)
        PLATFORM="windows"
        ;;
    *)
        echo "❌ Unsupported operating system: $OS"
        exit 1
        ;;
esac

# Check if Rust is installed
if command_exists rustc; then
    echo "✅ Rust is already installed:"
    rustc --version
    cargo --version
else
    echo "⚠️  Rust is not installed or not in PATH"
    read -p "Would you like to install Rust automatically? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ "$PLATFORM" = "unix" ]; then
            install_rust_unix
        else
            install_rust_windows
        fi
    else
        echo "❌ Rust is required to build effects. Please install it from https://rustup.rs/"
        exit 1
    fi
fi

# Check if uv is available
if ! command_exists uv; then
    echo "❌ uv is not installed or not in PATH"
    echo "Please install uv first: pip install uv"
    exit 1
fi

echo "✅ uv is available: $(uv --version)"

# Navigate to rust effects directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUST_EFFECTS_DIR="$SCRIPT_DIR"

if [ ! -f "$RUST_EFFECTS_DIR/Cargo.toml" ]; then
    echo "❌ Cargo.toml not found in: $RUST_EFFECTS_DIR"
    echo "This script should be run from the rust_effects directory"
    exit 1
fi

echo "📁 Working in rust effects directory: $RUST_EFFECTS_DIR"
cd "$RUST_EFFECTS_DIR"

# Build the Rust effects
echo "🔨 Building Rust effects..."
echo "This may take a while on the first run as dependencies are downloaded and compiled..."

if uv run --with maturin maturin develop --release; then
    echo "🎉 Rust effects built successfully!"
    echo "The effects are now available for use in LedFx."
else
    echo "❌ Failed to build Rust effects"
    echo "Please check the error messages above and ensure:"
    echo "  - Rust toolchain is properly installed"
    echo "  - You're in a Python virtual environment with maturin installed"
    echo "  - All dependencies are available"
    exit 1
fi
