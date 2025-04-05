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

./start-codespace.sh