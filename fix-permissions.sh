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

# Fix permissions for virtual environment
chown -R $CURRENT_USER:$CURRENT_USER "$VENV_DIR" || {
    log_message "ERROR: Failed to change ownership of $VENV_DIR"
    exit 1
}

# Ensure the virtual environment is executable
chmod -R u+rwX "$VENV_DIR" || {
    log_message "ERROR: Failed to set permissions on $VENV_DIR"
    exit 1
}

log_message "Installing/upgrading pip in the virtual environment"
"$VENV_DIR/bin/python" -m pip install --upgrade pip || {
    log_message "WARNING: Failed to upgrade pip"
}

log_message "Installing required Python packages"
# Install pymongo specifically
"$VENV_DIR/bin/pip" install pymongo==4.6.1 || {
    log_message "WARNING: Failed to install pymongo"
}

# Check if requirements.txt exists and install requirements
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    log_message "Installing requirements from requirements.txt"
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" || {
        log_message "WARNING: Failed to install some requirements"
    }
fi

log_message "Permission fix completed"
log_message "You can now run the restart.sh script"

exit 0
