#!/bin/bash

echo "========================================================"
echo "           STOPPING INVENTARSYSTEM SERVICES             "
echo "========================================================"

# Function to check if a service is active
is_service_active() {
    sudo systemctl is-active --quiet $1
    return $?
}

# Stop Nginx service first (since it depends on Gunicorn)
echo "Stopping Nginx service..."
if is_service_active inventarsystem-nginx; then
    sudo systemctl stop inventarsystem-nginx.service
    echo "✓ Nginx service stopped"
else
    echo "Nginx service was not running"
fi

# Stop Gunicorn service
echo "Stopping Gunicorn service..."
if is_service_active inventarsystem-gunicorn; then
    sudo systemctl stop inventarsystem-gunicorn.service
    echo "✓ Gunicorn service stopped"
else
    echo "Gunicorn service was not running"
fi

# Check for any remaining processes and kill them if necessary
echo "Checking for remaining processes..."

# Check for gunicorn processes
GUNICORN_PIDS=$(pgrep -f "gunicorn.*inventarsystem")
if [ -n "$GUNICORN_PIDS" ]; then
    echo "Found remaining Gunicorn processes. Killing them..."
    sudo kill -1 $GUNICORN_PIDS
    echo "✓ Remaining Gunicorn processes terminated"
fi



# Check for nginx processes (but don't stop the main nginx daemon if it's running other sites)
echo "Note: Not stopping the main Nginx daemon, as it might be serving other websites."

echo "========================================================"
echo "All Inventarsystem services have been stopped."
echo "========================================================"

# Make the script executable
chmod +x "$0"