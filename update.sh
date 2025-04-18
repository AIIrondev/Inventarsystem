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
    tee $PROJECT_ROOT/daily-update.sh > /dev/null << EOF
#!/bin/bash
trap 'echo "Script interrupted. Exiting."' SIGINT SIGTERM
# Daily reinstall script for Inventarsystem

set -e  # Exit on error
trap 'echo "Error occurred at line \$LINENO. Command: \$BASH_COMMAND"' ERR

# Set variables
REPO_URL="https://github.com/AIIrondev/Inventarsystem.git"
INSTALL_DIR="/var/Inventarsystem"
LOG_FILE="$PROJECT_ROOT/logs/update.log"
BACKUP_BASE_DIR="/var/backups/Inventar_backup"
BACKUP_DIR="\$BACKUP_BASE_DIR/\$(date +%Y-%m-%d)"

# Create log entry
echo "===== Daily reinstall started at \$(date) =====" >> \$LOG_FILE

# Create backup directories
sudo mkdir -p "\$BACKUP_BASE_DIR"
sudo chmod 777 "\$BACKUP_BASE_DIR"
mkdir -p "\$BACKUP_DIR"

# Backup important data
echo "Creating backup..." >> \$LOG_FILE
if [ -d "\$INSTALL_DIR/Web/static/images" ]; then
    mkdir -p "\$BACKUP_DIR/images"
    cp -r \$INSTALL_DIR/Web/static/images "\$BACKUP_DIR/" >> \$LOG_FILE 2>&1
fi
if [ -d "\$INSTALL_DIR/data" ]; then
    cp -r \$INSTALL_DIR/data \$BACKUP_DIR/ >> \$LOG_FILE 2>&1
fi
if [ -d "\$INSTALL_DIR/certs" ]; then
    cp -r \$INSTALL_DIR/certs \$BACKUP_DIR/ >> \$LOG_FILE 2>&1
fi
if [ -f "\$INSTALL_DIR/config.json" ]; then
    cp \$INSTALL_DIR/config.json \$BACKUP_DIR/ >> \$LOG_FILE 2>&1
fi

# Stop any running services related to Inventarsystem
echo "Stopping any running services..." >> \$LOG_FILE
pkill -f "start.sh" >> \$LOG_FILE 2>&1 || true
pkill -f "gunicorn app:app" >> \$LOG_FILE 2>&1 || true

# Completely remove the existing installation
echo "Removing existing installation..." >> \$LOG_FILE
if [ -d "\$INSTALL_DIR" ]; then
    sudo rm -rf \$INSTALL_DIR >> \$LOG_FILE 2>&1
fi

echo "Installing fresh copy..." >> \$LOG_FILE
wget -O - https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash >> \$LOG_FILE 2>&1

# Restore backed up files
echo "Restoring backed up files..." >> \$LOG_FILE

if [ -d "\$BACKUP_DIR/images" ]; then
    mkdir -p "\$INSTALL_DIR/Web/static/"
    cp -r "\$BACKUP_DIR/images" "\$INSTALL_DIR/Web/static/" >> \$LOG_FILE 2>&1
fi
if [ -d "\$BACKUP_DIR/data" ]; then
    cp -r "\$BACKUP_DIR/data" "\$INSTALL_DIR/" >> \$LOG_FILE 2>&1
fi
if [ -d "\$BACKUP_DIR/certs" ]; then
    cp -r "\$BACKUP_DIR/certs" "\$INSTALL_DIR/" >> \$LOG_FILE 2>&1
fi
if [ -f "\$BACKUP_DIR/config.json" ]; then
    cp "\$BACKUP_DIR/config.json" "\$INSTALL_DIR/" >> \$LOG_FILE 2>&1
fi

# Verify installation
echo "Verifying installation..." >> \$LOG_FILE
$PROJECT_ROOT/verify-installation.sh >> \$LOG_FILE 2>&1

# Clean up old backups
echo "Cleaning up old backups..." >> \$LOG_FILE
$PROJECT_ROOT/backup-cleanup.sh >> \$LOG_FILE 2>&1

echo "Script executed successfully!" >> \$LOG_FILE
echo "===== Daily reinstall completed at \$(date) =====" >> \$LOG_FILE
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