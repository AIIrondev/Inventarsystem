#!/bin/bash
#
# Inventarsystem Installation Script
# This script installs all required dependencies and sets up the Inventarsystem
#

echo "========================================================"
echo "          STARTING INVENTARSYSTEM INSTALLATION          "
echo "========================================================"

# Install required packages
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y curl wget git python3 python3-pip nginx mongodb

# Ensure MongoDB is running
echo "Setting up MongoDB..."
sudo systemctl enable mongodb
sudo systemctl start mongodb
sleep 2
mongod --version || {
    echo "Warning: MongoDB may not be installed correctly."
    echo "You may need to install MongoDB manually following the official documentation."
    echo "Visit: https://docs.mongodb.com/manual/installation/"
}

echo "Installing Inventarsystem..."
# Clone the repository to /var
sudo git clone https://github.com/AIIrondev/Inventarsystem.git /var/Inventarsystem || {
    echo "Failed to clone repository to /var/Inventarsystem. Exiting."
    exit 1
}

REPO_DIR="/var/Inventarsystem"

cd $REPO_DIR
# Check if the start.sh script exists
if [ ! -f "./start.sh" ]; then
    echo "start.sh script not found in $REPO_DIR"
    exit 1
fi

# Make all scripts executable
echo "Setting execute permissions on scripts..."
sudo chmod +x ./start.sh
sudo chmod +x ./fix-all.sh
sudo chmod +x ./update.sh
sudo chmod +x ./restart.sh
sudo chmod +x ./run-backup.sh 2>/dev/null || echo "Some scripts not found, continuing..."

# Install Python dependencies
echo "Installing Python dependencies..."
sudo pip3 install -r requirements.txt
sudo pip3 install -r Web/requirements.txt 2>/dev/null || echo "Web/requirements.txt not found"

echo "========================================================"
echo "                  INSTALLATION COMPLETE                 "
echo "========================================================"

# Run the fix-all script to set up permissions and directories
echo "Setting up directories and permissions..."
cd $REPO_DIR
sudo ./fix-all.sh || {
    echo "Failed to run fix-all.sh. Please check the logs for more details."
    exit 1
}

echo "========================================================"
echo "              STARTING APPLICATION                      "
echo "========================================================"

# Run the main startup script
echo "Starting Inventarsystem..."
sudo ./start.sh || {
    echo "Failed to run start.sh. Please check the logs for more details."
    exit 1
}

echo "Application started successfully!"

echo "========================================================"
echo "              SETTING UP AUTOSTART                      "
echo "========================================================"

# Set up autostart using the update script with restart-server flag
echo "Configuring autostart..."
cd $REPO_DIR
sudo ./update.sh --restart-server || {
    echo "Failed to set up autostart. Please check the logs for more details."
    exit 1
}

echo "Autostart setup successfully!"
echo "========================================================"
echo "          INVENTARSYSTEM INSTALLATION COMPLETE          "
echo "========================================================"
echo ""
echo "The system is now installed and running at: http://localhost:8080"
echo "Default login credentials can be found in README.md"
echo ""