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

# Clean up any existing MongoDB repos to avoid conflicts
echo "=== Cleaning up existing MongoDB repositories ==="
sudo rm -f /etc/apt/sources.list.d/mongodb*.list
sudo apt-key del 7F0CEB10 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5 20691EEC35216C63CAF66CE1656408E390CFB1F5 4B7C549A058F8B6B 2069827F925C2E182330D4D4B5BEA7232F5C6971 E162F504A20CDF15827F718D4B7C549A058F8B6B 9DA31620334BD75D9DCB49F368818C72E52529D4 F5679A222C647C87527C2F8CB00A0BD1E2C63C11 2023-02-15 > /dev/null 2>&1

# Update system packages
echo "=== Updating system packages ==="
sudo apt update || { echo "Failed to update package lists"; exit 1; }

# Add MongoDB repository for Ubuntu 24.04
echo "=== Adding MongoDB repository ==="
UBUNTU_VERSION=$(lsb_release -rs)
UBUNTU_CODENAME=$(lsb_release -cs)

if [[ "$UBUNTU_VERSION" == "24.04" || "$UBUNTU_CODENAME" == "noble" ]]; then
    echo "Detected Ubuntu 24.04 (Noble)"
    echo "Using Ubuntu 22.04 (Jammy) repository for MongoDB 6.0"
    
    # Modern way to add repository keys with explicit file
    wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg
    
    # Add repository using Jammy instead of Noble
    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
else
    # For older Ubuntu versions
    echo "Using repository for $UBUNTU_CODENAME"
    wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg
    
    echo "deb [signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu $UBUNTU_CODENAME/mongodb-org/6.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
fi

# Update package list with new repository
echo "=== Updating package list ==="
sudo apt update || { 
    echo "Warning: Failed to update with MongoDB repo, trying system MongoDB instead"; 
    # Remove problematic repo if update fails
    sudo rm -f /etc/apt/sources.list.d/mongodb-org-6.0.list
    sudo apt update
}

# Install necessary packages with fallback for MongoDB
echo "=== Installing required packages ==="
sudo apt install -y python3 python3-venv python3-pip nginx git ufw || { 
    echo "Failed to install base packages"; 
    exit 1; 
}

# Try to install MongoDB from the repository
echo "=== Installing MongoDB ==="
if sudo apt install -y mongodb-org; then
    echo "MongoDB installed successfully from MongoDB repository"
    MONGO_SERVICE="mongod"
else
    echo "Trying to install system MongoDB package instead..."
    sudo apt install -y mongodb || { 
        echo "Failed to install MongoDB"; 
        exit 1; 
    }
    echo "System MongoDB installed successfully"
    MONGO_SERVICE="mongodb"
fi

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
git clone $GITHUB_REPO $PROJECT_DIR || { 
    echo "Repository may exist already, trying to pull latest changes"; 
    cd $PROJECT_DIR && git pull || { 
        echo "Failed to update repository"; 
        exit 1; 
    }
}

# Create directories for logs, uploads, and QR codes
echo "=== Creating application directories ==="
mkdir -p $PROJECT_DIR/logs || { echo "Failed to create logs directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/uploads || { echo "Failed to create uploads directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/QRCodes || { echo "Failed to create QRCodes directory"; exit 1; }
mkdir -p $PROJECT_DIR/DeploymentCenter/static || { echo "Failed to create DeploymentCenter static directory"; exit 1; }

# Set up the virtual environment
echo "=== Setting up Python virtual environment ==="
python3 -m venv $PROJECT_DIR/.venv || { echo "Failed to create virtual environment"; exit 1; }
source $PROJECT_DIR/.venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Install Python dependencies
echo "=== Installing Python dependencies ==="
pip install --upgrade pip || { echo "Failed to upgrade pip"; exit 1; }
pip install -r $PROJECT_DIR/requirements.txt || { 
    echo "Error with requirements.txt, installing core dependencies directly"; 
    pip install flask pymongo pillow qrcode gunicorn
}
pip install gunicorn || { echo "Failed to install Gunicorn"; exit 1; }

# Create WSGI file for Web interface if it doesn't exist
echo "=== Creating Web WSGI file ==="
if [ ! -f "$PROJECT_DIR/Web/wsgi.py" ]; then
    cat > $PROJECT_DIR/Web/wsgi.py << EOF
from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0')
EOF
    [ $? -ne 0 ] && { echo "Failed to create Web WSGI file"; exit 1; }
fi

# Create WSGI file for DeploymentCenter if it doesn't exist
echo "=== Creating DeploymentCenter WSGI file ==="
if [ ! -f "$PROJECT_DIR/DeploymentCenter/wsgi.py" ]; then
    cat > $PROJECT_DIR/DeploymentCenter/wsgi.py << EOF
from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0')
EOF
    [ $? -ne 0 ] && { echo "Failed to create DeploymentCenter WSGI file"; exit 1; }
fi

# Configure MongoDB
echo "=== Configuring MongoDB for autostart ==="
sudo systemctl enable $MONGO_SERVICE || { echo "Failed to enable MongoDB"; exit 1; }
sudo systemctl start $MONGO_SERVICE || { echo "Failed to start MongoDB"; exit 1; }
echo "MongoDB configured and started"

# Create system user for running the service
echo "=== Creating system user ==="
sudo useradd -r -s /bin/false inventarsystem || echo "User already exists"
sudo usermod -a -G www-data inventarsystem || { echo "Failed to add user to www-data group"; exit 1; }

# Set appropriate permissions
echo "=== Setting file permissions ==="
sudo chown -R inventarsystem:www-data $PROJECT_DIR || { echo "Failed to change ownership"; exit 1; }
sudo chmod -R 755 $PROJECT_DIR || { echo "Failed to set permissions to 755"; exit 1; }
sudo chmod -R 775 $PROJECT_DIR/logs $PROJECT_DIR/Web/uploads $PROJECT_DIR/Web/QRCodes || { 
    echo "Failed to set permissions to 775"; 
    exit 1; 
}

# Create systemd service files for both applications
echo "=== Creating systemd services for Inventarsystem components ==="

# Create Web service
sudo tee /etc/systemd/system/inventarsystem-web.service > /dev/null << EOF
[Unit]
Description=Inventarsystem Web Interface
After=network.target $MONGO_SERVICE.service
Requires=$MONGO_SERVICE.service
Documentation=https://github.com/aiirondev/Inventarsystem

[Service]
User=inventarsystem
Group=www-data
WorkingDirectory=$PROJECT_DIR/Web
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/Web/inventarsystem.sock --access-logfile $PROJECT_DIR/logs/access.log --error-logfile $PROJECT_DIR/logs/error.log wsgi:app
Restart=always
RestartSec=10
SyslogIdentifier=inventarsystem-web
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create DeploymentCenter service
sudo tee /etc/systemd/system/inventarsystem-dc.service > /dev/null << EOF
[Unit]
Description=Inventarsystem DeploymentCenter
After=network.target $MONGO_SERVICE.service inventarsystem-web.service
Requires=$MONGO_SERVICE.service
Documentation=https://github.com/aiirondev/Inventarsystem

[Service]
User=inventarsystem
Group=www-data
WorkingDirectory=$PROJECT_DIR/DeploymentCenter
Environment="PATH=$PROJECT_DIR/.venv/bin"
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 2 --bind unix:$PROJECT_DIR/DeploymentCenter/deploymentcenter.sock --access-logfile $PROJECT_DIR/logs/deployment-access.log --error-logfile $PROJECT_DIR/logs/deployment-error.log wsgi:app
Restart=always
RestartSec=10
SyslogIdentifier=inventarsystem-dc
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx for both services
echo "=== Configuring Nginx ==="
sudo tee /etc/nginx/sites-available/inventarsystem > /dev/null << EOF
server {
    listen 80;
    server_name _;
    
    # Main Web Interface
    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/Web/inventarsystem.sock;
        client_max_body_size 10M;
    }
    
    # Static files for Web Interface
    location /static {
        alias $PROJECT_DIR/Web/static;
    }

    # Uploads folder
    location /uploads {
        alias $PROJECT_DIR/Web/uploads;
    }
}

server {
    listen 81;
    server_name _;
    
    # DeploymentCenter Interface
    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/DeploymentCenter/deploymentcenter.sock;
        client_max_body_size 10M;
    }
    
    # Static files for DeploymentCenter
    location /static {
        alias $PROJECT_DIR/DeploymentCenter/static;
    }
}
EOF

# Create proxy_params if not exists
if [ ! -f "/etc/nginx/proxy_params" ]; then
    sudo tee /etc/nginx/proxy_params > /dev/null << EOF
proxy_set_header Host \$http_host;
proxy_set_header X-Real-IP \$remote_addr;
proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto \$scheme;
EOF
fi

# Enable the site in Nginx
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Create convenient start/stop script
echo "=== Creating convenience script for management ==="
sudo tee $PROJECT_DIR/manage-inventarsystem.sh > /dev/null << EOF
#!/bin/bash

function display_help {
    echo "Inventarsystem Management Script"
    echo "Usage: \$0 [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start both Web and DeploymentCenter services"
    echo "  stop        Stop both services"
    echo "  restart     Restart both services"
    echo "  status      Show service status"
    echo "  logs        Show recent logs"
    echo "  web-start   Start only Web service"
    echo "  dc-start    Start only DeploymentCenter service"
    echo "  web-stop    Stop only Web service"
    echo "  dc-stop     Stop only DeploymentCenter service"
}

case "\$1" in
    start)
        echo "Starting Inventarsystem services..."
        sudo systemctl start inventarsystem-web.service
        sudo systemctl start inventarsystem-dc.service
        sudo systemctl restart nginx
        ;;
    stop)
        echo "Stopping Inventarsystem services..."
        sudo systemctl stop inventarsystem-web.service
        sudo systemctl stop inventarsystem-dc.service
        ;;
    restart)
        echo "Restarting Inventarsystem services..."
        sudo systemctl restart inventarsystem-web.service
        sudo systemctl restart inventarsystem-dc.service
        sudo systemctl restart nginx
        ;;
    status)
        echo "=== Web Interface Status ==="
        sudo systemctl status inventarsystem-web.service
        echo ""
        echo "=== DeploymentCenter Status ==="
        sudo systemctl status inventarsystem-dc.service
        echo ""
        echo "=== Nginx Status ==="
        sudo systemctl status nginx
        ;;
    logs)
        echo "Showing recent logs..."
        echo "=== Web Access Log ==="
        tail -n 20 $PROJECT_DIR/logs/access.log
        echo ""
        echo "=== Web Error Log ==="
        tail -n 20 $PROJECT_DIR/logs/error.log
        echo ""
        echo "=== DeploymentCenter Access Log ==="
        tail -n 20 $PROJECT_DIR/logs/deployment-access.log
        echo ""
        echo "=== DeploymentCenter Error Log ==="
        tail -n 20 $PROJECT_DIR/logs/deployment-error.log
        ;;
    web-start)
        echo "Starting Web service..."
        sudo systemctl start inventarsystem-web.service
        ;;
    dc-start)
        echo "Starting DeploymentCenter service..."
        sudo systemctl start inventarsystem-dc.service
        ;;
    web-stop)
        echo "Stopping Web service..."
        sudo systemctl stop inventarsystem-web.service
        ;;
    dc-stop)
        echo "Stopping DeploymentCenter service..."
        sudo systemctl stop inventarsystem-dc.service
        ;;
    *)
        display_help
        ;;
esac
EOF

# Make the script executable
sudo chmod +x $PROJECT_DIR/manage-inventarsystem.sh

# Reload systemd, enable and start the services
echo "=== Enabling and starting services ==="
sudo systemctl daemon-reload
sudo systemctl enable inventarsystem-web.service
sudo systemctl enable inventarsystem-dc.service

# Test Nginx configuration and restart
sudo nginx -t && sudo systemctl restart nginx || {
    echo "Nginx configuration error, checking...";
    sudo nginx -t -c /etc/nginx/nginx.conf;
    exit 1;
}

# Start the services
sudo systemctl start inventarsystem-web.service
sudo systemctl start inventarsystem-dc.service

# Allow Nginx ports in firewall
sudo ufw allow 80 || echo "Warning: Could not open port 80"
sudo ufw allow 81 || echo "Warning: Could not open port 81"

# Create a log rotation configuration
sudo tee /etc/logrotate.d/inventarsystem > /dev/null << EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 inventarsystem www-data
    sharedscripts
    postrotate
        systemctl reload inventarsystem-web.service > /dev/null 2>/dev/null || true
        systemctl reload inventarsystem-dc.service > /dev/null 2>/dev/null || true
    endscript
}
EOF

echo "==================================================="
echo "Installation complete!"
echo "Your Inventarsystem is now available at:"
echo "- Web Interface:     http://$SERVER_IP"
echo "- DeploymentCenter:  http://$SERVER_IP:81"
echo "==================================================="
echo "MANAGEMENT:"
echo "- To manage services: sudo $PROJECT_DIR/manage-inventarsystem.sh [command]"
echo "- For help, run:      sudo $PROJECT_DIR/manage-inventarsystem.sh"
echo "==================================================="
echo "AUTOSTART CONFIGURATION:"
echo "- All services will automatically start on system boot"
echo "==================================================="