#!/bin/bash

# Update the system
sudo apt update && sudo apt upgrade -y

# Install dependencies including the updated MongoDB version
sudo apt install -y python3 python3-pip git mongodb-org fail2ban nginx

# Start and enable MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify MongoDB status
if systemctl is-active --quiet mongod; then
    echo "MongoDB is running successfully."
else
    echo "MongoDB failed to start. Exiting..."
    exit 1
fi

sudo service --status-all
sudo service mongod start

cd DeploymentCenter/Web
gunicorn -w 2 -b 127.0.0.1:5000 app:app