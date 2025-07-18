#!/bin/bash

# This script fixes the pymongo/bson conflict in a Python environment
# It should be run with sudo

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
VENV_DIR="$SCRIPT_DIR/.venv"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting pymongo/bson conflict resolution"

# Ensure we have proper permissions
log_message "Setting permissions for virtual environment"
chmod -R 755 "$VENV_DIR" || {
    log_message "WARNING: Could not set permissions on $VENV_DIR"
}

# Make sure the bson directory is removed
BSON_DIR="$VENV_DIR/lib/python3.12/site-packages/bson"
if [ -d "$BSON_DIR" ]; then
    log_message "Removing conflicting bson directory"
    sudo rm -rf "$BSON_DIR"
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate" || {
    log_message "ERROR: Could not activate virtual environment"
    exit 1
}

# Uninstall packages
log_message "Uninstalling bson and pymongo packages"
pip uninstall -y bson || log_message "WARNING: bson not installed"
pip uninstall -y pymongo || log_message "WARNING: pymongo not installed"

# Check if the bson directory still exists and force remove it
if [ -d "$BSON_DIR" ]; then
    log_message "Force removing bson directory"
    sudo rm -rf "$BSON_DIR"
fi

# Install pymongo
log_message "Installing pymongo version 4.6.3"
pip install pymongo==4.6.3 || {
    log_message "WARNING: Failed to install pymongo with pip. Trying alternative method..."
    python -m pip install pymongo==4.6.3
}

# Verify installation
log_message "Verifying pymongo installation"
if python -c "import pymongo; print(f'PyMongo version: {pymongo.__version__}')" 2>/dev/null; then
    log_message "✓ PyMongo installed successfully: $(python -c "import pymongo; print(pymongo.__version__)")"
else
    log_message "ERROR: PyMongo installation failed verification"
    log_message "Attempting with system Python..."
    
    # Deactivate virtual environment
    deactivate
    
    # Install pymongo system-wide as fallback
    sudo pip install pymongo==4.6.3 || log_message "ERROR: Failed to install pymongo system-wide"
fi

# Deactivate virtual environment
deactivate

log_message "PyMongo/bson conflict resolution completed"
exit 0
