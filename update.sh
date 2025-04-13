#!/bin/bash

# Set project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" || {
    echo "Failed to determine project root directory. Exiting."
    exit 1
}

# Enable error checking
set -e

echo "========================================================"
echo "           SETTING UP AUTOMATIC DAILY REINSTALL         "
echo "========================================================"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Create update script that will completely reinstall daily
create_update_script() {
    echo "Creating daily reinstall script..."
    
    # Create the update script
    tee $PROJECT_ROOT/daily-update.sh > /dev/null << EOF
#!/bin/bash
# Daily reinstall script for Inventarsystem

# Set variables
REPO_URL="https://github.com/AIIrondev/Inventarsystem.git"
INSTALL_DIR="/var/Inventarsystem"
LOG_FILE="$PROJECT_ROOT/logs/update.log"
BACKUP_DIR="$PROJECT_ROOT/backups/\$(date +%Y-%m-%d)"

# Create log entry
echo "===== Daily reinstall started at \$(date) =====" >> \$LOG_FILE

# Create backup directory
mkdir -p \$BACKUP_DIR

# Backup important data
echo "Creating backup..." >> \$LOG_FILE
if [ -d "\$INSTALL_DIR/data" ]; then
    cp -r \$INSTALL_DIR/data \$BACKUP_DIR/ >> \$LOG_FILE 2>&1
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

# Install fresh copy like in install.sh
echo "Installing Inventarsystem..." >> \$LOG_FILE
sudo apt-get update >> \$LOG_FILE 2>&1
sudo apt-get install -y curl wget git >> \$LOG_FILE 2>&1

# Clone the repository to /var
sudo git clone \$REPO_URL \$INSTALL_DIR >> \$LOG_FILE 2>&1 || {
    echo "Failed to clone repository to \$INSTALL_DIR" >> \$LOG_FILE
    exit 1
}

# Restore backed up data
echo "Restoring important data..." >> \$LOG_FILE
if [ -d "\$BACKUP_DIR/data" ]; then
    sudo cp -r \$BACKUP_DIR/data \$INSTALL_DIR/ >> \$LOG_FILE 2>&1
fi
if [ -f "\$BACKUP_DIR/config.json" ]; then
    sudo cp \$BACKUP_DIR/config.json \$INSTALL_DIR/ >> \$LOG_FILE 2>&1
fi

# Set correct permissions
sudo chmod +x \$INSTALL_DIR/start.sh >> \$LOG_FILE 2>&1
sudo chmod +x \$INSTALL_DIR/update.sh >> \$LOG_FILE 2>&1

# Change to the installation directory
cd \$INSTALL_DIR

echo "=======================================================" >> \$LOG_FILE
echo "                INSTALLATION COMPLETE                  " >> \$LOG_FILE
echo "=======================================================" >> \$LOG_FILE

# Run the script
echo "Running the script now..." >> \$LOG_FILE
sudo ./start.sh >> \$LOG_FILE 2>&1 &

if [ \$? -ne 0 ]; then
    echo "Failed to run the script. Please check the logs for more details." >> \$LOG_FILE
    exit 1
fi

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
    
    # Set up cron job
    setup_cron_job
    
    echo "========================================================"
    echo "                  SETUP COMPLETE                        "
    echo "========================================================"
    echo "The Inventarsystem application will now:"
    echo "  - Be completely deleted and reinstalled every day at 3:00 AM"
    echo "  - Important data will be backed up before deletion"
    echo "  - The application will restart automatically after reinstall"
    echo ""
    echo "Reinstall logs will be stored in:"
    echo "  $PROJECT_ROOT/logs/update.log"
    echo "Backups will be stored in:"
    echo "  $PROJECT_ROOT/backups/<date>"
    echo "========================================================"
fi