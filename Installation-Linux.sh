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

# Update system packages
echo "=== Updating system packages ==="
sudo apt update || { echo "Failed to update package lists"; exit 1; }

# Clean up any existing MongoDB repos to avoid conflicts
echo "=== Cleaning up existing MongoDB repositories ==="
sudo rm -f /etc/apt/sources.list.d/mongodb*.list
sudo apt-key del 7F0CEB10 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5 20691EEC35216C63CAF66CE1656408E390CFB1F5 4B7C549A058F8B6B 2069827F925C2E182330D4D4B5BEA7232F5C6971 E162F504A20CDF15827F718D4B7C549A058F8B6B 9DA31620334BD75D9DCB49F368818C72E52529D4 F5679A222C647C87527C2F8CB00A0BD1E2C63C11 2023-02-15 > /dev/null 2>&1

# Add MongoDB repository for Ubuntu 24.04
echo "=== Adding MongoDB repository for Ubuntu 24.04 ==="
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

# Continue with rest of script...
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

# Create WSGI file if it doesn't exist
echo "=== Creating WSGI file ==="
if [ ! -f "$PROJECT_DIR/Web/wsgi.py" ]; then
    cat > $PROJECT_DIR/Web/wsgi.py << EOF
from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0')
EOF
    [ $? -ne 0 ] && { echo "Failed to create WSGI file"; exit 1; }
fi

# Configure MongoDB
echo "=== Configuring MongoDB for autostart ==="
sudo systemctl enable $MONGO_SERVICE || { echo "Failed to enable MongoDB"; exit 1; }
sudo systemctl start $MONGO_SERVICE || { echo "Failed to start MongoDB"; exit 1; }
echo "MongoDB configured and started"

# Rest of your installation script continues...
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

# Create a systemd service file for Gunicorn
echo "=== Creating systemd service for Gunicorn with autostart ==="
sudo tee /etc/systemd/system/inventarsystem.service > /dev/null << EOF
[Unit]
Description=Gunicorn instance to serve Inventarsystem
After=network.target $MONGO_SERVICE.service
Requires=$MONGO_SERVICE.service

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

echo "==================================================="
echo "Installation complete!"
echo "Your Inventarsystem is now running at http://$SERVER_IP"
echo "==================================================="
echo "AUTOSTART CONFIGURATION:"
echo "- All services will automatically start on system boot"
echo "==================================================="