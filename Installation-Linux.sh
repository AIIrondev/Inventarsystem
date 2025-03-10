#!/bin/bash

# Set the project directory to the current path
PROJECT_DIR=$(pwd)

# Get the local network IP address
DOMAIN=$(hostname -I | awk '{print $1}')

# Clone the repository
git clone https://github.com/yourusername/yourrepository.git $PROJECT_DIR

# Update and upgrade the system
sudo apt update && sudo apt upgrade -y

# Install necessary packages
sudo apt install -y python3 python3-venv python3-pip nginx mongodb

# Set up the virtual environment
python3 -m venv $PROJECT_DIR/.venv
source $PROJECT_DIR/.venv/bin/activate

# Install Python dependencies
pip install -r $PROJECT_DIR/requirements.txt

# Set up Gunicorn
pip install gunicorn

# Create a systemd service file for Gunicorn
sudo tee /etc/systemd/system/inventarsystem.service > /dev/null <<EOF
[Unit]
Description=Gunicorn instance to serve Inventarsystem
After=network.target

[Service]
User=web
Group=www-data
WorkingDirectory=$PROJECT_DIR/Web
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/Web/inventarsystem.sock -m 007 main:app

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the Gunicorn service
sudo systemctl start inventarsystem
sudo systemctl enable inventarsystem

# Configure Nginx to proxy requests to Gunicorn
sudo tee /etc/nginx/sites-available/inventarsystem > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/Web/inventarsystem.sock;
    }

    location /static/ {
        alias $PROJECT_DIR/Web/static/;
    }

    location /uploads/ {
        alias $PROJECT_DIR/Web/uploads/;
    }
}
EOF

# Enable the Nginx server block configuration
sudo ln -s /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled

# Test the Nginx configuration
sudo nginx -t

# Restart Nginx to apply the changes
sudo systemctl restart nginx

# Ensure MongoDB is running
sudo systemctl start mongodb
sudo systemctl enable mongodb

echo "Installation and setup complete. Your Flask application is now running with Gunicorn and Nginx on your local network."