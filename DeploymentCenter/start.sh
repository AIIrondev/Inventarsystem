#!/bin/bash

# start the Database
service mongodb start
service mongodb status

# Start the gunicorn server
gunicorn -w 4 -b 0.0.0.0:5000 app:app