#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/start-codespace.sh

# Create logs directory if it doesn't exist
mkdir -p /home/max/Dokumente/repos/Inventarsystem/logs

# Get the local network IP address
NETWORK_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Start MongoDB
echo "Starting MongoDB service..."
if systemctl is-active --quiet mongodb; then
    echo "MongoDB is already running"
else
    # Try different service names
    for SERVICE in mongodb mongod; do
        if systemctl list-unit-files | grep -q $SERVICE; then
            sudo systemctl start $SERVICE
            echo "Started $SERVICE service"
            break
        fi
    done
fi


# Set environment variables
export FLASK_ENV=production
export FLASK_APP=Web/app.py

# Change to project directory
cd /home/max/Dokumente/repos/Inventarsystem

# Show access information
echo "========================================================"
echo "Access Information:"
echo "Web Interface: http://$NETWORK_IP:8000"
echo "DeploymentCenter: http://$NETWORK_IP:8001"
echo "========================================================"

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

# If we get here, kill the background DeploymentCenter process
if ps -p $DEPLOYMENT_PID > /dev/null; then
    echo "Stopping DeploymentCenter (PID: $DEPLOYMENT_PID)..."
    kill $DEPLOYMENT_PID
fi

echo "All services stopped."