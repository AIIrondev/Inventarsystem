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
gunicorn --bind 0.0.0.0:5000 wsgi:app --workers 3 --access-logfile ../logs/access.log --error-logfile ../logs/error.log