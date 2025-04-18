#!/bin/bash

# Set project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" || {
    echo "Failed to determine project root directory. Exiting."
    exit 1
}

set -e  # Exit on error
trap 'echo "Error occurred at line $LINENO. Command: $BASH_COMMAND"' ERR

# Initialize the directories first before installing or changing anything important
echo "Initializing required directories..."
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/certs"

# Create backup directory
BACKUP_BASE_DIR="/var/backups/Inventar_backup"
sudo mkdir -p "$BACKUP_BASE_DIR"
sudo chmod 777 "$BACKUP_BASE_DIR"

# Save all images and certs before deleting in an unused tmp backup dir
echo "Creating backup of important files..."
BACKUP_TMP_DIR="$BACKUP_BASE_DIR/tmp_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_TMP_DIR"

# Backup images if they exist
if [ -d "$PROJECT_ROOT/Web/static/images" ]; then
    echo "Backing up images..."
    cp -r "$PROJECT_ROOT/Web/static/images" "$BACKUP_TMP_DIR/"
fi

# Backup certificates if they exist
if [ -d "$PROJECT_ROOT/certs" ]; then
    echo "Backing up certificates..."
    cp -r "$PROJECT_ROOT/certs" "$BACKUP_TMP_DIR/"
fi

# Backup configuration files if they exist
if [ -f "$PROJECT_ROOT/config.json" ]; then
    echo "Backing up configuration..."
    cp "$PROJECT_ROOT/config.json" "$BACKUP_TMP_DIR/"
fi

# New function: Verify backup integrity
verify_backup() {
    echo "Verifying backup integrity..."
    local backup_dir="$1"
    local issues_found=0
    
    # Check if images were backed up correctly
    if [ -d "$PROJECT_ROOT/Web/static/images" ] && [ ! -d "$backup_dir/images" ]; then
        echo "WARNING: Images backup is missing"
        issues_found=$((issues_found+1))
    fi
    
    # Check if certificates were backed up correctly
    if [ -d "$PROJECT_ROOT/certs" ] && [ ! -d "$backup_dir/certs" ]; then
        echo "WARNING: Certificates backup is missing"
        issues_found=$((issues_found+1))
    fi
    
    # Check if config was backed up correctly
    if [ -f "$PROJECT_ROOT/config.json" ] && [ ! -f "$backup_dir/config.json" ]; then
        echo "WARNING: Configuration backup is missing"
        issues_found=$((issues_found+1))
    fi
    
    if [ $issues_found -eq 0 ]; then
        echo "✓ Backup verification completed successfully"
    else
        echo "! $issues_found backup issues detected"
    fi
    
    return $issues_found
}

# Verify the backup
verify_backup "$BACKUP_TMP_DIR"

echo "Backup completed to: $BACKUP_TMP_DIR"

# Enable error checking
set -e

echo "========================================================"
echo "           SETTING UP AUTOMATIC DAILY REINSTALL         "
echo "========================================================"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# New function: Clean up old backups
cleanup_old_backups() {
    echo "Setting up backup cleanup functionality..."
    local backup_dir="$1"
    local max_backups="$2"
    
    # Create cleanup script
    tee $PROJECT_ROOT/backup-cleanup.sh > /dev/null << EOF
#!/bin/bash
# Cleanup old backups to prevent disk space issues

BACKUP_DIR="$backup_dir"
MAX_BACKUPS="$max_backups"

# Get a list of all backup directories (excluding tmp backups)
BACKUPS=\$(find \$BACKUP_DIR -maxdepth 1 -type d -name "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]" | sort)

# Count total backups
TOTAL_BACKUPS=\$(echo "\$BACKUPS" | grep -v "^$" | wc -l)

# If we have more than MAX_BACKUPS, delete the oldest ones
if [ \$TOTAL_BACKUPS -gt \$MAX_BACKUPS ]; then
    # Calculate how many to delete
    DELETE_COUNT=\$(( TOTAL_BACKUPS - MAX_BACKUPS ))
    
    # Get the oldest backup directories
    TO_DELETE=\$(echo "\$BACKUPS" | head -n \$DELETE_COUNT)
    
    # Delete the oldest backup directories
    echo "Deleting \$DELETE_COUNT old backup(s)..."
    for dir in \$TO_DELETE; do
        echo "Removing old backup: \$dir"
        rm -rf "\$dir"
    done
fi

# Cleanup tmp backups older than 7 days
find \$BACKUP_DIR -maxdepth 1 -type d -name "tmp_backup_*" -mtime +7 -exec rm -rf {} \;
EOF
    
    # Make the cleanup script executable
    chmod +x $PROJECT_ROOT/backup-cleanup.sh
    
    echo "✓ Backup cleanup script created"
}

# New function: Check installation status
check_installation_status() {
    echo "Creating installation verification script..."
    
    tee $PROJECT_ROOT/verify-installation.sh > /dev/null << EOF
#!/bin/bash
# Verify if the Inventarsystem is working correctly

INSTALL_DIR="/var/Inventarsystem"
LOG_FILE="$PROJECT_ROOT/logs/verification.log"

echo "===== Verification started at \$(date) =====" >> \$LOG_FILE

# Check if installation directory exists
if [ ! -d "\$INSTALL_DIR" ]; then
    echo "ERROR: Installation directory does not exist" >> \$LOG_FILE
    exit 1
fi

# Check if main files exist
if [ ! -f "\$INSTALL_DIR/start.sh" ]; then
    echo "ERROR: start.sh does not exist" >> \$LOG_FILE
    exit 1
fi

# Check if config exists
if [ ! -f "\$INSTALL_DIR/config.json" ]; then
    echo "WARNING: config.json does not exist" >> \$LOG_FILE
fi

# Check if the service is running
if ! pgrep -f "gunicorn app:app" > /dev/null; then
    echo "WARNING: gunicorn service is not running" >> \$LOG_FILE
    
    # Attempt to start the service
    echo "Attempting to start the service..." >> \$LOG_FILE
    cd \$INSTALL_DIR && ./start.sh >> \$LOG_FILE 2>&1 &
fi

echo "Installation verification completed successfully" >> \$LOG_FILE
echo "===== Verification completed at \$(date) =====" >> \$LOG_FILE
EOF
    
    # Make the verification script executable
    chmod +x $PROJECT_ROOT/verify-installation.sh
    
    echo "✓ Installation verification script created"
}

# Create update script that will completely reinstall daily
create_update_script() {
    echo "Creating daily reinstall script..."
    
    # Create the update script
    tee $PROJECT_ROOT/daily-update.sh > /dev/null << 'EOF'
#!/bin/bash
trap 'echo "Script interrupted. Exiting."' SIGINT SIGTERM
# Daily reinstall script for Inventarsystem

set -e  # Exit on error
trap 'echo "Error occurred at line $LINENO. Command: $BASH_COMMAND"' ERR

# Set variables
REPO_URL="https://github.com/AIIrondev/Inventarsystem.git"
INSTALL_DIR="/var/Inventarsystem"
LOG_FILE="/home/max/Dokumente/repos/Inventarsystem/logs/update.log"
BACKUP_BASE_DIR="/var/backups/Inventar_backup"
BACKUP_DIR="$BACKUP_BASE_DIR/$(date +%Y-%m-%d)"

# Create log entry
echo "===== Daily reinstall started at $(date) =====" >> $LOG_FILE

# Create backup directories
sudo mkdir -p "$BACKUP_BASE_DIR"
sudo chmod 777 "$BACKUP_BASE_DIR"
mkdir -p "$BACKUP_DIR"

# Backup important data
echo "Creating backup..." >> $LOG_FILE
# Backup Web/upload directory specifically - use rsync for better copying
if [ -d "$INSTALL_DIR/Web/upload" ]; then
    echo "Backing up Web/upload directory..." >> $LOG_FILE
    mkdir -p "$BACKUP_DIR/Web/upload"
    rsync -av --delete $INSTALL_DIR/Web/upload/ "$BACKUP_DIR/Web/upload/" >> $LOG_FILE 2>&1 || {
        echo "Falling back to cp command for backup..." >> $LOG_FILE
        rm -rf "$BACKUP_DIR/Web/upload/"  # Clean destination first
        mkdir -p "$BACKUP_DIR/Web/upload/"
        cp -r $INSTALL_DIR/Web/upload/* "$BACKUP_DIR/Web/upload/" 2>/dev/null || true
    }
    # Count files to verify backup success
    UPLOAD_FILE_COUNT=$(find "$INSTALL_DIR/Web/upload/" -type f | wc -l)
    BACKUP_FILE_COUNT=$(find "$BACKUP_DIR/Web/upload/" -type f | wc -l)
    echo "Original upload dir has $UPLOAD_FILE_COUNT files, backup has $BACKUP_FILE_COUNT files" >> $LOG_FILE
fi
# Backup Web/uploads directory (with "s") if it exists
if [ -d "$INSTALL_DIR/Web/uploads" ]; then
    echo "Backing up Web/uploads directory..." >> $LOG_FILE
    mkdir -p "$BACKUP_DIR/uploads"
    cp -r $INSTALL_DIR/Web/uploads "$BACKUP_DIR/" >> $LOG_FILE 2>&1
fi
if [ -d "$INSTALL_DIR/certs" ]; then
    cp -r $INSTALL_DIR/certs $BACKUP_DIR/ >> $LOG_FILE 2>&1
fi
if [ -f "$INSTALL_DIR/config.json" ]; then
    cp $INSTALL_DIR/config.json $BACKUP_DIR/ >> $LOG_FILE 2>&1
fi

# Stop any running services related to Inventarsystem
echo "Stopping any running services..." >> $LOG_FILE
pkill -f "start.sh" >> $LOG_FILE 2>&1 || true
pkill -f "gunicorn app:app" >> $LOG_FILE 2>&1 || true

# Completely remove the existing installation
echo "Removing existing installation..." >> $LOG_FILE
if [ -d "$INSTALL_DIR" ]; then
    sudo rm -rf $INSTALL_DIR >> $LOG_FILE 2>&1
fi

echo "Installing fresh copy directly..." >> $LOG_FILE

# Temporarily disable exit on error for this section
set +e

# Define our own installation procedure instead of using the external script
echo "Cloning repository..." >> $LOG_FILE
sudo git clone "$REPO_URL" "$INSTALL_DIR" >> $LOG_FILE 2>&1
CLONE_RESULT=$?

if [ $CLONE_RESULT -ne 0 ]; then
    echo "Failed to clone repository. Aborting installation." >> $LOG_FILE
    exit 1
fi

# Set proper permissions - using more aggressive permission settings
echo "Setting permissions..." >> $LOG_FILE
CURRENT_USER=$(whoami)
sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR" >> $LOG_FILE 2>&1
sudo chmod -R 755 "$INSTALL_DIR" >> $LOG_FILE 2>&1

# Make sure the virtual environment directory will be writable
sudo mkdir -p "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1
sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1
sudo chmod -R 777 "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1

# Create necessary directories with correct permissions
echo "Creating necessary directories with proper permissions..." >> $LOG_FILE
for dir in "certs" "logs" "Web/upload" "Web/uploads" "Web/static/images"; do
    sudo mkdir -p "$INSTALL_DIR/$dir" >> $LOG_FILE 2>&1
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/$dir" >> $LOG_FILE 2>&1
    sudo chmod -R 777 "$INSTALL_DIR/$dir" >> $LOG_FILE 2>&1
done

# Make scripts executable with correct permissions
for script in "start.sh" "restart.sh" "stop.sh"; do
    if [ -f "$INSTALL_DIR/$script" ]; then
        sudo chmod +x "$INSTALL_DIR/$script" >> $LOG_FILE 2>&1
        sudo chown $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/$script" >> $LOG_FILE 2>&1
    else
        echo "Warning: $script not found in cloned repository" >> $LOG_FILE
    fi
done

# Create a proper Python virtual environment
echo "Creating Python virtual environment..." >> $LOG_FILE
cd "$INSTALL_DIR"

# Ensure python3-venv is installed
sudo apt-get update >> $LOG_FILE 2>&1
sudo apt-get install -y python3-venv >> $LOG_FILE 2>&1

# Remove any existing virtual environment
sudo rm -rf "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1

# Create a fresh virtual environment
python3 -m venv "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1
if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment. This may cause issues." >> $LOG_FILE
else
    echo "Virtual environment created successfully." >> $LOG_FILE
    
    # Set permissions
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1
    sudo chmod -R 755 "$INSTALL_DIR/.venv" >> $LOG_FILE 2>&1
    
    # Install basic requirements
    echo "Installing basic Python packages..." >> $LOG_FILE
    # Source the activate script
    source "$INSTALL_DIR/.venv/bin/activate" >> $LOG_FILE 2>&1
    
    # Upgrade pip
    "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip >> $LOG_FILE 2>&1
    
    # Install packages if requirements.txt exists
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" >> $LOG_FILE 2>&1
    else
        # Install basic packages anyway
        "$INSTALL_DIR/.venv/bin/pip" install flask gunicorn pymongo==4.6.1 >> $LOG_FILE 2>&1
    fi
    
    # Deactivate the environment
    deactivate >> $LOG_FILE 2>&1 || true
fi

# Re-enable exit on error
set -e

# Check if installation was successful
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Installation failed. Installation directory does not exist." >> $LOG_FILE
    exit 1
else
    echo "Installation appears to have completed successfully." >> $LOG_FILE
fi

# Restore backed up files with explicit permissions
echo "Restoring backed up files with correct permissions..." >> $LOG_FILE

# Restore Web/upload directory with better handling
if [ -d "$BACKUP_DIR/Web/upload" ]; then
    echo "Restoring Web/upload directory..." >> $LOG_FILE
    sudo mkdir -p "$INSTALL_DIR/Web/upload" >> $LOG_FILE 2>&1
    # Use rsync for better copying, preserving permissions and timestamps
    sudo rsync -av --delete "$BACKUP_DIR/Web/upload/" "$INSTALL_DIR/Web/upload/" >> $LOG_FILE 2>&1 || {
        echo "Falling back to cp command for restore..." >> $LOG_FILE
        sudo rm -rf "$INSTALL_DIR/Web/upload/"*  # Clean destination first
        sudo cp -r "$BACKUP_DIR/Web/upload/"* "$INSTALL_DIR/Web/upload/" 2>/dev/null || true
    }
    # Set very permissive permissions to ensure web server can access
    sudo chown -R $CURRENT_USER:www-data "$INSTALL_DIR/Web/upload" >> $LOG_FILE 2>&1
    sudo chmod -R 777 "$INSTALL_DIR/Web/upload" >> $LOG_FILE 2>&1
    
    # Count files to verify restore success
    BACKUP_FILE_COUNT=$(find "$BACKUP_DIR/Web/upload/" -type f | wc -l)
    RESTORED_FILE_COUNT=$(find "$INSTALL_DIR/Web/upload/" -type f | wc -l)
    echo "Backup has $BACKUP_FILE_COUNT files, restored upload dir has $RESTORED_FILE_COUNT files" >> $LOG_FILE
    
    # If counts don't match, try different approach
    if [ $BACKUP_FILE_COUNT -ne $RESTORED_FILE_COUNT ]; then
        echo "File count mismatch! Trying alternative restore approach..." >> $LOG_FILE
        sudo rm -rf "$INSTALL_DIR/Web/upload"
        sudo cp -rp "$BACKUP_DIR/Web/upload" "$INSTALL_DIR/Web/" >> $LOG_FILE 2>&1
        sudo chown -R $CURRENT_USER:www-data "$INSTALL_DIR/Web/upload" >> $LOG_FILE 2>&1
        sudo chmod -R 777 "$INSTALL_DIR/Web/upload" >> $LOG_FILE 2>&1
    fi
fi
# Restore Web/uploads directory (with "s")
if [ -d "$BACKUP_DIR/uploads" ]; then
    echo "Restoring Web/uploads directory..." >> $LOG_FILE
    sudo mkdir -p "$INSTALL_DIR/Web/" >> $LOG_FILE 2>&1
    sudo cp -r "$BACKUP_DIR/uploads" "$INSTALL_DIR/Web/" >> $LOG_FILE 2>&1
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/Web/uploads" >> $LOG_FILE 2>&1
    sudo chmod -R 777 "$INSTALL_DIR/Web/uploads" >> $LOG_FILE 2>&1
fi
if [ -d "$BACKUP_DIR/certs" ]; then
    sudo cp -r "$BACKUP_DIR/certs" "$INSTALL_DIR/" >> $LOG_FILE 2>&1
    sudo chown -R $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/certs" >> $LOG_FILE 2>&1
    sudo chmod -R 600 "$INSTALL_DIR/certs"/*.key >> $LOG_FILE 2>&1
    sudo chmod -R 644 "$INSTALL_DIR/certs"/*.crt >> $LOG_FILE 2>&1
fi
if [ -f "$BACKUP_DIR/config.json" ]; then
    sudo cp "$BACKUP_DIR/config.json" "$INSTALL_DIR/" >> $LOG_FILE 2>&1
    sudo chown $CURRENT_USER:$CURRENT_USER "$INSTALL_DIR/config.json" >> $LOG_FILE 2>&1
    sudo chmod 666 "$INSTALL_DIR/config.json" >> $LOG_FILE 2>&1
fi

# Verify installation
echo "Verifying installation..." >> $LOG_FILE
/home/max/Dokumente/repos/Inventarsystem/verify-installation.sh >> $LOG_FILE 2>&1

# Clean up old backups
echo "Cleaning up old backups..." >> $LOG_FILE
/home/max/Dokumente/repos/Inventarsystem/backup-cleanup.sh >> $LOG_FILE 2>&1

/home/max/Dokumente/repos/Inventarsystem/restart.sh >> $LOG_FILE 2>&1
# Check if restart was successful
if [ $? -ne 0 ]; then
    echo "Failed to restart the service. Please check the logs." >> $LOG_FILE
    exit 1
else
    echo "Service restarted successfully." >> $LOG_FILE
fi

echo "Script executed successfully!" >> $LOG_FILE
echo "===== Daily reinstall completed at $(date) =====" >> $LOG_FILE
EOF

    # Make the update script executable
    chmod +x $PROJECT_ROOT/daily-update.sh
    
    echo "✓ Daily reinstall script created"
}

# Set up cron job for daily updates
setup_cron_job() {
    echo "Setting up cron job for daily reinstall..."
    
    # Create a temp file for the new crontab
    TEMP_CRON=$(mktemp)
    
    # Export existing crontab
    crontab -l > $TEMP_CRON 2>/dev/null || echo "# New crontab" > $TEMP_CRON
    
    # Check if our job is already in crontab
    if ! grep -q "$PROJECT_ROOT/daily-update.sh" $TEMP_CRON; then
        # Add our job to run at 3:00 AM every day
        echo "0 3 * * * $PROJECT_ROOT/daily-update.sh" >> $TEMP_CRON
        
        # Install the new crontab
        crontab $TEMP_CRON
        echo "✓ Cron job added for daily reinstall at 3:00 AM"
    else
        echo "✓ Cron job already exists for daily reinstall"
    fi
    
    # Remove the temp file
    rm $TEMP_CRON
}

# Check if running in a GitHub Codespace
if [ -n "$CODESPACES" ] && [ "$CODESPACES" = "true" ]; then
    echo "Detected GitHub Codespace environment"
    echo "Daily reinstall is not applicable in Codespaces"
else
    # Create the daily update script
    create_update_script
    
    # Create the verification script
    check_installation_status
    
    # Create the backup cleanup script (keeping last 7 backups)
    cleanup_old_backups "$BACKUP_BASE_DIR" 7
    
    # Set up cron job
    setup_cron_job
    
    echo "========================================================"
    echo "                  SETUP COMPLETE                        "
    echo "========================================================"
    echo "The Inventarsystem application will now:"
    echo "  - Be completely deleted and reinstalled every day at 3:00 AM"
    echo "  - Important data will be backed up to $BACKUP_BASE_DIR"
    echo "  - The application will restart automatically after reinstall"
    echo "  - Old backups will be automatically cleaned up (keeping last 7)"
    echo ""
    echo "Reinstall logs will be stored in:"
    echo "  $PROJECT_ROOT/logs/update.log"
    echo "Backups will be stored in:"
    echo "  $BACKUP_BASE_DIR/<date>"
    echo "========================================================"
fi