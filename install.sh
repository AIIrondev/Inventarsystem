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


echo "========================================================"
echo "                  INSTALLATION COMPLETE                 "
echo "========================================================"
echo "You can now access Inventarsystem in these ways:"
echo "1. Type 'inventarsystem' in terminal"
echo "2. Type 'invsys' to navigate to the directory"
echo "3. Find 'Inventarsystem' in your application menu"
echo ""
echo "Please run the following command to activate the changes in your current terminal:"
echo "source ~/.bashrc"
echo "========================================================"
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