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

sudo service --status-all
sudo service mongodb start

cd DeploymentCenter/web
gunicorn -w 2 -b 127.0.0.1:5000 app:app