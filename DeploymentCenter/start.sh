#!/bin/bash

# Set the project directory to the current path
PROJECT_DIR=$(pwd)

# Activate the virtual environment
source $PROJECT_DIR/.venv/bin/activate

# Start the MongoDB service
sudo service mongodb start
sudo service mongodb status

# Start the Gunicorn server
gunicorn -w 4 -b 0.0.0.0:5000 app:app