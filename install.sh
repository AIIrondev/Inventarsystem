#!/bin/bash

sudo apt-get update
sudo apt-get install -y curl wget git

echo "Installing Inventarsystem..."
# Clone the repository to /var
git clone https://github.com/AIIrondev/Inventarsystem.git /var/Inventarsystem || {
    echo "Failed to clone repository to /var/Inventarsystem. Exiting."
    exit 1
}

cd /var/Inventarsystem
# Check if the start.sh script exists
if [ ! -f "./start.sh" ]; then
    echo "start.sh script not found in /var/Inventarsystem"
    exit 1
fi

# Make the script executable
chmod +x ./start.sh

 "========================================================"
echo "                  INSTALLATION COMPLETE                 "
echo "========================================================"

cd /var/Inventarsystem
# Run the script
# Ask the user if they want to run the script now
echo "Running the script now..."
./start.sh
if [ $? -ne 0 ]; then
    echo "Failed to run the script. Please check the logs for more details."
    exit 1
fi
echo "Script executed successfully!"

echo "========================================================"
echo "                   AUTOSTART INSTALLATION                   "
echo "========================================================"

./update.sh
if [ $? -ne 0 ]; then
    echo "Failed to set up autostart. Please check the logs for more details."
    exit 1
fi
echo "Autostart setup successfully!"
echo "========================================================"
echo "              AUTOSTART INSTALLATION COMPLETED          "
echo "========================================================"