@echo off
echo Checking for Rust installation...

REM Check if rustc is available
where rustc >nul 2>&1
if %errorlevel% equ 0 (
    echo Rust is already installed
    goto :build
)

echo Rust not found, installing automatically...

REM Download and install rustup
echo Downloading rustup installer...
powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe"

if not exist rustup-init.exe (
    echo Failed to download rustup installer
    exit /b 1
)

echo Installing Rust toolchain...
rustup-init.exe -y

if %errorlevel% neq 0 (
    echo Rust installation failed
    del rustup-init.exe 2>nul
    exit /b 1
)

del rustup-init.exe 2>nul
echo Rust installed successfully

REM Add Rust to PATH for this session
set PATH=%PATH%;%USERPROFILE%\.cargo\bin

:build
echo Stopping any running LedFx processes...
powershell -ExecutionPolicy Bypass -File "%~dp0stop-ledfx.ps1"

echo Building Rust effects...
cd /d "%~dp0.."

echo Building workspace with uv sync...
uv sync

if %errorlevel% equ 0 (
    echo Rust effects built successfully!
) else (
    echo Build failed
    exit /b 1
)
