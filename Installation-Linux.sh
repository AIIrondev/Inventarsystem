#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/Installation-Linux.sh
set -e  # Exit immediately if a command exits with non-zero status

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
log "Asking for installation source"
echo ""
echo "How would you like to install Inventarsystem?"
echo "1) Download from GitHub repository (default)"
echo "2) Copy from this local directory"
read -p "Enter your choice [1-2]: " INSTALL_SOURCE
if [ -z "$INSTALL_SOURCE" ]; then
    INSTALL_SOURCE="1"
fi
log "User chose installation source: $INSTALL_SOURCE"

# Check if project directory already exists
if [ -d "$PROJECT_DIR" ]; then
    log "Project directory already exists: $PROJECT_DIR"
    echo "Directory $PROJECT_DIR already exists."
    read -p "Do you want to remove it and perform a clean install? (y/n): " CLEAN_INSTALL
    if [ "$CLEAN_INSTALL" = "y" ] || [ "$CLEAN_INSTALL" = "Y" ]; then
        log "User chose to remove existing installation"
        echo "Removing existing installation..."
        # Stop any running services first
        log_cmd "sudo systemctl stop inventarsystem-web.service 2>/dev/null || true"
        log_cmd "sudo systemctl stop inventarsystem-dc.service 2>/dev/null || true"
        # Remove the directory
        log_cmd "sudo rm -rf $PROJECT_DIR"
        echo "Existing installation removed."
    else
        log "User chose to keep existing installation"
        echo "Will attempt to work with existing installation."
    fi
fi

# Get the server IP address
SERVER_IP=$(hostname -I | awk '{print $1}')
log "Server IP: $SERVER_IP"
echo "Server IP: $SERVER_IP"

# Clean up any existing MongoDB repos to avoid conflicts
log "Cleaning up existing MongoDB repositories"
echo "=== Cleaning up existing MongoDB repositories ==="
log_cmd "sudo rm -f /etc/apt/sources.list.d/mongodb*.list"
log_cmd "sudo apt-key del 7F0CEB10 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5 20691EEC35216C63CAF66CE1656408E390CFB1F5 4B7C549A058F8B6B 2069827F925C2E182330D4D4B5BEA7232F5C6971 E162F504A20CDF15827F718D4B7C549A058F8B6B 9DA31620334BD75D9DCB49F368818C72E52529D4 F5679A222C647C87527C2F8CB00A0BD1E2C63C11 2023-02-15 > /dev/null 2>&1 || true"

# Update system packages
log "Updating system packages"
echo "=== Updating system packages ==="
log_cmd "sudo apt update" || { log "Failed to update package lists"; exit 1; }

# Add MongoDB repository for Ubuntu 24.04
log "Adding MongoDB repository"
echo "=== Adding MongoDB repository ==="
UBUNTU_VERSION=$(lsb_release -rs)
UBUNTU_CODENAME=$(lsb_release -cs)
log "Ubuntu version: $UBUNTU_VERSION (codename: $UBUNTU_CODENAME)"

if [[ "$UBUNTU_VERSION" == "24.04" || "$UBUNTU_CODENAME" == "noble" ]]; then
    log "Detected Ubuntu 24.04 (Noble), using Jammy repository for MongoDB"
    echo "Detected Ubuntu 24.04 (Noble)"
    echo "Using Ubuntu 22.04 (Jammy) repository for MongoDB 6.0"
    
    # Modern way to add repository keys with explicit file
    log_cmd "wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg"
    
    # Add repository using Jammy instead of Noble
    log_cmd "echo \"deb [signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/6.0 multiverse\" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list"
else
    # For older Ubuntu versions
    log "Using repository for $UBUNTU_CODENAME"
    echo "Using repository for $UBUNTU_CODENAME"
    log_cmd "wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-6.0.gpg"
    
    log_cmd "echo \"deb [signed-by=/usr/share/keyrings/mongodb-server-6.0.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu $UBUNTU_CODENAME/mongodb-org/6.0 multiverse\" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list"
fi

# Update package list with new repository
log "Updating package list with new repository"
echo "=== Updating package list ==="
log_cmd "sudo apt update" || { 
    log "Warning: Failed to update with MongoDB repo, trying system MongoDB instead"
    echo "Warning: Failed to update with MongoDB repo, trying system MongoDB instead"; 
    # Remove problematic repo if update fails
    log_cmd "sudo rm -f /etc/apt/sources.list.d/mongodb-org-6.0.list"
    log_cmd "sudo apt update" || true
}

# Install necessary packages with fallback for MongoDB
log "Installing required packages"
echo "=== Installing required packages ==="
log_cmd "sudo apt install -y python3 python3-venv python3-pip nginx git ufw" || { 
    log "Failed to install base packages"
    echo "Failed to install base packages"; 
    exit 1; 
}

# Try to install MongoDB from the repository
log "Installing MongoDB"
echo "=== Installing MongoDB ==="
if log_cmd "sudo apt install -y mongodb-org"; then
    log "MongoDB installed successfully from MongoDB repository"
    echo "MongoDB installed successfully from MongoDB repository"
    MONGO_SERVICE="mongod"
else
    log "Trying to install system MongoDB package instead"
    echo "Trying to install system MongoDB package instead..."
    if log_cmd "sudo apt install -y mongodb"; then
        log "System MongoDB installed successfully"
        echo "System MongoDB installed successfully"
        MONGO_SERVICE="mongodb"
    else
        log "Failed to install MongoDB"
        echo "Failed to install MongoDB"; 
        exit 1;
    }
fi

# Create project directory and set ownership
log "Creating project directory"
echo "=== Creating project directory ==="
log_cmd "sudo mkdir -p $PROJECT_DIR" || { log "Failed to create project directory"; exit 1; }
log_cmd "sudo chown $USER:$USER $PROJECT_DIR" || { log "Failed to set ownership for project directory"; exit 1; }

# Install the Inventarsystem files
log "Setting up project files"
echo "=== Setting up project files ==="

# Get the current script directory for local installation
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log "Current script directory: $SCRIPT_DIR"

if [ "$INSTALL_SOURCE" = "2" ]; then
    # Copy from local directory
    log "Copying files from local directory: $SCRIPT_DIR"
    echo "Copying files from: $SCRIPT_DIR"
    log_cmd "cp -r \"$SCRIPT_DIR\"/* \"$PROJECT_DIR/\"" || {
        log "Error: Failed to copy files from local directory"
        echo "Error: Failed to copy files from local directory";
        exit 1;
    }
    log "Files copied successfully from local directory"
    echo "Files copied successfully from local directory."
else
    # Clone from GitHub repository
    log "Cloning from GitHub repository: $GITHUB_REPO"
    echo "Cloning from GitHub repository: $GITHUB_REPO"
    
    # Create system temporary directory
    TEMP_DIR=$(mktemp -d)
    log "Using temporary directory: $TEMP_DIR"
    
    # Setup cleanup to run on script exit, interrupt, or termination
    trap 'log "Cleaning up temporary files"; rm -rf "$TEMP_DIR"; log "Cleanup complete"' EXIT
    
    echo "Using temporary directory: $TEMP_DIR"
    # Create systemd service files with improved socket handling
log "Creating systemd services with improved socket handling"
echo "=== Creating systemd services for Inventarsystem components ==="

# Create Web service with fixed PATH and explicit binary paths
log "Creating Web service configuration"
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

# Create DeploymentCenter service with fixed PATH and explicit binary paths
log "Creating DeploymentCenter service configuration"
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
log "Configuring Nginx"
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
log "Setting up proxy_params for Nginx"
if [ ! -f "/etc/nginx/proxy_params" ]; then
    sudo tee /etc/nginx/proxy_params > /dev/null << EOF
proxy_set_header Host \$http_host;
proxy_set_header X-Real-IP \$remote_addr;
proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto \$scheme;
EOF
fi

# Enable the site in Nginx
log "Enabling Nginx site configuration"
log_cmd "sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled/" || log "Warning: Failed to enable site in Nginx"
log_cmd "sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true"

# Create convenient start/stop script
log "Creating management script"
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
        
        echo "Checking permissions..."
        echo "Web directory:"
        ls -la $PROJECT_DIR/Web
        echo "DeploymentCenter directory:"
        ls -la $PROJECT_DIR/DeploymentCenter
        
        echo "Checking logs..."
        tail -n 5 $PROJECT_DIR/logs/error.log || echo "No error log found"
        tail -n 5 $PROJECT_DIR/logs/deployment-error.log || echo "No deployment error log found"
        
        echo "Checking system binary paths..."
        which chmod || echo "ERROR: chmod not found!"
        which chown || echo "ERROR: chown not found!"
        
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
log "Making management script executable"
log_cmd "sudo chmod +x $PROJECT_DIR/manage-inventarsystem.sh"

# Reload systemd, enable and start the services
log "Reloading systemd and enabling services"
echo "=== Enabling and starting services ==="
log_cmd "sudo systemctl daemon-reload"
log_cmd "sudo systemctl enable inventarsystem-web.service"
log_cmd "sudo systemctl enable inventarsystem-dc.service"

# Start services with thorough error checking
log "Starting services with detailed error checking"
echo "=== Starting services with detailed error checking ==="
log_cmd "sudo systemctl restart inventarsystem-web.service"
echo "Starting Web service..."
sleep 2

# Detailed error checking for Web service
if ! sudo systemctl is-active --quiet inventarsystem-web.service; then
    log "ERROR: Web service failed to start, checking logs"
    echo "WARNING: Web service failed to start. Checking logs:"
    journal_logs=$(sudo journalctl -u inventarsystem-web.service --no-pager -n 30)
    log "Web service journal logs: $journal_logs"
    echo "$journal_logs"
    echo ""
else
    log "Web service started successfully"
    echo "Web service started successfully."
fi

log "Starting DeploymentCenter service"
echo "Starting DeploymentCenter service..."
log_cmd "sudo systemctl restart inventarsystem-dc.service"
sleep 2

# Detailed error checking for DeploymentCenter service
if ! sudo systemctl is-active --quiet inventarsystem-dc.service; then
    log "ERROR: DeploymentCenter service failed to start, checking logs"
    echo "WARNING: DeploymentCenter service failed to start. Checking logs:"
    journal_logs=$(sudo journalctl -u inventarsystem-dc.service --no-pager -n 30)
    log "DeploymentCenter service journal logs: $journal_logs"
    echo "$journal_logs"
    echo ""
else
    log "DeploymentCenter service started successfully"
    echo "DeploymentCenter service started successfully."
fi

# Test Nginx configuration and restart
log "Testing and restarting Nginx"
if sudo nginx -t; then
    log "Nginx configuration test passed, restarting"
    log_cmd "sudo systemctl restart nginx"
else
    log "WARNING: Nginx configuration has errors, checking details"
    echo "Warning: Nginx configuration error, checking..."
    log_cmd "sudo nginx -t -c /etc/nginx/nginx.conf"
    echo "Continuing despite Nginx configuration issues..."
fi

# Allow Nginx ports in firewall
log "Configuring firewall for Nginx"
log_cmd "sudo ufw allow 80" || log "Warning: Could not open port 80"
log_cmd "sudo ufw allow 81" || log "Warning: Could not open port 81"

# Create a log rotation configuration
log "Setting up log rotation"
echo "=== Setting up log rotation ==="
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

# Copy log file to final location for permanent storage
log "Saving installation log to permanent location"
sudo cp "$LOG_FILE" "$FINAL_LOG_FILE" || log "Warning: Failed to copy log to permanent location"
sudo chown inventarsystem:www-data "$FINAL_LOG_FILE" 2>/dev/null || log "Warning: Failed to set log file ownership"
sudo chmod 644 "$FINAL_LOG_FILE" 2>/dev/null || log "Warning: Failed to set log file permissions"

log "Installation process completed. Log saved to $FINAL_LOG_FILE"

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
echo "LOG FILES:"
echo "- Installation log:  $FINAL_LOG_FILE"
echo "- Current temp log:  $LOG_FILE"
echo "==================================================="
echo "AUTOSTART CONFIGURATION:"
echo "- All services will automatically start on system boot"
echo "==================================================="