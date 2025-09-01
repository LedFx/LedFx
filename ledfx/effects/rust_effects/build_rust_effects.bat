@echo off
setlocal enabledelayedexpansion

REM LedFx Rust Effects Builder for Windows
REM Batch script to build Rust-based effects for LedFx

echo 🦀 LedFx Rust Effects Builder (Windows)
echo ====================================

REM Check if Rust is installed
where rustc >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Rust is not installed or not in PATH
    set /p install="Would you like to install Rust automatically? (y/n): "
    if /i "!install!" == "y" (
        echo 📦 Installing Rust toolchain...
        powershell -Command "Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe; .\rustup-init.exe -y; Remove-Item rustup-init.exe"
        set PATH=%PATH%;%USERPROFILE%\.cargo\bin
        echo ✅ Rust installed successfully!
        echo ⚠️  You may need to restart your command prompt for PATH changes to take effect
    ) else (
        echo ❌ Rust is required to build effects. Please install it from https://rustup.rs/
        pause
        exit /b 1
    )
) else (
    echo ✅ Rust is already installed:
    rustc --version
    cargo --version
)

REM Check if uv is available
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv is not installed or not in PATH
    echo Please install uv first: pip install uv
    pause
    exit /b 1
)

echo ✅ uv is available
uv --version

REM Navigate to rust effects directory
set SCRIPT_DIR=%~dp0
set RUST_EFFECTS_DIR=%SCRIPT_DIR%

if not exist "%RUST_EFFECTS_DIR%\Cargo.toml" (
    echo ❌ Cargo.toml not found in: %RUST_EFFECTS_DIR%
    echo This script should be run from the rust_effects directory
    pause
    exit /b 1
)

echo 📁 Working in rust effects directory: %RUST_EFFECTS_DIR%
cd /d "%RUST_EFFECTS_DIR%"

REM Build the Rust effects
echo 🔨 Building Rust effects...
echo This may take a while on the first run as dependencies are downloaded and compiled...

uv run --with maturin maturin develop --release
if %errorlevel% equ 0 (
    echo 🎉 Rust effects built successfully!
    echo The effects are now available for use in LedFx.
) else (
    echo ❌ Failed to build Rust effects
    echo Please check the error messages above and ensure:
    echo   - Rust toolchain is properly installed
    echo   - You're in a Python virtual environment with maturin installed
    echo   - All dependencies are available
    pause
    exit /b 1
)

pause
