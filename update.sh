#!/bin/bash

# Set project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" || {
    echo "Failed to determine project root directory. Exiting."
    exit 1
}
VENV_DIR="$PROJECT_ROOT/.venv"

# Enable error checking
set -e

echo "========================================================"
echo "    SETTING UP AUTOSTART AND AUTOMATIC UPDATES         "
echo "========================================================"

# Create systemd service for the Inventarsystem application
create_systemd_service() {
    echo "Creating systemd service for Inventarsystem..."
    
    # Create the service file
    sudo tee /etc/systemd/system/inventarsystem.service > /dev/null << EOF
[Unit]
Description=Inventarsystem Web Application
After=network.target mongodb.service

[Service]
User=$(whoami)
WorkingDirectory=$PROJECT_ROOT/Web
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/gunicorn app:app --bind unix:/tmp/inventarsystem.sock --workers 1 --access-logfile $PROJECT_ROOT/logs/access.log --error-logfile $PROJECT_ROOT/logs/error.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd to recognize the new service
    sudo systemctl daemon-reload
    
    # Enable the service to start at boot
    sudo systemctl enable inventarsystem.service
    
    # Start the service
    sudo systemctl start inventarsystem.service
    
    echo "✓ Inventarsystem service created and started"
}

# Create update script that will be run by cron
create_update_script() {
    echo "Creating daily update script..."
    
    # Create the update script
    tee $PROJECT_ROOT/daily-update.sh > /dev/null << EOF
#!/bin/bash
# Daily update script for Inventarsystem

# Set project root directory
PROJECT_ROOT="$PROJECT_ROOT"
VENV_DIR="$PROJECT_ROOT/.venv"
LOG_FILE="$PROJECT_ROOT/logs/update.log"

# Create log entry
echo "===== Update started at \$(date) =====" >> \$LOG_FILE

# Pull latest code from repository (if git is used)
cd \$PROJECT_ROOT
if [ -d ".git" ]; then
    echo "Pulling latest code..." >> \$LOG_FILE
    git pull origin main >> \$LOG_FILE 2>&1 || {
        echo "Failed to pull latest code" >> \$LOG_FILE
    }
fi

# Activate virtual environment
source "\$VENV_DIR/bin/activate" || {
    echo "Failed to activate virtual environment" >> \$LOG_FILE
    exit 1
}

# Update Python dependencies
if [ -f requirements.txt ]; then
    echo "Updating Python dependencies..." >> \$LOG_FILE
    pip install --upgrade -r requirements.txt >> \$LOG_FILE 2>&1 || {
        echo "Warning: Some dependencies may not have updated correctly" >> \$LOG_FILE
    }
fi

# Deactivate virtual environment
deactivate

# Restart the application service
echo "Restarting services..." >> \$LOG_FILE
sudo systemctl restart inventarsystem.service >> \$LOG_FILE 2>&1 || {
    echo "Failed to restart Inventarsystem service" >> \$LOG_FILE
}

echo "===== Update completed at \$(date) =====" >> \$LOG_FILE
EOF

    # Make the update script executable
    chmod +x $PROJECT_ROOT/daily-update.sh
    
    echo "✓ Daily update script created"
}

# Set up cron job for daily updates
setup_cron_job() {
    echo "Setting up cron job for daily updates..."
    
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
        echo "✓ Cron job added for daily updates at 3:00 AM"
    else
        echo "✓ Cron job already exists for daily updates"
    fi
    
    # Remove the temp file
    rm $TEMP_CRON
}

# Check if running in a GitHub Codespace
if [ -n "$CODESPACES" ] && [ "$CODESPACES" = "true" ]; then
    echo "Detected GitHub Codespace environment"
    echo "Autostart configuration is not applicable in Codespaces"
    echo "You may need to manually start the application with ./start-codespace.sh"
else
    # Create systemd service for autostart
    create_systemd_service
    
    # Create the daily update script
    create_update_script
    
    # Set up cron job
    setup_cron_job
    
    echo "========================================================"
    echo "                  SETUP COMPLETE                        "
    echo "========================================================"
    echo "The Inventarsystem application will now:"
    echo "  - Start automatically on system boot"
    echo "  - Update automatically every day at 3:00 AM"
    echo ""
    echo "You can manually start/stop the service with:"
    echo "  sudo systemctl start inventarsystem.service"
    echo "  sudo systemctl stop inventarsystem.service"
    echo ""
    echo "You can check the service status with:"
    echo "  sudo systemctl status inventarsystem.service"
    echo ""
    echo "Update logs will be stored in:"
    echo "  $PROJECT_ROOT/logs/update.log"
    echo "========================================================"
fi

# Make this script executable
chmod +x "$0"