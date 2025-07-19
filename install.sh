#!/bin/bash
#
# Inventarsystem Installation Script
# This script installs all required dependencies and sets up the Inventarsystem
#

echo "========================================================"
echo "          STARTING INVENTARSYSTEM INSTALLATION          "
echo "========================================================"

# Install required packages
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y curl wget git python3 

# Install pip if not present
echo "Installing pip..."
which pip3 || sudo apt-get install -y python3-pip

# Install nginx
echo "Installing nginx..."
sudo apt-get install -y nginx

# Check if MongoDB is already installed
echo "Checking MongoDB..."
if ! which mongod > /dev/null; then
    echo "MongoDB not found, attempting to install..."
    # Try to install MongoDB from official repository
    if [ ! -f /etc/apt/sources.list.d/mongodb-org-6.0.list ]; then
        echo "Adding MongoDB repository..."
        sudo apt-get install -y gnupg
        wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
        echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list
        sudo apt-get update
    fi

    # Install MongoDB
    echo "Installing MongoDB packages..."
    sudo apt-get install -y mongodb-org
    
    # Start MongoDB service
    echo "Starting MongoDB service..."
    sudo systemctl enable mongod
    sudo systemctl start mongod
    sleep 3
fi

# Verify MongoDB is working
echo "Verifying MongoDB installation..."
mongod --version || {
    echo "Warning: MongoDB may not be installed correctly."
    echo "You may need to install MongoDB manually following the official documentation."
    echo "Visit: https://docs.mongodb.com/manual/installation/"
    echo "Continuing with installation..."
}

echo "Installing Inventarsystem..."
# Clone the repository to /var
sudo git clone https://github.com/AIIrondev/Inventarsystem.git /var/Inventarsystem || {
    echo "Failed to clone repository to /var/Inventarsystem. Exiting."
    exit 1
}

REPO_DIR="/var/Inventarsystem"

cd $REPO_DIR
# Check if the start.sh script exists
if [ ! -f "./start.sh" ]; then
    echo "start.sh script not found in $REPO_DIR"
    exit 1
fi

# Make all scripts executable
echo "Setting execute permissions on scripts..."
sudo chmod +x ./start.sh
sudo chmod +x ./fix-all.sh
sudo chmod +x ./update.sh
sudo chmod +x ./restart.sh
sudo chmod +x ./run-backup.sh 2>/dev/null || echo "Some scripts not found, continuing..."

# Install Python dependencies
echo "Installing Python dependencies..."
if which pip3 > /dev/null; then
    echo "Found pip3, installing dependencies..."
    echo "Installing gunicorn (required for web service)..."
    sudo pip3 install gunicorn
    echo "Installing main requirements..."
    sudo pip3 install -r requirements.txt || echo "Warning: Failed to install main requirements"
    if [ -f Web/requirements.txt ]; then
        sudo pip3 install -r Web/requirements.txt || echo "Warning: Failed to install Web requirements"
    else
        echo "Web/requirements.txt not found, creating minimal requirements file"
        cat > Web/requirements.txt << EOF
flask==2.0.1
pymongo==4.0.1
gunicorn==20.1.0
pillow==9.0.0
qrcode==7.3.1
apscheduler==3.8.1
python-dateutil==2.8.2
EOF
        sudo pip3 install -r Web/requirements.txt || echo "Warning: Failed to install created Web requirements"
    fi
else
    echo "ERROR: pip3 not found, please install with: sudo apt-get install python3-pip"
    exit 1
fi

echo "========================================================"
echo "                  INSTALLATION COMPLETE                 "
echo "========================================================"

# Run the fix-all script to set up permissions and directories
echo "Setting up directories and permissions..."
cd $REPO_DIR
if [ -f ./fix-all.sh ]; then
    chmod +x ./fix-all.sh
    sudo bash ./fix-all.sh || {
        echo "Warning: fix-all.sh reported errors, but we'll continue..."
        echo "Check logs in logs/fix_all.log for details"
        # Create essential directories manually as fallback
        echo "Creating essential directories as fallback..."
        sudo mkdir -p /var/Inventarsystem/Web/uploads
        sudo mkdir -p /var/Inventarsystem/Web/thumbnails
        sudo mkdir -p /var/Inventarsystem/Web/previews
        sudo mkdir -p /var/Inventarsystem/Web/QRCodes
        sudo mkdir -p /var/Inventarsystem/logs
        sudo chmod -R 777 /var/Inventarsystem/Web/uploads
        sudo chmod -R 777 /var/Inventarsystem/Web/thumbnails
        sudo chmod -R 777 /var/Inventarsystem/Web/previews
        sudo chmod -R 777 /var/Inventarsystem/Web/QRCodes
        sudo chmod -R 777 /var/Inventarsystem/logs
    }
else
    echo "Warning: fix-all.sh not found, creating essential directories manually..."
    sudo mkdir -p /var/Inventarsystem/Web/uploads
    sudo mkdir -p /var/Inventarsystem/Web/thumbnails
    sudo mkdir -p /var/Inventarsystem/Web/previews
    sudo mkdir -p /var/Inventarsystem/Web/QRCodes
    sudo mkdir -p /var/Inventarsystem/logs
    sudo chmod -R 777 /var/Inventarsystem/Web/uploads
    sudo chmod -R 777 /var/Inventarsystem/Web/thumbnails
    sudo chmod -R 777 /var/Inventarsystem/Web/previews
    sudo chmod -R 777 /var/Inventarsystem/Web/QRCodes
    sudo chmod -R 777 /var/Inventarsystem/logs
fi

echo "========================================================"
echo "              STARTING APPLICATION                      "
echo "========================================================"

# Run the main startup script
echo "Starting Inventarsystem..."
if [ -f ./start.sh ]; then
    chmod +x ./start.sh
    sudo bash ./start.sh || {
        echo "Warning: start.sh reported errors."
        echo "Trying alternative startup method..."
        
        # Try to start with gunicorn directly as fallback
        if [ -f ./Web/app.py ]; then
            echo "Attempting to start with gunicorn directly..."
            cd Web
            sudo gunicorn -b 0.0.0.0:8080 app:app --daemon || {
                echo "Failed to start application with gunicorn."
                echo "Please check the logs for more details."
                exit 1
            }
            cd ..
        else
            echo "Failed to find Web/app.py. Cannot start application."
            exit 1
        fi
    }
else
    echo "Error: start.sh not found. Cannot start application."
    exit 1
fi

echo "Application started successfully!"

echo "========================================================"
echo "              SETTING UP AUTOSTART                      "
echo "========================================================"

# Set up autostart using the update script with restart-server flag
echo "Configuring autostart..."
cd $REPO_DIR
if [ -f ./update.sh ]; then
    chmod +x ./update.sh
    sudo bash ./update.sh --restart-server || {
        echo "Warning: Failed to set up autostart using update.sh."
        echo "Setting up manual systemd service as fallback..."
        
        # Create systemd service file as fallback
        cat > /tmp/inventarsystem.service << EOF
[Unit]
Description=Inventarsystem Web Application
After=network.target mongodb.service

[Service]
User=root
WorkingDirectory=/var/Inventarsystem/Web
ExecStart=/usr/bin/gunicorn -b 0.0.0.0:8080 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        sudo mv /tmp/inventarsystem.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable inventarsystem.service
        sudo systemctl start inventarsystem.service
    }
else
    echo "Warning: update.sh not found, creating systemd service manually..."
    # Create systemd service file
    cat > /tmp/inventarsystem.service << EOF
[Unit]
Description=Inventarsystem Web Application
After=network.target mongodb.service

[Service]
User=root
WorkingDirectory=/var/Inventarsystem/Web
ExecStart=/usr/bin/gunicorn -b 0.0.0.0:8080 app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    sudo mv /tmp/inventarsystem.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable inventarsystem.service
    sudo systemctl start inventarsystem.service
fi

echo "Autostart setup successfully!"
echo "========================================================"
echo "          INVENTARSYSTEM INSTALLATION COMPLETE          "
echo "========================================================"
echo ""
echo "The system is now installed and running at: http://localhost:8080"
echo "Default login credentials can be found in README.md"
echo ""