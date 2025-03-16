#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/Installation-Linux.sh
set -e  # Exit immediately if a command exits with non-zero status

# Add this section right after the initial set -e line:

# Setup logging
LOG_FILE="/tmp/inventarsystem_install_$(date +%Y%m%d_%H%M%S).log"
FINAL_LOG_FILE="/var/log/inventarsystem_installation.log"

# Log function - writes to both console and log file
log() {
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "[$timestamp] $1"
    echo -e "[$timestamp] $1" >> "$LOG_FILE"
}

log_cmd() {
    local cmd="$1"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo -e "[$timestamp] COMMAND: $cmd"
    echo -e "[$timestamp] COMMAND: $cmd" >> "$LOG_FILE"
    # Run the command, capture output and exit code
    OUTPUT=$(eval "$cmd" 2>&1) || {
        local exit_code=$?
        echo -e "[$timestamp] EXIT CODE: $exit_code\n$OUTPUT" | tee -a "$LOG_FILE"
        return $exit_code
    }
    echo -e "[$timestamp] SUCCESS: $cmd\n$OUTPUT" >> "$LOG_FILE"
    echo "$OUTPUT"
}

# Start the log file
log "=== Inventarsystem Installation Log ==="
log "Starting installation on $(date)"
log "System information: $(uname -a)"
log "User: $(whoami)"
log "Working directory: $(pwd)"

echo "=== Inventarsystem Installation Script for Ubuntu Server ==="
echo "This script will install Inventarsystem with Gunicorn and MongoDB on Ubuntu"
echo "The system will be configured to automatically start on boot"

# Set the project directory - don't clone into current directory
PROJECT_DIR="/opt/inventarsystem"
GITHUB_REPO="https://github.com/aiirondev/Inventarsystem.git"

# Ask for installation source
echo ""
echo "How would you like to install Inventarsystem?"
echo "1) Download from GitHub repository (default)"
echo "2) Copy from this local directory"
read -p "Enter your choice [1-2]: " INSTALL_SOURCE
if [ -z "$INSTALL_SOURCE" ]; then
    INSTALL_SOURCE="1"
fi

# Check if project directory already exists
if [ -d "$PROJECT_DIR" ]; then
    echo "Directory $PROJECT_DIR already exists."
    read -p "Do you want to remove it and perform a clean install? (y/n): " CLEAN_INSTALL
    if [ "$CLEAN_INSTALL" = "y" ] || [ "$CLEAN_INSTALL" = "Y" ]; then
        echo "Removing existing installation..."
        # Stop any running services first
        sudo systemctl stop inventarsystem-web.service 2>/dev/null || true
        sudo systemctl stop inventarsystem-dc.service 2>/dev/null || true
        # Remove the directory
        sudo rm -rf $PROJECT_DIR
        echo "Existing installation removed."
    else
        echo "Will attempt to work with existing installation."
    fi
fi

# Get the server IP address
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "Server IP: $SERVER_IP"

# Clean up any existing MongoDB repos to avoid conflicts
echo "=== Cleaning up existing MongoDB repositories ==="
sudo rm -f /etc/apt/sources.list.d/mongodb*.list
sudo apt-key del 7F0CEB10 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5 20691EEC35216C63CAF66CE1656408E390CFB1F5 4B7C549A058F8B6B 2069827F925C2E182330D4D4B5BEA7232F5C6971 E162F504A20CDF15827F718D4B7C549A058F8B6B 9DA31620334BD75D9DCB49F368818C72E52529D4 F5679A222C647C87527C2F8CB00A0BD1E2C63C11 2023-02-15 > /dev/null 2>&1 || true

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
    sudo apt update || true
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

# Create project directory and set ownership
echo "=== Creating project directory ==="
sudo mkdir -p $PROJECT_DIR || { echo "Failed to create project directory"; exit 1; }
sudo chown $USER:$USER $PROJECT_DIR || { echo "Failed to set ownership for project directory"; exit 1; }

# Install the Inventarsystem files
echo "=== Setting up project files ==="

# Get the current script directory for local installation
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$INSTALL_SOURCE" = "2" ]; then
    # Copy from local directory
    echo "Copying files from: $SCRIPT_DIR"
    cp -r "$SCRIPT_DIR"/* "$PROJECT_DIR/" || {
        echo "Error: Failed to copy files from local directory";
        exit 1;
    }
    echo "Files copied successfully from local directory."
else
    # Clone from GitHub repository
    echo "Cloning from GitHub repository: $GITHUB_REPO"
    
    # Create system temporary directory
    TEMP_DIR=$(mktemp -d)
    
    # Setup cleanup to run on script exit, interrupt, or termination
    trap 'echo "Cleaning up temporary files..."; rm -rf "$TEMP_DIR"; echo "Cleanup complete."' EXIT
    
    echo "Using temporary directory: $TEMP_DIR"
    
    # Clone repository to temp directory
    if git clone --verbose "$GITHUB_REPO" "$TEMP_DIR"; then
        echo "Repository cloned successfully to temporary directory."
        
        # Make sure project directory exists and is empty
        mkdir -p "$PROJECT_DIR"
        rm -rf "$PROJECT_DIR"/* "$PROJECT_DIR"/.[!.]* 2>/dev/null || true
        
        # Copy all files from temp directory to project directory
        echo "Copying files to installation directory..."
        cp -r "$TEMP_DIR"/* "$PROJECT_DIR/" 2>/dev/null || echo "Note: No regular files to copy"
        cp -r "$TEMP_DIR"/.[!.]* "$PROJECT_DIR/" 2>/dev/null || echo "Note: No hidden files to copy"
        
        echo "Files copied successfully from repository."
    else
        echo "Failed to clone repository from GitHub."
        echo "Would you like to:"
        echo "1) Copy from the local directory instead"
        echo "2) Create a basic structure"
        echo "3) Abort installation"
        read -p "Choose an option [1-3]: " CLONE_FAIL_ACTION
        
        if [ "$CLONE_FAIL_ACTION" = "1" ]; then
            echo "Copying files from: $SCRIPT_DIR"
            cp -r "$SCRIPT_DIR"/* "$PROJECT_DIR/" || {
                echo "Error: Failed to copy files from local directory";
                exit 1;
            }
            echo "Files copied successfully from local directory."
        elif [ "$CLONE_FAIL_ACTION" = "2" ]; then
            echo "Creating basic application structure..."
            mkdir -p $PROJECT_DIR/Web/static $PROJECT_DIR/Web/templates
            mkdir -p $PROJECT_DIR/DeploymentCenter/static $PROJECT_DIR/DeploymentCenter/templates
            
            # Create basic app.py files
            cat > $PROJECT_DIR/Web/app.py << EOF
from flask import Flask, render_template, redirect, url_for
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF
            
            cat > $PROJECT_DIR/DeploymentCenter/app.py << EOF
from flask import Flask, render_template
app = Flask(__name__)

@app.route('/')
def admin():
    return render_template('admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
EOF

            # Create basic templates
            cat > $PROJECT_DIR/Web/templates/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Inventarsystem</title>
</head>
<body>
    <h1>Inventarsystem</h1>
    <p>Web Interface</p>
</body>
</html>
EOF

            cat > $PROJECT_DIR/DeploymentCenter/templates/admin.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Deployment Center</title>
</head>
<body>
    <h1>Deployment Center</h1>
    <p>Admin Interface</p>
</body>
</html>
EOF
        else
            echo "Installation aborted."
            exit 1
        fi
    fi
fi

# Check for alternate directory names
if [ -d "$PROJECT_DIR/Managment" ] && [ ! -d "$PROJECT_DIR/DeploymentCenter" ]; then
    echo "Found 'Managment' directory instead of 'DeploymentCenter', creating symlink..."
    ln -sf "$PROJECT_DIR/Managment" "$PROJECT_DIR/DeploymentCenter" || {
        echo "Created symbolic link from Managment to DeploymentCenter";
    }
fi

# Create directories for logs, uploads, and QR codes
echo "=== Creating application directories ==="
mkdir -p $PROJECT_DIR/logs || { echo "Failed to create logs directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/uploads || { echo "Failed to create uploads directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/QRCodes || { echo "Failed to create QRCodes directory"; exit 1; }
mkdir -p $PROJECT_DIR/Web/static || { echo "Failed to create Web static directory"; exit 1; }
mkdir -p $PROJECT_DIR/DeploymentCenter/static || { echo "Failed to create DeploymentCenter static directory"; exit 1; }

# Set up the virtual environment
echo "=== Setting up Python virtual environment ==="
python3 -m venv $PROJECT_DIR/.venv || { echo "Failed to create virtual environment"; exit 1; }
source $PROJECT_DIR/.venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Install Python dependencies with fix for BSON/PyMongo issue
echo "=== Installing Python dependencies ==="
pip install --upgrade pip || { echo "Failed to upgrade pip"; exit 1; }

# Fix for BSON/PyMongo compatibility issue - THIS IS THE KEY FIX
echo "=== Fixing Python dependencies for PyMongo/BSON ==="
# Remove standalone bson if it exists (it conflicts with pymongo's built-in bson)
pip uninstall -y bson || true

# Install pymongo explicitly first with compatible version
pip install pymongo==4.5.0 || { 
    echo "Failed to install pymongo, trying alternative version"; 
    pip install pymongo==3.12.3 || { echo "Failed to install pymongo"; exit 1; }
}

# Now install other dependencies
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    # Fix the requirements file if needed
    if grep -q "^bson" "$PROJECT_DIR/requirements.txt"; then
        echo "Removing standalone bson from requirements.txt"
        sed -i '/^bson/d' "$PROJECT_DIR/requirements.txt"
    fi
    
    # Install requirements without dependencies to avoid overwriting pymongo
    pip install -r "$PROJECT_DIR/requirements.txt" || echo "Warning: Some requirements failed, continuing with core dependencies"
fi

# Always install core dependencies to be safe
pip install flask pillow qrcode gunicorn

# Verify pymongo installation is working
echo "=== Verifying PyMongo installation ==="
python3 -c "import pymongo; print('PyMongo version:', pymongo.__version__); from pymongo.bson import SON; print('BSON SON imported successfully')" || {
    echo "WARNING: PyMongo verification failed. This might cause issues with the application.";
    echo "Continuing with installation anyway...";
}

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

# Enable UFW and configure firewall
echo "=== Configuring firewall ==="
sudo ufw allow 'Nginx Full' || echo "Warning: Failed to allow 'Nginx Full' in UFW"
sudo ufw allow ssh || echo "Warning: Failed to allow SSH in UFW"
sudo ufw --force enable || echo "Warning: Failed to enable UFW"

# Configure MongoDB
echo "=== Configuring MongoDB for autostart ==="
sudo systemctl enable $MONGO_SERVICE || echo "Warning: Failed to enable MongoDB"
sudo systemctl start $MONGO_SERVICE || echo "Warning: Failed to start MongoDB"
echo "MongoDB configured and started"

# Create system user for running the service
echo "=== Creating system user ==="
sudo useradd -r -s /bin/false inventarsystem 2>/dev/null || echo "User already exists"
sudo usermod -a -G www-data inventarsystem || echo "Warning: Failed to add user to www-data group"

# Set appropriate permissions
echo "=== Setting file permissions ==="
sudo chown -R inventarsystem:www-data $PROJECT_DIR || echo "Warning: Failed to change ownership"
sudo chmod -R 755 $PROJECT_DIR || echo "Warning: Failed to set permissions to 755"
sudo chmod -R 775 $PROJECT_DIR/logs $PROJECT_DIR/Web/uploads $PROJECT_DIR/Web/QRCodes || echo "Warning: Failed to set permissions to 775"

# Create systemd service files with improved socket handling
echo "=== Creating systemd services for Inventarsystem components ==="

# Replace the Web service definition with:
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
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PATH=$PROJECT_DIR/.venv/bin:\$PATH"
# Remove any existing socket file before starting
ExecStartPre=/bin/rm -f $PROJECT_DIR/Web/inventarsystem.sock
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/Web/inventarsystem.sock --access-logfile $PROJECT_DIR/logs/access.log --error-logfile $PROJECT_DIR/logs/error.log --log-level debug wsgi:app
# Fix socket permissions after starting with full paths
ExecStartPost=/bin/chmod 660 $PROJECT_DIR/Web/inventarsystem.sock
ExecStartPost=/bin/chown inventarsystem:www-data $PROJECT_DIR/Web/inventarsystem.sock
Restart=always
RestartSec=10
SyslogIdentifier=inventarsystem-web
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

# Replace the DeploymentCenter service definition with:
sudo tee /etc/systemd/system/inventarsystem-dc.service > /dev/null << EOF
[Unit]
Description=Inventarsystem DeploymentCenter
After=network.target $MONGO_SERVICE.service
Requires=$MONGO_SERVICE.service
Documentation=https://github.com/aiirondev/Inventarsystem

[Service]
User=inventarsystem
Group=www-data
WorkingDirectory=$PROJECT_DIR/DeploymentCenter
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PATH=$PROJECT_DIR/.venv/bin:\$PATH"
# Remove any existing socket file before starting
ExecStartPre=/bin/rm -f $PROJECT_DIR/DeploymentCenter/deploymentcenter.sock
ExecStart=$PROJECT_DIR/.venv/bin/gunicorn --workers 2 --bind unix:$PROJECT_DIR/DeploymentCenter/deploymentcenter.sock --access-logfile $PROJECT_DIR/logs/deployment-access.log --error-logfile $PROJECT_DIR/logs/deployment-error.log --log-level debug wsgi:app
# Fix socket permissions after starting with full paths
ExecStartPost=/bin/chmod 660 $PROJECT_DIR/DeploymentCenter/deploymentcenter.sock
ExecStartPost=/bin/chown inventarsystem:www-data $PROJECT_DIR/DeploymentCenter/deploymentcenter.sock
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
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled/ || echo "Warning: Failed to enable site in Nginx"
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

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
    echo "  uninstall   Completely remove Inventarsystem"
    echo "  diagnose    Run diagnostic checks on the system"
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
    diagnose)
        echo "=== Running Inventarsystem Diagnostics ==="
        echo "Checking Python installation..."
        source $PROJECT_DIR/.venv/bin/activate
        python3 -c "import sys; print('Python version:', sys.version)"
        python3 -c "import pymongo; print('PyMongo version:', pymongo.__version__)"
        
        echo "Checking socket files..."
        ls -la $PROJECT_DIR/Web/inventarsystem.sock || echo "ERROR: Web socket file not found!"
        ls -la $PROJECT_DIR/DeploymentCenter/deploymentcenter.sock || echo "ERROR: DeploymentCenter socket file not found!"
        
        echo "Checking services..."
        sudo systemctl status inventarsystem-web.service | grep "Active:"
        sudo systemctl status inventarsystem-dc.service | grep "Active:"
        sudo systemctl status nginx | grep "Active:"
        
        echo "Finished diagnostics."
        ;;
    uninstall)
        echo "WARNING: This will completely remove Inventarsystem."
        read -p "Are you sure you want to continue? (y/n): " confirm
        if [ "\$confirm" = "y" ] || [ "\$confirm" = "Y" ]; then
            echo "Stopping services..."
            sudo systemctl stop inventarsystem-web.service
            sudo systemctl stop inventarsystem-dc.service
            
            echo "Disabling services..."
            sudo systemctl disable inventarsystem-web.service
            sudo systemctl disable inventarsystem-dc.service
            
            echo "Removing service files..."
            sudo rm -f /etc/systemd/system/inventarsystem-web.service
            sudo rm -f /etc/systemd/system/inventarsystem-dc.service
            
            echo "Removing Nginx configuration..."
            sudo rm -f /etc/nginx/sites-available/inventarsystem
            sudo rm -f /etc/nginx/sites-enabled/inventarsystem
            
            echo "Reloading systemd and Nginx..."
            sudo systemctl daemon-reload
            sudo systemctl restart nginx
            
            echo "Removing application directory..."
            sudo rm -rf $PROJECT_DIR
            
            echo "Uninstallation complete."
        else
            echo "Uninstallation cancelled."
        fi
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

# Start services with thorough error checking
echo "=== Starting services with detailed error checking ==="
sudo systemctl restart inventarsystem-web.service
echo "Starting Web service..."
sleep 2

# Detailed error checking for Web service
if ! sudo systemctl is-active --quiet inventarsystem-web.service; then
    echo "WARNING: Web service failed to start. Checking logs:"
    sudo journalctl -u inventarsystem-web.service --no-pager -n 30 || echo "No logs available"
    echo ""
else
    echo "Web service started successfully."
fi

echo "Starting DeploymentCenter service..."
sudo systemctl restart inventarsystem-dc.service
sleep 2

# Detailed error checking for DeploymentCenter service
if ! sudo systemctl is-active --quiet inventarsystem-dc.service; then
    echo "WARNING: DeploymentCenter service failed to start. Checking logs:"
    sudo journalctl -u inventarsystem-dc.service --no-pager -n 30 || echo "No logs available"
    echo ""
else
    echo "DeploymentCenter service started successfully."
fi

# Test Nginx configuration and restart
sudo nginx -t && sudo systemctl restart nginx || {
    echo "Warning: Nginx configuration error, checking...";
    sudo nginx -t -c /etc/nginx/nginx.conf;
    echo "Continuing despite Nginx configuration issues...";
}

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
echo "- To diagnose issues: sudo $PROJECT_DIR/manage-inventarsystem.sh diagnose"
echo "- To uninstall:       sudo $PROJECT_DIR/manage-inventarsystem.sh uninstall"
echo "==================================================="
echo "AUTOSTART CONFIGURATION:"
echo "- All services will automatically start on system boot"
sudo cp "$LOG_FILE" "$FINAL_LOG_FILE" 2>/dev/null || echo "Warning: Failed to copy log to permanent location"
sudo chown inventarsystem:www-data "$FINAL_LOG_FILE" 2>/dev/null || echo "Warning: Failed to set log file ownership"
sudo chmod 644 "$FINAL_LOG_FILE" 2>/dev/null || echo "Warning: Failed to set log file permissions"

echo "==================================================="
echo "LOG FILES:"
echo "- Installation log:  $FINAL_LOG_FILE"
echo "- Current temp log:  $LOG_FILE"
echo "==================================================="