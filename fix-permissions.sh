#!/bin/bash

# This script fixes permission issues with the virtual environment
# It should be run as root/sudo

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
VENV_DIR="$SCRIPT_DIR/.venv"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Fixing permissions for virtual environment at $VENV_DIR"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    log_message "Virtual environment not found at $VENV_DIR"
    log_message "Creating a new virtual environment..."
    
    # Create a new virtual environment
    python3 -m venv "$VENV_DIR" || {
        log_message "ERROR: Failed to create virtual environment"
        exit 1
    }
fi

# Get the current user and ensure proper ownership
CURRENT_USER=$(whoami)
log_message "Setting ownership of virtual environment to $CURRENT_USER"

# Fix permissions first before checking if venv is broken
log_message "Applying permissions recursively to virtual environment directory"
chmod -R 755 "$VENV_DIR" || {
    log_message "ERROR: Failed to set permissions on $VENV_DIR"
    exit 1
}

# Make directories and files accessible
find "$VENV_DIR" -type d -exec chmod 755 {} \; 2>/dev/null
find "$VENV_DIR" -type f -exec chmod 644 {} \; 2>/dev/null
find "$VENV_DIR/bin" -type f -exec chmod 755 {} \; 2>/dev/null

# Detect bson/pymongo conflict
if [ -d "$VENV_DIR/lib/python3.12/site-packages/bson" ]; then
    log_message "Detected potential bson/pymongo conflict. Fixing..."
    sudo rm -rf "$VENV_DIR/lib/python3.12/site-packages/bson"
    log_message "Removed conflicting bson package"
fi

# Check if virtual environment is broken, if so, remove and recreate
if [ ! -x "$VENV_DIR/bin/python" ] || [ ! -x "$VENV_DIR/bin/pip" ]; then
    log_message "Virtual environment appears broken. Removing and recreating..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR" || {
        log_message "ERROR: Failed to create virtual environment"
        exit 1
    }
fi

# Make all directories accessible
find "$VENV_DIR" -type d -exec chmod 755 {} \; 2>/dev/null

# Make all files in bin directory executable
chmod -R +x "$VENV_DIR/bin/"* 2>/dev/null || log_message "Warning: Could not make bin files executable"

log_message "Installing/upgrading pip in the virtual environment"
# Use the activate script to properly set up the environment
source "$VENV_DIR/bin/activate" || {
    log_message "ERROR: Could not activate virtual environment"
    exit 1
}

# Now we are in the virtual environment, use pip directly
log_message "Upgrading pip..."
pip install --upgrade pip || log_message "WARNING: Failed to upgrade pip"

log_message "Installing required Python packages"
# First make sure any conflicting packages are removed
log_message "Removing any conflicting packages..."
pip uninstall -y bson pymongo || log_message "WARNING: Failed to uninstall packages (may not exist)"

# Clean up any remnants
if [ -d "$VENV_DIR/lib/python3.12/site-packages/bson" ]; then
    log_message "Removing bson directory..."
    sudo rm -rf "$VENV_DIR/lib/python3.12/site-packages/bson"
fi

# Install pymongo specifically
log_message "Installing pymongo..."
pip install pymongo==4.6.3 || {
    log_message "WARNING: Failed to install pymongo with pip. Trying with pip directly..."
    python -m pip install pymongo==4.6.3 || log_message "WARNING: All attempts to install pymongo failed"
}

# Check if pymongo was installed correctly
log_message "Verifying pymongo installation..."
python -c "import pymongo; print(f'PyMongo version: {pymongo.__version__}')" && log_message "✓ PyMongo installed correctly" || log_message "WARNING: PyMongo installation verification failed"

# Check if requirements.txt exists and install requirements
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log_message "Installing requirements from requirements.txt"
    # Filter out pymongo from requirements to avoid conflicts
    grep -v "^pymongo" "$SCRIPT_DIR/requirements.txt" > "$SCRIPT_DIR/requirements_filtered.txt"
    pip install -r "$SCRIPT_DIR/requirements_filtered.txt" || log_message "WARNING: Failed to install some requirements"
    rm -f "$SCRIPT_DIR/requirements_filtered.txt"
fi

# Deactivate the virtual environment
deactivate

log_message "Permission fix completed"
log_message "You can now run the restart.sh script"

exit 0
