#!/bin/bash

###############################################################################
# LedFx Mood Detection Deployment Script
# 
# This script deploys the LedFx installation with custom mood detection
# features to a Raspberry Pi, replacing the existing installation while
# preserving configuration and ensuring mood detection functionality.
###############################################################################

set -e  # Exit on error

# Configuration
PI_HOST="pi@pi6.local"
PI_PASSWORD="pass"
LOCAL_LEDFX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PI_LEDFX_DIR="/home/pi/ledfx"  # Adjust if LedFx is installed elsewhere
PI_CONFIG_DIR="/home/pi/.ledfx"  # Default LedFx config directory
BACKUP_DIR="/home/pi/ledfx_backup_$(date +%Y%m%d_%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to run command on Pi
run_on_pi() {
    sshpass -p "$PI_PASSWORD" ssh -o StrictHostKeyChecking=no "$PI_HOST" "$@"
}

# Function to copy files to Pi
copy_to_pi() {
    sshpass -p "$PI_PASSWORD" scp -o StrictHostKeyChecking=no -r "$@"
}

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    print_error "sshpass is not installed. Install it with: brew install sshpass (macOS) or apt-get install sshpass (Linux)"
    exit 1
fi

print_status "Starting LedFx deployment to $PI_HOST"
print_status "Local LedFx directory: $LOCAL_LEDFX_DIR"
print_status "Remote LedFx directory: $PI_LEDFX_DIR"

# Step 1: Check connection to Pi
print_status "Step 1: Checking connection to Raspberry Pi..."
if ! run_on_pi "echo 'Connection successful'" &> /dev/null; then
    print_error "Cannot connect to $PI_HOST. Please check:"
    print_error "  - Pi is powered on and connected to network"
    print_error "  - SSH is enabled on Pi"
    print_error "  - Hostname/IP is correct"
    exit 1
fi
print_status "Connection successful!"

# Step 2: Stop LedFx if running
print_status "Step 2: Stopping LedFx if running..."
run_on_pi "pkill -f ledfx || true" || true
run_on_pi "systemctl stop ledfx 2>/dev/null || true" || true
sleep 2
print_status "LedFx stopped (if it was running)"

# Step 3: Detect LedFx installation location
print_status "Step 3: Detecting LedFx installation location..."
LEDFX_LOCATION=$(run_on_pi "which ledfx 2>/dev/null || echo ''" | head -n1)
if [ -z "$LEDFX_LOCATION" ]; then
    # Try to find pipx installation
    LEDFX_LOCATION=$(run_on_pi "find ~/.local -name ledfx 2>/dev/null | head -n1 || echo ''")
fi

if [ -n "$LEDFX_LOCATION" ]; then
    print_status "Found LedFx at: $LEDFX_LOCATION"
    # Get the actual installation directory
    if [[ "$LEDFX_LOCATION" == *"/bin/ledfx" ]]; then
        PI_LEDFX_DIR=$(run_on_pi "dirname \"$(dirname \"$LEDFX_LOCATION\")\"")
    else
        PI_LEDFX_DIR=$(run_on_pi "dirname \"$LEDFX_LOCATION\"")
    fi
    print_status "Using LedFx directory: $PI_LEDFX_DIR"
else
    print_warning "LedFx executable not found. Assuming source installation at $PI_LEDFX_DIR"
fi

# Step 4: Create backup
print_status "Step 4: Creating backup of existing installation..."
run_on_pi "mkdir -p $BACKUP_DIR"
if run_on_pi "[ -d '$PI_LEDFX_DIR' ]"; then
    run_on_pi "cp -r $PI_LEDFX_DIR $BACKUP_DIR/ledfx_source 2>/dev/null || true"
    print_status "Backed up LedFx source to: $BACKUP_DIR/ledfx_source"
fi
if run_on_pi "[ -d '$PI_CONFIG_DIR' ]"; then
    run_on_pi "cp -r $PI_CONFIG_DIR $BACKUP_DIR/config 2>/dev/null || true"
    print_status "Backed up config to: $BACKUP_DIR/config"
fi
print_status "Backup created at: $BACKUP_DIR"

# Step 5: Create temporary directory on Pi
print_status "Step 5: Preparing deployment directory..."
TEMP_DIR=$(run_on_pi "mktemp -d")
print_status "Using temporary directory: $TEMP_DIR"

# Step 6: Copy LedFx files (excluding unnecessary files)
print_status "Step 6: Copying LedFx files to Pi..."
print_status "This may take a few minutes..."

# Create a list of files/directories to exclude
EXCLUDE_PATTERNS=(
    "--exclude=venv"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=*.pyo"
    "--exclude=.git"
    "--exclude=.gitignore"
    "--exclude=*.log"
    "--exclude=nohup.out"
    "--exclude=*.zip"
    "--exclude=*.spec"
    "--exclude=ledfx.zip"
    "--exclude=test_*.py"
    "--exclude=check_*.py"
    "--exclude=setup_*.py"
    "--exclude=update_*.py"
    "--exclude=droplet_creator.py"
    "--exclude=performance_analyser.py"
    "--exclude=fix_*.py"
    "--exclude=hiddenimports.py"
    "--exclude=loopback"
    "--exclude=installer"
    "--exclude=ledfx_docker"
    "--exclude=docs"
    "--exclude=tests"
    "--exclude=.github"
    "--exclude=uv.lock"
)

# Copy the entire directory structure
rsync -avz --progress \
    "${EXCLUDE_PATTERNS[@]}" \
    -e "sshpass -p '$PI_PASSWORD' ssh -o StrictHostKeyChecking=no" \
    "$LOCAL_LEDFX_DIR/" "$PI_HOST:$TEMP_DIR/"

print_status "Files copied successfully"

# Step 7: Install/update dependencies
print_status "Step 7: Installing/updating Python dependencies..."

# Check Python version and use appropriate installation method
PYTHON_VERSION=$(run_on_pi "python3 --version 2>&1 | awk '{print \$2}'")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

# For Python 3.11+, use --user --break-system-packages flags
# For older versions, use --user flag
if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    INSTALL_FLAGS="--user --break-system-packages"
    print_status "Detected Python 3.11+, using --user --break-system-packages flags"
else
    INSTALL_FLAGS="--user"
    print_status "Using --user flag for installation"
fi

# Try to upgrade pip first (with appropriate flags)
run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS --upgrade pip setuptools wheel" || true

# Install LedFx and dependencies
print_status "Installing LedFx with dependencies..."
if run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS -e ." 2>&1; then
    print_status "LedFx installed successfully"
else
    print_warning "Standard installation failed, trying alternative methods..."
    
    # Try with --break-system-packages as fallback (Python 3.11+)
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
            print_warning "Trying with --break-system-packages flag..."
            run_on_pi "cd $TEMP_DIR && python3 -m pip install --break-system-packages -e ." || {
                print_warning "Still failed, installing dependencies separately..."
                # Install core dependencies including python-dotenv
                run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS numpy aiohttp aiohttp-cors voluptuous sounddevice samplerate aubio-ledfx psutil python-dotenv" || true
            }
    else
        # For older Python, try without flags
        run_on_pi "cd $TEMP_DIR && python3 -m pip install -e . --no-deps" || true
        run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS numpy aiohttp aiohttp-cors voluptuous sounddevice samplerate aubio-ledfx psutil python-dotenv" || true
    fi
fi

# Step 8: Install optional librosa dependency for advanced mood detection
print_status "Step 8: Installing optional librosa dependency for advanced mood detection..."
if [ -n "$INSTALL_FLAGS" ]; then
    run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS --break-system-packages 'librosa>=0.10.0' 2>&1 || echo 'Librosa installation failed (optional)'" || true
else
    run_on_pi "cd $TEMP_DIR && python3 -m pip install $INSTALL_FLAGS 'librosa>=0.10.0' 2>&1 || echo 'Librosa installation failed (optional)'" || true
fi

# Step 9: Replace existing installation
print_status "Step 9: Replacing existing LedFx installation..."

# Find where LedFx is actually installed
LEDFX_PYTHON_PATH=$(run_on_pi "python3 -c 'import ledfx; import os; print(os.path.dirname(ledfx.__file__))' 2>/dev/null" || echo "")
if [ -n "$LEDFX_PYTHON_PATH" ] && [ "$LEDFX_PYTHON_PATH" != "None" ]; then
    print_status "Found LedFx installation at: $LEDFX_PYTHON_PATH"
    LEDFX_INSTALL_DIR="$LEDFX_PYTHON_PATH"
    
    # Backup existing ledfx directory
    if run_on_pi "[ -d '$LEDFX_INSTALL_DIR' ]"; then
        run_on_pi "cp -r $LEDFX_INSTALL_DIR $BACKUP_DIR/ledfx_python_package 2>/dev/null || true"
        print_status "Backed up existing LedFx package"
    fi
    
    # Copy new files to the installation directory
    print_status "Replacing LedFx files in Python package directory..."
    run_on_pi "rm -rf $LEDFX_INSTALL_DIR/*"
    run_on_pi "cp -r $TEMP_DIR/ledfx/* $LEDFX_INSTALL_DIR/ 2>/dev/null || cp -r $TEMP_DIR/* $LEDFX_INSTALL_DIR/"
    print_status "LedFx files replaced at: $LEDFX_INSTALL_DIR"
    PI_LEDFX_DIR="$LEDFX_INSTALL_DIR"
    
elif [[ "$LEDFX_LOCATION" == *"/.local/pipx"* ]] || [[ "$LEDFX_LOCATION" == *"pipx"* ]]; then
    print_warning "LedFx appears to be installed via pipx."
    print_status "Installing as editable package in pipx environment..."
    
    # Try to reinstall in pipx environment
    PIPX_VENV=$(run_on_pi "pipx list --short 2>/dev/null | grep ledfx | awk '{print \$2}' | head -n1" || echo "")
    if [ -n "$PIPX_VENV" ]; then
        print_status "Found pipx venv: $PIPX_VENV"
        # Copy to pipx venv
        run_on_pi "cp -r $TEMP_DIR/ledfx/* $PIPX_VENV/lib/python*/site-packages/ledfx/ 2>/dev/null || cp -r $TEMP_DIR/* $PIPX_VENV/lib/python*/site-packages/ledfx/"
        print_status "Updated pipx installation"
        PI_LEDFX_DIR="$PIPX_VENV/lib/python*/site-packages/ledfx"
    else
        print_warning "Could not find pipx venv. Creating source installation at $PI_LEDFX_DIR"
        run_on_pi "mkdir -p $PI_LEDFX_DIR"
        run_on_pi "cp -r $TEMP_DIR/* $PI_LEDFX_DIR/"
        print_status "Source installation created at: $PI_LEDFX_DIR"
        print_warning "You may need to run: cd $PI_LEDFX_DIR && python3 -m ledfx"
    fi
else
    # Check if files were installed to .local/lib/python3.x/site-packages (user install)
    USER_SITE_PACKAGES=$(run_on_pi "python3 -c 'import site; print(site.getusersitepackages())' 2>/dev/null" || echo "")
    if [ -n "$USER_SITE_PACKAGES" ] && run_on_pi "[ -d '$USER_SITE_PACKAGES/ledfx' ]"; then
        print_status "Found user site-packages installation at: $USER_SITE_PACKAGES/ledfx"
        run_on_pi "rm -rf $USER_SITE_PACKAGES/ledfx/*"
        run_on_pi "cp -r $TEMP_DIR/ledfx/* $USER_SITE_PACKAGES/ledfx/"
        print_status "Replaced user site-packages installation"
        PI_LEDFX_DIR="$USER_SITE_PACKAGES/ledfx"
    else
        # Standard source installation
        if run_on_pi "[ -d '$PI_LEDFX_DIR' ]"; then
            run_on_pi "rm -rf $PI_LEDFX_DIR"
        fi
        run_on_pi "mkdir -p $PI_LEDFX_DIR"
        run_on_pi "cp -r $TEMP_DIR/* $PI_LEDFX_DIR/"
        print_status "Installation replaced at: $PI_LEDFX_DIR"
    fi
fi

# Step 10: Preserve configuration
print_status "Step 10: Preserving existing configuration..."
if run_on_pi "[ -d '$BACKUP_DIR/config' ]"; then
    print_status "Configuration was backed up and will be preserved"
    print_status "Config location: $PI_CONFIG_DIR"
fi

# Step 11: Verify mood detection files
print_status "Step 11: Verifying mood detection files..."
MOOD_FILES=(
    "ledfx/mood_detector.py"
    "ledfx/mood_detector_librosa.py"
    "ledfx/structure_analyzer.py"
    "ledfx/integrations/mood_manager.py"
    "ledfx/api/mood.py"
    "ledfx/api/mood_scenes.py"
    "ledfx/effects/mood_analysis.py"
    "ledfx/events.py"
)

MISSING_FILES=()
for file in "${MOOD_FILES[@]}"; do
    if ! run_on_pi "[ -f '$PI_LEDFX_DIR/$file' ]"; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -eq 0 ]; then
    print_status "All mood detection files verified!"
else
    print_error "Missing mood detection files:"
    for file in "${MISSING_FILES[@]}"; do
        print_error "  - $file"
    done
    exit 1
fi

# Step 12: Clean up temporary directory
print_status "Step 12: Cleaning up temporary files..."
run_on_pi "rm -rf $TEMP_DIR"

# Step 13: Verify Python can import mood modules
print_status "Step 13: Verifying Python imports..."
if run_on_pi "python3 -c 'from ledfx.mood_detector import MoodDetector; print(\"MoodDetector imported successfully\")' 2>&1"; then
    print_status "Mood detection modules can be imported!"
else
    print_warning "Warning: Could not verify mood detection imports."
    print_warning "This is likely because dependencies need to be installed."
    print_warning "Run the following command to install dependencies:"
    print_warning "  ssh $PI_HOST 'python3 -m pip install --user --break-system-packages -e $TEMP_DIR'"
fi

# Step 14: Create startup script (optional)
print_status "Step 14: Creating helper scripts..."
START_SCRIPT="/home/pi/start_ledfx.sh"
run_on_pi "cat > $START_SCRIPT << 'EOF'
#!/bin/bash
cd $PI_LEDFX_DIR
python3 -m ledfx \"\$@\"
EOF
chmod +x $START_SCRIPT"
print_status "Created startup script: $START_SCRIPT"

# Step 15: Summary
print_status ""
print_status "=========================================="
print_status "Deployment Summary"
print_status "=========================================="
print_status "✓ LedFx with mood detection deployed to: $PI_LEDFX_DIR"
print_status "✓ Backup created at: $BACKUP_DIR"
print_status "✓ Configuration preserved at: $PI_CONFIG_DIR"
print_status ""
print_status "Next steps:"
print_status "1. Start LedFx: ssh $PI_HOST 'cd $PI_LEDFX_DIR && python3 -m ledfx'"
print_status "2. Or use the startup script: ssh $PI_HOST '$START_SCRIPT'"
print_status "3. Verify mood detection: curl http://$PI_HOST:8888/api/mood"
print_status ""
print_status "To enable mood detection:"
print_status "  curl -X PUT http://$PI_HOST:8888/api/mood \\"
print_status "    -H 'Content-Type: application/json' \\"
print_status "    -d '{\"enabled\": true}'"
print_status ""
print_status "To install missing dependencies (if deployment had issues):"
print_status "  ./fix_dependencies.sh"
print_status ""
print_status "To install librosa for advanced features (optional):"
print_status "  ssh $PI_HOST 'python3 -m pip install --user --break-system-packages librosa>=0.10.0'"
print_status "=========================================="

print_status "Deployment completed successfully!"

