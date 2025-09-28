# VS Code Tasks

This document describes the available VS Code tasks for building and developing LedFx.

## Available Tasks

### Rust Development

#### 1. **Build Rust Effects (with Auto-Install)** ⭐ *Recommended*
- **Purpose**: Build Rust-based effects with automatic Rust installation if needed
- **What it does**:
  - Automatically detects if Rust is installed
  - If not found, downloads and installs Rust toolchain
  - Stops running LedFx processes before building
  - Builds using `uv sync` (modern workspace approach)
- **Cross-platform**: Works on Windows, Linux, and macOS
- **Use when**: You want a "just works" solution for any environment

#### 2. **Build Workspace (Recommended)**
- **Purpose**: Build entire workspace including Rust effects using uv workspace
- **What it does**: Runs `uv sync` to build everything
- **Use when**: You want the standard, comprehensive build

#### 3. **Build Rust Effects**
- **Purpose**: Build only Rust effects (requires Rust to be pre-installed)
- **What it does**: Targeted Rust build using `uv run maturin develop --release`
- **Use when**: Rust is already installed and you only want to rebuild Rust components
- **Purpose**: Install Rust toolchain if not present
- **What it does**: Downloads and installs Rust using rustup
- **Platform**: Windows only (uses PowerShell)
- **Use when**: You need to manually install Rust

#### 4. **Check Rust Installation**
- **Purpose**: Verify Rust toolchain is accessible
- **What it does**: Runs `rustc --version` with proper PATH setup
- **Cross-platform**: Works on all platforms
- **Use when**: You want to verify Rust is properly installed

### Documentation

#### 5. **Build Docs**
- **Purpose**: Build Sphinx documentation
- **Dependencies**: Automatically installs docs dependencies first
- **Output**: `docs/build/index.html`

#### 6. **Build and Open Docs**
- **Purpose**: Build docs and open in browser
- **Cross-platform**: Uses appropriate opener for each OS

### Utilities

#### 7. **Cleanup Debug Config Folder**
- **Purpose**: Remove debug_config folder for clean start
- **Cross-platform**: Works on Windows, Linux, macOS

#### 8. **Init Frontend submodule**
- **Purpose**: Initialize and update frontend Git submodule

## Quick Start

1. **For new developers**: Use "Build Rust Effects (with Auto-Install)" - it handles everything automatically
2. **For regular development**: Use "Build Workspace (Recommended)" for complete builds
3. **For targeted rebuilds**: Use "Build Rust Effects" for Rust-only changes
4. **For documentation**: Use "Build and Open Docs"

## Troubleshooting

### Rust Build Issues
- If you get "rustc not found" errors, use the "Install Rust Toolchain" task first
- On Windows, you may need to restart VS Code after installing Rust
- The auto-install task handles PATH updates automatically

### Documentation Build Issues
- Dependencies are installed automatically via the "Install Docs Dependencies" task
- Make sure you have Python and uv installed

### Path Issues
- All tasks are configured with proper PATH environment variables
- Windows: `%USERPROFILE%\.cargo\bin`
- Linux/macOS: `$HOME/.cargo/bin`

## Performance Notes

### First-time Rust Build
- Downloads ~8MB of crates
- Compiles all dependencies (~37 seconds)
- This is a one-time overhead

### Subsequent Rust Builds
- Uses cached dependencies
- Only recompiles changed code (~2-5 seconds)
- Much faster incremental builds

## Task Execution

You can run tasks via:
1. **Command Palette**: `Ctrl+Shift+P` → "Tasks: Run Task"
2. **Terminal menu**: Terminal → Run Task
3. **Keyboard shortcut**: `Ctrl+Shift+P` → search for task name
