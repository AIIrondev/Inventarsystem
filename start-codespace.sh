#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/start-codespace.sh

# Create logs directory if it doesn't exist
mkdir -p /home/max/Dokumente/repos/Inventarsystem/logs

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

# Start DeploymentCenter in background
echo "Starting DeploymentCenter with Gunicorn..."
cd DeploymentCenter
gunicorn app:app --bind 0.0.0.0:8001 --workers 2 --access-logfile ../logs/deployment-access.log --error-logfile ../logs/deployment-error.log &
DEPLOYMENT_PID=$!
echo "DeploymentCenter started with PID: $DEPLOYMENT_PID"

# Return to project directory
cd /home/max/Dokumente/repos/Inventarsystem

# Start main application with Gunicorn in foreground
echo "Starting Inventarsystem main application with Gunicorn..."
cd Web
gunicorn app:app --bind 0.0.0.0:8000 --workers 4 --access-logfile ../logs/access.log --error-logfile ../logs/error.log

# Note: The script will only reach here if the main application terminates
echo "Main application has terminated."

# If we get here, kill the background DeploymentCenter process
if ps -p $DEPLOYMENT_PID > /dev/null; then
    echo "Stopping DeploymentCenter (PID: $DEPLOYMENT_PID)..."
    kill $DEPLOYMENT_PID
fi

echo "All services stopped."