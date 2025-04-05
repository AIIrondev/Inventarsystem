#!/bin/bash

sudo apt-get update
sudo apt-get install -y curl wget git

# Clone the repository if it doesn't exist already
REPO_URL="https://github.com/aiirondev/Inventarsystem.git"
REPO_DIR="$HOME/Inventarsystem"

if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning Inventarsystem repository..."
    git clone $REPO_URL $REPO_DIR
else
    echo "Repository already exists at $REPO_DIR"
fi

cd $REPO_DIR
# Check if the start-codespace.sh script exists
if [ ! -f "./start-codespace.sh" ]; then
    echo "start-codespace.sh script not found in $REPO_DIR"
    exit 1
fi
# Make the script executable
chmod +x ./start-codespace.sh
# Run the script
echo "Running start-codespace.sh..."
./start-codespace.sh