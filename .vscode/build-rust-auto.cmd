@echo off
echo 🔧 Checking for Rust installation...

REM Check if rustc is available
where rustc >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Rust is already installed
    goto :build
)

echo 🚀 Rust not found, installing automatically...

REM Download and install rustup
echo Downloading rustup installer...
powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe"

if not exist rustup-init.exe (
    echo ❌ Failed to download rustup installer
    exit /b 1
)

echo Installing Rust toolchain...
rustup-init.exe -y

if %errorlevel% neq 0 (
    echo ❌ Rust installation failed
    del rustup-init.exe 2>nul
    exit /b 1
)

del rustup-init.exe 2>nul

echo ✅ Rust installed successfully

REM Add Rust to PATH for this session
set PATH=%PATH%;%USERPROFILE%\.cargo\bin

:build
echo 🔨 Building Rust effects...

REM Change to rust effects directory
cd /d "%~dp0..\ledfx\effects\rust_effects"

if not exist Cargo.toml (
    echo ❌ Cargo.toml not found in rust_effects directory
    exit /b 1
)

REM Build with maturin
set PATH=%PATH%;%USERPROFILE%\.cargo\bin
echo 🔧 Updated PATH for this session: %USERPROFILE%\.cargo\bin
echo 🔨 Running: uv run --with maturin maturin develop --release

REM Try building with updated PATH and auto-install maturin
uv run --with maturin maturin develop --release

if %errorlevel% equ 0 (
    echo ✅ Rust effects built successfully!
) else (
    echo ❌ Build failed
    exit /b 1
)

echo.
echo 📝 Note: If this was a fresh Rust installation, you may need to restart
echo    VS Code or reload the window for PATH changes to take effect globally.
