#!/bin/bash

'''
    Copyright 2025-2026 Maximilian Gründinger

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''

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