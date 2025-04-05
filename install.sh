#!/bin/bash

sudo apt-get update
sudo apt-get install -y curl wget git

echo "Installing Inventarsystem..."
# Clone the repository to /var
git clone https://github.com/AIIrondev/Inventarsystem.git /var/Inventarsystem || {
    echo "Failed to clone repository to /var/Inventarsystem. Exiting."
    exit 1
}

REPO_DIR = /var/Inventarsystem

cd $REPO_DIR
# Check if the start-codespace.sh script exists
if [ ! -f "./start-codespace.sh" ]; then
    echo "start-codespace.sh script not found in $REPO_DIR"
    exit 1
fi

# Make the script executable
chmod +x ./start-codespace.sh

 "========================================================"
echo "                  INSTALLATION COMPLETE                 "
echo "========================================================"

cd $REPO_DIR
# Run the script
# Ask the user if they want to run the script now
echo "Running the script now..."
./start-codespace.sh
if [ $? -ne 0 ]; then
    echo "Failed to run the script. Please check the logs for more details."
    exit 1
fi
echo "Script executed successfully!"