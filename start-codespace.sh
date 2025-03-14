#!/bin/bash

# Start MongoDB
echo "Starting MongoDB service..."
sudo service mongodb start

# Check MongoDB status
echo "MongoDB service status:"
sudo service mongodb status

# Set environment variables
export FLASK_ENV=production
export FLASK_APP=Web/app.py

# Change to project directory
cd /home/max/Dokumente/repos/Inventarsystem

# Start application with Gunicorn
echo "Starting Inventarsystem with Gunicorn..."
cd Web
gunicorn app:app --workers 4 --access-logfile ../logs/access.log --error-logfile ../logs/error.log