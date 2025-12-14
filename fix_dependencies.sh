#!/bin/bash

###############################################################################
# Post-Deployment Dependency Fix Script
#
# This script installs missing dependencies after deployment
# Handles Python 3.11+ externally-managed-environment restrictions
###############################################################################

set -e

PI_HOST="pi@pi6.local"
PI_PASSWORD="pass"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_on_pi() {
    sshpass -p "$PI_PASSWORD" ssh -o StrictHostKeyChecking=no "$PI_HOST" "$@"
}

print_status "Installing LedFx dependencies on Raspberry Pi..."

# Check Python version
PYTHON_VERSION=$(run_on_pi "python3 --version 2>&1 | awk '{print \$2}'")
print_status "Python version: $PYTHON_VERSION"

# Determine installation method
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    INSTALL_FLAGS="--user --break-system-packages"
    print_status "Using --user --break-system-packages flags for Python 3.11+"
else
    INSTALL_FLAGS="--user"
    print_status "Using --user flag for installation"
fi

# Find LedFx installation directory
LEDFX_DIR=$(run_on_pi "python3 -c 'import ledfx; import os; print(os.path.dirname(ledfx.__file__))' 2>/dev/null" || echo "")
if [ -z "$LEDFX_DIR" ] || [ "$LEDFX_DIR" = "None" ]; then
    print_error "Could not find LedFx installation. Please run deploy_to_pi.sh first."
    exit 1
fi

print_status "Found LedFx at: $LEDFX_DIR"
LEDFX_PARENT=$(run_on_pi "dirname '$LEDFX_DIR'")

# Install core dependencies
print_status "Installing core dependencies..."
run_on_pi "python3 -m pip install $INSTALL_FLAGS --upgrade pip setuptools wheel" || true

# Install LedFx dependencies from pyproject.toml if available
if run_on_pi "[ -f '$LEDFX_PARENT/../pyproject.toml' ]"; then
    print_status "Installing from pyproject.toml..."
    run_on_pi "cd '$LEDFX_PARENT/..' && python3 -m pip install $INSTALL_FLAGS -e ." || {
        print_warning "Installation from pyproject.toml failed, installing dependencies manually..."
        run_on_pi "python3 -m pip install $INSTALL_FLAGS numpy aiohttp aiohttp-cors voluptuous sounddevice samplerate aubio-ledfx psutil pyserial pystray python-rtmidi requests sacn sentry-sdk zeroconf pillow flux-led python-osc pybase64 mss netifaces2 packaging xled" || true
    }
else
    print_status "Installing dependencies manually..."
    # Install all dependencies from pyproject.toml
    run_on_pi "python3 -m pip install $INSTALL_FLAGS numpy aiohttp aiohttp-cors voluptuous sounddevice samplerate aubio-ledfx psutil pyserial pystray python-rtmidi requests sacn sentry-sdk zeroconf pillow flux-led python-osc pybase64 mss netifaces2 packaging xled python-dotenv cffi wheel certifi multidict paho-mqtt openrgb-python icmplib uvloop rpi-ws281x stupidartnet vnoise" || true
fi

# Install optional librosa
print_status "Installing optional librosa dependency..."
run_on_pi "python3 -m pip install $INSTALL_FLAGS 'librosa>=0.10.0'" || {
    print_warning "Librosa installation failed (optional - mood detection will work without it)"
}

# Verify installation
print_status "Verifying installation..."
if run_on_pi "python3 -c 'from ledfx.mood_detector import MoodDetector; print(\"✓ MoodDetector imported successfully\")' 2>&1"; then
    print_status "✓ All dependencies installed successfully!"
    print_status ""
    print_status "You can now start LedFx:"
    print_status "  ssh $PI_HOST 'python3 -m ledfx'"
else
    print_warning "Some dependencies may still be missing."
    print_warning "Try running LedFx and check the error messages."
fi

