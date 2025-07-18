#!/bin/bash

# This script fixes the requirements.txt file by removing bson dependency
# which conflicts with pymongo

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
BACKUP_FILE="$SCRIPT_DIR/requirements.txt.bak"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Fixing requirements.txt to avoid pymongo/bson conflict"

# Backup original requirements file
log_message "Creating backup of original requirements file"
cp "$REQUIREMENTS_FILE" "$BACKUP_FILE"

# Create new requirements file without bson
log_message "Creating new requirements file without standalone bson package"
grep -v "^bson" "$REQUIREMENTS_FILE" > "$REQUIREMENTS_FILE.tmp"
mv "$REQUIREMENTS_FILE.tmp" "$REQUIREMENTS_FILE"

# Ensure pymongo is set to the correct version
log_message "Setting pymongo version to 4.6.1"
if grep -q "^pymongo" "$REQUIREMENTS_FILE"; then
    # Replace existing pymongo line
    sed -i 's/^pymongo.*/pymongo==4.6.1/' "$REQUIREMENTS_FILE"
else
    # Add pymongo if not already in the file
    echo "pymongo==4.6.1" >> "$REQUIREMENTS_FILE"
fi

# Add comment to explain the removal
sed -i '1s/^/# This requirements file has been modified to avoid bson/pymongo conflicts\n/' "$REQUIREMENTS_FILE"

log_message "Requirements file has been updated successfully"
log_message "Original file backed up as $BACKUP_FILE"
log_message "You should now run: sudo ./rebuild-venv.sh"

exit 0
