#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/Installation-Linux.sh
set -e  # Exit immediately if a command exits with non-zero status

echo "=== Inventarsystem Installation Script for Ubuntu Server ==="
echo "This script will install Inventarsystem with Gunicorn and MongoDB on Ubuntu"
echo "The system will be configured to automatically start on boot"

# Set the project directory - don't clone into current directory
PROJECT_DIR="/opt/inventarsystem"
GITHUB_REPO="https://github.com/aiirondev/Inventarsystem.git"

# Get the server IP address
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "Server IP: $SERVER_IP"

# Update and upgrade system packages
echo "=== Updating system packages ==="
sudo apt update && sudo apt upgrade -y

# Install necessary packages
echo "=== Installing required packages ==="
sudo apt install -y python3 python3-venv python3-pip nginx mongodb git ufw

# Enable UFW and configure firewall
echo "=== Configuring firewall ==="
sudo ufw allow 'Nginx Full'
sudo ufw allow ssh
sudo ufw --force enable

# Create project directory and set ownership
echo "=== Creating project directory ==="
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

# Clone the repository
echo "=== Cloning Inventarsystem repository ==="
git clone $GITHUB_REPO $PROJECT_DIR || { echo "Repository already exists, pulling latest changes"; cd $PROJECT_DIR && git pull; }

# Create directories for logs, uploads, and QR codes
echo "=== Creating application directories ==="
mkdir -p $PROJECT_DIR/logs
mkdir -p $PROJECT_DIR/Web/uploads
mkdir -p $PROJECT_DIR/Web/qrcodes

# Set up the virtual environment
echo "=== Setting up Python virtual environment ==="
python3 -m venv $PROJECT_DIR/.venv
source $PROJECT_DIR/.venv/bin/activate

# Install Python dependencies
echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r $PROJECT_DIR/requirements.txt
pip install gunicorn

# Create WSGI file if it doesn't exist
echo "=== Creating WSGI file ==="
if [ ! -f "$PROJECT_DIR/Web/wsgi.py" ]; then
    cat > $PROJECT_DIR/Web/wsgi.py << EOF
from app import app

if __name__ == "__main__":
    app.run()
EOF
fi

# Configure MongoDB
echo "=== Configuring MongoDB for autostart ==="
sudo systemctl enable mongodb
sudo systemctl start mongodb
echo "MongoDB configured and started"

# Create system user for running the service
echo "=== Creating system user ==="
sudo useradd -r -s /bin/false inventarsystem || echo "User already exists"
sudo usermod -a -G www-data inventarsystem

# Set appropriate permissions
echo "=== Setting file permissions ==="
sudo chown -R inventarsystem:www-data $PROJECT_DIR
sudo chmod -R 755 $PROJECT_DIR
sudo chmod -R 775 $PROJECT_DIR/logs $PROJECT_DIR/Web/uploads $PROJECT_DIR/Web/qrcodes

# Create a systemd service file for Gunicorn
echo "=== Creating systemd service for Gunicorn with autostart ==="
sudo tee /etc/systemd/system/inventarsystem.service > /dev/null << EOF
[Unit]
Description=Gunicorn instance to serve Inventarsystem
After=network.target mongodb.service
Requires=mongodb.service
StartLimitIntervalSec=0

[Service]
User=inventarsystem
Group=www-data
WorkingDirectory=$PROJECT_DIR/Web
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/Web/inventarsystem.sock --access-logfile $PROJECT_DIR/logs/access.log --error-logfile $PROJECT_DIR/logs/error.log wsgi:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the Gunicorn service for autostart
echo "=== Enabling autostart for Inventarsystem ==="
sudo systemctl daemon-reload
sudo systemctl start inventarsystem
sudo systemctl enable inventarsystem
echo "Gunicorn service started and enabled for autostart"

# Configure Nginx to proxy requests to Gunicorn
echo "=== Configuring Nginx with autostart ==="
sudo tee /etc/nginx/sites-available/inventarsystem > /dev/null << EOF
server {
    listen 80;
    server_name $SERVER_IP;

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/Web/inventarsystem.sock;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /static/ {
        alias $PROJECT_DIR/Web/static/;
    }

    location /uploads/ {
        alias $PROJECT_DIR/Web/uploads/;
    }
    
    location /qrcodes/ {
        alias $PROJECT_DIR/Web/qrcodes/;
    }
    
    # Increase maximum file upload size
    client_max_body_size 10M;
}
EOF

# Enable the Nginx server block and restart Nginx
echo "=== Enabling Nginx autostart configuration ==="
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled
sudo rm -f /etc/nginx/sites-enabled/default

# Test the Nginx configuration
echo "=== Testing Nginx configuration ==="
sudo nginx -t

# Restart Nginx and enable autostart
echo "=== Setting up Nginx autostart ==="
sudo systemctl restart nginx
sudo systemctl enable nginx

# Verify autostart settings
echo "=== Verifying autostart configuration ==="
mongodb_autostart=$(systemctl is-enabled mongodb)
inventarsystem_autostart=$(systemctl is-enabled inventarsystem)
nginx_autostart=$(systemctl is-enabled nginx)

echo "MongoDB autostart: $mongodb_autostart"
echo "Inventarsystem autostart: $inventarsystem_autostart"
echo "Nginx autostart: $nginx_autostart"

# Final status checks
echo "=== Checking service status ==="
echo "MongoDB status:"
sudo systemctl status mongodb --no-pager
echo "Inventarsystem status:"
sudo systemctl status inventarsystem --no-pager
echo "Nginx status:"
sudo systemctl status nginx --no-pager

echo "==================================================="
echo "Installation complete!"
echo "Your Inventarsystem is now running at http://$SERVER_IP"
echo "==================================================="
echo "AUTOSTART CONFIGURATION:"
echo "- All services will automatically start on system boot"
echo "- No manual intervention required after restart"
echo "==================================================="
echo "To view logs:"
echo "  Application logs: sudo journalctl -u inventarsystem"
echo "  Access logs: cat $PROJECT_DIR/logs/access.log"
echo "  Error logs: cat $PROJECT_DIR/logs/error.log"
echo "==================================================="
echo "To test autostart functionality, run: sudo reboot"
echo "After reboot, services should be running automatically"
echo "==================================================="