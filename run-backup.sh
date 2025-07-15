#!/bin/bash
# Helper script to run the backup with proper Python environment

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# Check if we're in a virtual environment
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    # Use the virtual environment's Python
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Backup-DB.py" "$@"
else
    # Use system Python
    python3 "$SCRIPT_DIR/Backup-DB.py" "$@"
fi
