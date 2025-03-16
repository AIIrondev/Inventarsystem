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
sudo apt update && sudo apt upgrade -y || { echo "Failed to update and upgrade system packages"; exit 1; }

# Add MongoDB repository for the latest version
echo "=== Adding MongoDB repository ==="
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add - || { echo "Failed to add MongoDB GPG key"; exit 1; }
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list || { echo "Failed to add MongoDB repository"; exit 1; }

# Update package list again
echo "=== Updating package list ==="
sudo apt update || { echo "Failed to update package list"; exit 1; }

# Install necessary packages
echo "=== Installing required packages ==="
sudo apt install -y python3 python3-venv python3-pip nginx mongodb-org git ufw || { echo "Failed to install required packages"; exit 1; }

# Enable UFW and configure firewall
echo "=== Configuring firewall ==="
sudo ufw allow 'Nginx Full' || { echo "Failed to allow 'Nginx Full' in UFW"; exit 1; }
sudo ufw allow ssh || { echo "Failed to allow SSH in UFW"; exit 1; }
sudo ufw --force enable || { echo "Failed to enable UFW"; exit 1; }

# Create project directory and set ownership
echo "=== Creating project directory ==="
sudo mkdir -p $PROJECT_DIR || { echo "Failed to create project directory"; exit 1; }
sudo chown $USER:$USER $PROJECT_DIR || { echo "Failed to set ownership for project directory"; exit 1; }

# Clone the repository
echo "=== Cloning Inventarsystem repository ==="
git clone $GITHUB_REPO $PROJECT_DIR || { echo "Repository already exists, pulling latest changes"; cd $PROJECT_DIR && git pull || { echo "Failed to pull latest changes"; exit 1; }; }

# Create directories for logs, uploads, and QR codes
echo "=== Creating application directories ==="
mkdir -p $PROJECT_DIR/logs || { echo "Failed to create logs directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/uploads || { echo "Failed to create uploads directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/qrcodes || { echo "Failed to create qrcodes directory"; exit 1; }

# Set up the virtual environment
echo "=== Setting up Python virtual environment ==="
python3 -m venv $PROJECT_DIR/.venv || { echo "Failed to create virtual environment"; exit 1; }
source $PROJECT_DIR/.venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Install Python dependencies
echo "=== Installing Python dependencies ==="
pip install --upgrade pip || { echo "Failed to upgrade pip"; exit 1; }
pip install -r $PROJECT_DIR/requirements.txt || { echo "Failed to install requirements from requirements.txt"; exit 1; }
pip install gunicorn || { echo "Failed to install Gunicorn"; exit 1; }

# Create WSGI file if it doesn't exist
echo "=== Creating WSGI file ==="
if [ ! -f "$PROJECT_DIR/Web/wsgi.py" ]; then
    cat > $PROJECT_DIR/Web/wsgi.py << EOF
from app import app

if __name__ == "__main__":
    app.run()
EOF
    [ $? -ne 0 ] && { echo "Failed to create WSGI file"; exit 1; }
fi

# Configure MongoDB
echo "=== Configuring MongoDB for autostart ==="
sudo systemctl enable mongod || { echo "Failed to enable MongoDB"; exit 1; }
sudo systemctl start mongod || { echo "Failed to start MongoDB"; exit 1; }
echo "MongoDB configured and started"

# Create system user for running the service
echo "=== Creating system user ==="
sudo useradd -r -s /bin/false inventarsystem || echo "User already exists"
sudo usermod -a -G www-data inventarsystem || { echo "Failed to add user to www-data group"; exit 1; }

# Set appropriate permissions
echo "=== Setting file permissions ==="
sudo chown -R inventarsystem:www-data $PROJECT_DIR || { echo "Failed to change ownership"; exit 1; }
sudo chmod -R 755 $PROJECT_DIR || { echo "Failed to set permissions to 755"; exit 1; }
sudo chmod -R 775 $PROJECT_DIR/logs $PROJECT_DIR/Web/uploads $PROJECT_DIR/Web/qrcodes || { echo "Failed to set permissions to 775"; exit 1; }

# Create a systemd service file for Gunicorn
echo "=== Creating systemd service for Gunicorn with autostart ==="
sudo tee /etc/systemd/system/inventarsystem.service > /dev/null << EOF
[Unit]
Description=Gunicorn instance to serve Inventarsystem
After=network.target mongod.service
Requires=mongod.service
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
[ $? -ne 0 ] && { echo "Failed to create systemd service file"; exit 1; }

# Start and enable the Gunicorn service for autostart
echo "=== Enabling autostart for Inventarsystem ==="
sudo systemctl daemon-reload || { echo "Failed to reload systemd daemon"; exit 1; }
sudo systemctl start inventarsystem || { echo "Failed to start Gunicorn service"; exit 1; }
sudo systemctl enable inventarsystem || { echo "Failed to enable Gunicorn service"; exit 1; }
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
[ $? -ne 0 ] && { echo "Failed to configure Nginx"; exit 1; }

# Enable the Nginx server block and restart Nginx
echo "=== Enabling Nginx autostart configuration ==="
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled || { echo "Failed to enable Nginx site"; exit 1; }
sudo rm -f /etc/nginx/sites-enabled/default || { echo "Failed to remove default Nginx site"; exit 1; }

# Test the Nginx configuration
echo "=== Testing Nginx configuration ==="
sudo nginx -t || { echo "Nginx configuration test failed"; exit 1; }

# Restart Nginx and enable autostart
echo "=== Setting up Nginx autostart ==="
sudo systemctl restart nginx || { echo "Failed to restart Nginx"; exit 1; }
sudo systemctl enable nginx || { echo "Failed to enable Nginx"; exit 1; }

# Verify autostart settings
echo "=== Verifying autostart configuration ==="
mongodb_autostart=$(systemctl is-enabled mongod)
inventarsystem_autostart=$(systemctl is-enabled inventarsystem)
nginx_autostart=$(systemctl is-enabled nginx)

echo "MongoDB autostart: $mongodb_autostart"
echo "Inventarsystem autostart: $inventarsystem_autostart"
echo "Nginx autostart: $nginx_autostart"

# Final status checks
echo "=== Checking service status ==="
echo "MongoDB status:"
sudo systemctl status mongod --no-pager || { echo "Failed to get MongoDB status"; exit 1; }
echo "Inventarsystem status:"
sudo systemctl status inventarsystem --no-pager || { echo "Failed to get Inventarsystem status"; exit 1; }
echo "Nginx status:"
sudo systemctl status nginx --no-pager || { echo "Failed to get Nginx status"; exit 1; }

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
