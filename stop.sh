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

# Stop Gunicorn service via systemctl (cleaner)
echo "Stopping Gunicorn service..."
if is_service_active inventarsystem-gunicorn; then
    sudo systemctl stop inventarsystem-gunicorn.service
    echo "✓ Gunicorn service stopped"
else
    echo "Gunicorn service was not running"
fi

# Give the service a moment to gracefully shut down
sleep 2

# Check for any remaining Gunicorn processes (with exact filter)
echo "Checking for remaining Gunicorn processes..."
GUNICORN_PIDS=$(pgrep -f "gunicorn.*inventarsystem" 2>/dev/null)

if [ -n "$GUNICORN_PIDS" ]; then
    echo "Found remaining Gunicorn processes: $GUNICORN_PIDS"
    echo "Attempting graceful shutdown (SIGTERM)..."
    sudo kill -15 $GUNICORN_PIDS 2>/dev/null
    
    # Wait a bit for graceful shutdown
    sleep 2
    
    # Force kill if still running
    REMAINING_PIDS=$(pgrep -f "gunicorn.*inventarsystem" 2>/dev/null)
    if [ -n "$REMAINING_PIDS" ]; then
        echo "Force killing remaining processes..."
        sudo kill -9 $REMAINING_PIDS
        echo "✓ Forced termination complete"
    else
        echo "✓ Graceful shutdown successful"
    fi
else
    echo "No remaining Gunicorn processes found"
fi

# Check for any Python processes that might be related to inventarsystem
echo "Checking for related Python processes..."
PYTHON_PIDS=$(pgrep -f "python.*app.py" 2>/dev/null | grep -v grep)

if [ -n "$PYTHON_PIDS" ]; then
    echo "⚠️  Warning: Found Python processes that might be related:"
    ps aux | grep -E "python.*app.py" | grep -v grep
    echo "These were NOT killed to avoid stopping unrelated services."
    echo "If these are orphaned Inventarsystem processes, review your systemctl config."
else
    echo "✓ No related Python processes found"
fi

echo ""
echo "========================================================"
echo "All Inventarsystem services have been stopped."
echo "========================================================"

# Make the script executable
chmod +x "$0"
