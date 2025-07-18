#!/bin/bash
# Helper script to run the backup with proper Python environment

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# Default values if no arguments provided
if [ $# -eq 0 ]; then
    # Define default values
    DB="Inventarsystem"
    URI="mongodb://localhost:27017/"
    OUT="$SCRIPT_DIR/backups/$(date +%Y-%m-%d)"
    
    echo "No arguments provided. Using defaults:"
    echo "  --uri $URI"
    echo "  --db $DB"
    echo "  --out $OUT"
    
    # Create output directory if it doesn't exist
    mkdir -p "$OUT"
    
    # Set the arguments
    ARGS="--uri $URI --db $DB --out $OUT"
else
    # Use provided arguments
    ARGS="$@"
fi

# Check if we're in a virtual environment
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    # Use the virtual environment's Python
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/Backup-DB.py" $ARGS
else
    # Use system Python
    python3 "$SCRIPT_DIR/Backup-DB.py" $ARGS
fi
