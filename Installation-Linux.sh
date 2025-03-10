#!/bin/bash

# Update the system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-pip git mongodb fail2ban nginx

# Start and enable MongoDB
sudo systemctl start mongodb
sudo systemctl enable mongodb

# Verify MongoDB status
if systemctl is-active --quiet mongodb; then
    echo "MongoDB is running successfully."
else
    echo "MongoDB failed to start. Exiting..."
    exit 1
fi

# Clone the repository
git clone https://github.com/AIIrondev/Chatsystem.git /opt/Chatsystem
cd /opt/Chatsystem

# Install Python dependencies
pip3 install -r requirements.txt

# Start the DeploymentCenter application
nohup python3 DeploymentCenter/main.py > /dev/null 2>&1 &

# Display success message
echo "DeploymentCenter application has been successfully deployed."
