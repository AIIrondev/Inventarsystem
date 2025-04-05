#!/bin/bash

sudo apt-get update
sudo apt-get install -y curl wget git

echo "Installing Inventarsystem..."
# Clone the repository if it doesn't exist already
REPO_URL="https://github.com/aiirondev/Inventarsystem.git"
REPO_DIR="$HOME/.local/share/inventarsystem"

# Create directory structure if it doesn't exist
mkdir -p "$HOME/.local/bin"

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

# Create user-level symbolic link for easy access (no sudo required)
echo "Creating symbolic link for easy access..."
ln -sf "$REPO_DIR/start-codespace.sh" "$HOME/.local/bin/inventarsystem"

# Make sure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Added ~/.local/bin to your PATH"
fi

# Add alias for quick directory access
echo "Adding alias for quick directory navigation..."
if ! grep -q "alias invsys=" "$HOME/.bashrc"; then
    echo "alias invsys='cd $REPO_DIR'" >> "$HOME/.bashrc"
fi

# Create a desktop file for easy launching
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/inventarsystem.desktop" << EOF
[Desktop Entry]
Name=Inventarsystem
Comment=Launch Inventarsystem
Exec=$HOME/.local/bin/inventarsystem
Terminal=true
Type=Application
Categories=Utility;
EOF

# Source bashrc to make alias available immediately
echo ""
echo "Setup complete!"
echo "You can now access Inventarsystem in these ways:"
echo "1. Type 'inventarsystem' in terminal"
echo "2. Type 'invsys' to navigate to the directory"
echo "3. Find 'Inventarsystem' in your application menu"
echo ""
echo "Please run the following command to activate the changes in your current terminal:"
echo "source ~/.bashrc"

# Run the script
# Ask the user if they want to run the script now
read -p "Do you want to run the script now? (y/n): " run_now
if [[ $run_now == "y" || $run_now == "Y" ]]; then
    echo "Running the script now..."
    ./start-codespace.sh
    if [ $? -ne 0 ]; then
        echo "Failed to run the script. Please check the logs for more details."
        exit 1
    fi
    echo "Script executed successfully!"
    ^C
else
    echo "You can run the script later by typing 'inventarsystem' in your terminal."
fi

# Ask if the user wants to install it as a autostartup application
read -p "Do you want to install it as an autostart application? (y/n): " install_autostart
if [[ $install_autostart == "y" || $install_autostart == "Y" ]]; then
    ./update.sh
    echo "Autostart application installed successfully!"
else
    echo "Autostart application installation skipped."
fi

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