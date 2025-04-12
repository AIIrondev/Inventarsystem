#!/bin/bash

# Get the local network IP address
NETWORK_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Set project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" || {
    echo "Failed to determine project root directory. Exiting."
    exit 1
}
VENV_DIR="$PROJECT_ROOT/.venv"

# Create logs directory if it doesn't exist
sudo mkdir -p "$PROJECT_ROOT/logs"
# Ensure current user owns the logs directory
sudo chown -R $(whoami) "$PROJECT_ROOT/logs"
# Set appropriate permissions
sudo chmod -R 755 "$PROJECT_ROOT/logs"

# Create certificates directory if it doesn't exist
CERT_DIR="$PROJECT_ROOT/certs"
sudo mkdir -p $CERT_DIR

echo "========================================================"
echo "           CHECKING/CREATING VIRTUAL ENVIRONMENT        "
echo "========================================================"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating one..."
    
    # Check if venv module is available
    python3 -m venv --help > /dev/null 2>&1 || {
        echo "Python venv module not available. Installing..."
        sudo apt-get update
        sudo apt-get install -y python3-venv || {
            echo "Failed to install python3-venv. Exiting."
            exit 1
        }
    }
    
    # Create virtual environment
    python3 -m venv "$VENV_DIR" || {
        echo "Failed to create virtual environment. Exiting."
        exit 1
    }
    
    echo "✓ Virtual environment created at $VENV_DIR"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate" || {
    echo "Failed to activate virtual environment. Exiting."
    exit 1
}

# Upgrade pip in virtual environment
echo "Upgrading pip in virtual environment..."
pip install --upgrade pip || echo "Warning: Failed to upgrade pip."

# Function to check and install package
check_and_install() {
    echo "Checking for $1..."
    if ! command -v $1 &> /dev/null; then
        echo "Installing $1..."
        case $1 in
            nginx)
                sudo apt-get update
                sudo apt-get install -y nginx || return 1
                ;;
            gunicorn)
                pip install gunicorn || return 1
                ;;
            openssl)
                sudo apt-get update
                sudo apt-get install -y openssl || return 1
                ;;
            mongod)
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
                
                # Install MongoDB
                sudo apt-get update
                sudo apt-get install -y mongodb-org || return 1
                ;;
            *)
                echo "Unknown package: $1"
                return 1
                ;;
        esac
    fi
    echo "✓ $1 is installed"
    return 0
}

echo "========================================================"
echo "           CHECKING REQUIRED APPLICATIONS               "
echo "========================================================"

# Check all required applications
check_and_install nginx || { echo "Failed to install nginx. Exiting."; exit 1; }
check_and_install gunicorn || { echo "Failed to install gunicorn. Exiting."; exit 1; }
check_and_install openssl || { echo "Failed to install openssl. Exiting."; exit 1; }
check_and_install mongod || echo "MongoDB installation incomplete. Continuing anyway..."

# Create Nginx configuration with HTTPS
cd $PROJECT_ROOT

echo "========================================================"
echo "           INSTALLING PYTHON DEPENDENCIES               "
echo "========================================================"

# Prepare Python environment
# Create a temporary requirements file without bson
if [ -f requirements.txt ]; then
    echo "Creating modified requirements file..."
    grep -v "^bson" requirements.txt > requirements_modified.txt
    
    # Install Python requirements except PyMongo (we'll install a specific version later)
    echo "Installing Python dependencies..."
    grep -v "^pymongo" requirements_modified.txt > requirements_no_mongo.txt
    pip install -r requirements_no_mongo.txt || {
        echo "Warning: Some Python dependencies may not be installed correctly."
    }
    rm requirements_no_mongo.txt requirements_modified.txt
fi

# Fix PyMongo/Bson compatibility issue
echo "Fixing PyMongo/Bson compatibility issue..."
pip uninstall -y bson pymongo
pip install pymongo==4.6.1 || {
    echo "Failed to install pymongo. Exiting."
    exit 1
}
echo "PyMongo installed successfully"

echo "========================================================"
echo "              VERIFYING INSTALLATIONS                   "
echo "========================================================"

# Verify Nginx installation
nginx -v || {
    echo "ERROR: Nginx not installed properly."
    exit 1
}

# Verify Gunicorn installation
gunicorn --version || {
    echo "ERROR: Gunicorn not installed properly."
    exit 1
}

# Verify MongoDB service
if ! systemctl is-active --quiet mongodb && ! systemctl is-active --quiet mongod; then
    echo "Starting MongoDB service..."
    # Try different service names
    MONGODB_STARTED=false
    for SERVICE in mongodb mongod; do
        if systemctl list-unit-files | grep -q $SERVICE; then
            sudo systemctl start $SERVICE
            if [ $? -eq 0 ]; then
                echo "Started $SERVICE service"
                MONGODB_STARTED=true
                break
            fi
        fi
    done
    
    if [ "$MONGODB_STARTED" = false ]; then
        echo "Warning: Could not start MongoDB service"
        read -p "Continue without MongoDB? (y/n): " -n 1 -r
        echo "Warning: The website might not respond to any requests from clients if the database is down"
        echo 
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Exiting."
            exit 1
        fi
    fi
else
    echo "✓ MongoDB is running"
fi

# Verify PyMongo installation is correct
echo "Verifying PyMongo installation..."
python -c "from pymongo import MongoClient; from bson import SON; print('✓ PyMongo configuration correct')" || {
    echo "ERROR: PyMongo still not configured correctly."
    echo "Trying to fix by uninstalling standalone bson..."
    pip uninstall -y bson
    python -c "from pymongo import MongoClient; from bson import SON; print('✓ PyMongo configuration fixed')" || {
        echo "ERROR: PyMongo configuration still incorrect. Exiting."
        exit 1
    }
}

# Verify Flask application files
echo "Checking Flask application files..."
if [ ! -f "$PROJECT_ROOT/Web/app.py" ]; then
    echo "ERROR: Main application file Web/app.py not found!"
    exit 1
fi

echo "✓ Flask application files found"

echo "========================================================"
echo "           CHECKING FOR SSL CERTIFICATES                "
echo "========================================================"

# Set default certificate paths
CERT_PATH="${CUSTOM_CERT_PATH:-$CERT_DIR/inventarsystem.crt}"
KEY_PATH="${CUSTOM_KEY_PATH:-$CERT_DIR/inventarsystem.key}"

# Check if custom certificates are specified and exist
if [ -n "$CUSTOM_CERT_PATH" ] && [ -n "$CUSTOM_KEY_PATH" ]; then
    if [ -f "$CUSTOM_CERT_PATH" ] && [ -f "$CUSTOM_KEY_PATH" ]; then
        echo "Using custom certificates from:"
        echo "  - Certificate: $CUSTOM_CERT_PATH"
        echo "  - Key: $CUSTOM_KEY_PATH"
    else
        echo "WARNING: Specified custom certificates not found!"
        echo "  - Certificate: $CUSTOM_CERT_PATH"
        echo "  - Key: $CUSTOM_KEY_PATH"
        echo "Falling back to default certificate location."
        CERT_PATH="$CERT_DIR/inventarsystem.crt"
        KEY_PATH="$CERT_DIR/inventarsystem.key"
    fi
fi

# Generate SSL certificates if they don't exist
if [ ! -f $CERT_PATH ] || [ ! -f $KEY_PATH ]; then
    echo "Generating SSL certificates..."
    # First ensure the directory is writable by the current user
    sudo chown -R $(whoami) $CERT_DIR
    
    # Generate certificates
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout $CERT_DIR/inventarsystem.key -out $CERT_DIR/inventarsystem.crt \
        -subj "/C=DE/ST=State/L=City/O=Inventarsystem/CN=$NETWORK_IP" || {
            echo "ERROR: Failed to generate SSL certificates"
            exit 1
        }
    
    # Fix permissions
    chmod 600 $CERT_DIR/inventarsystem.key
    
    # Set paths to the newly generated certificates
    CERT_PATH="$CERT_DIR/inventarsystem.crt"
    KEY_PATH="$CERT_DIR/inventarsystem.key"
    
    # Verify certificates exist
    if [ -f $CERT_PATH ] && [ -f $KEY_PATH ]; then
        echo "✓ SSL certificates generated"
    else
        echo "ERROR: SSL certificates were not created properly"
        exit 1
    fi
else
    echo "✓ SSL certificates already exist"
    # Ensure key has appropriate permissions
    chmod 600 $KEY_PATH
fi

# Set environment variables
export FLASK_ENV=production
export FLASK_APP=Web/app.py

# Use systemctl for standard environments
NGINX_START_CMD="sudo systemctl restart nginx"
NGINX_STOP_CMD="sudo systemctl stop nginx"

# Use Unix sockets for standard environments
WEB_BINDING="unix:/tmp/inventarsystem.sock"

echo "========================================================"
echo "           CONFIGURING NGINX                            "
echo "========================================================"

# Create Nginx config file
echo "Creating Nginx configuration..."

# Standard Nginx configuration with SSL
sudo tee /etc/nginx/sites-available/inventarsystem.conf > /dev/null << EOF
# HTTPS for main app
server {
    listen 443 ssl;
    server_name _;
    
    ssl_certificate $CERT_DIR/inventarsystem.crt;
    ssl_certificate_key $CERT_DIR/inventarsystem.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    location / {
        proxy_pass http://unix:/tmp/inventarsystem.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $PROJECT_ROOT/Web/static;
    }
}
EOF

# Create symbolic link to enable the site
if [ ! -f /etc/nginx/sites-enabled/inventarsystem.conf ]; then
    sudo ln -s /etc/nginx/sites-available/inventarsystem.conf /etc/nginx/sites-enabled/
fi

# Check Nginx configuration
sudo nginx -t || {
    echo "ERROR: Nginx configuration is invalid."
    exit 1
}

# Remove inventarsystem.sock if it exists from previous runs
rm -f /tmp/inventarsystem.sock

# Start Nginx using the appropriate command
$NGINX_START_CMD || {
    echo "ERROR: Failed to start Nginx. Continuing anyway..."
}
echo "✓ Nginx configured and started"

echo "========================================================"
echo "           STARTING APPLICATION                         "
echo "========================================================"

# Show access information
echo "========================================================"
echo "Access Information:"
echo "========================================================"

echo "Web Interface: https://$NETWORK_IP"
echo "Web Interface (Unix Socket): http://unix:/tmp/inventarsystem.sock"
echo "MongoDB: mongodb://localhost:27017"
echo "========================================================"

# Add autostart functionality
echo "========================================================"
echo "           CONFIGURING AUTOSTART                        "
echo "========================================================"

# Create systemd service file
SERVICE_FILE="$HOME/.config/systemd/user/inventarsystem.service"
mkdir -p "$HOME/.config/systemd/user"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Inventarsystem Service
After=network.target mongodb.service

[Service]
Type=simple
ExecStart=$PROJECT_ROOT/start.sh
WorkingDirectory=$PROJECT_ROOT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Enable the service for autostart
systemctl --user enable inventarsystem.service

# Enable lingering for the user to allow the service to start on boot
sudo loginctl enable-linger $(whoami)

echo "✓ Autostart enabled. Inventarsystem will start automatically on system boot."

echo "========================================================"
echo "NOTE: Your browser may show a security warning because"
echo "      we're using a self-signed certificate."
echo "      This is normal and you can safely proceed."
echo "========================================================"

# Start main application with Gunicorn
echo "Starting Inventarsystem main application with Gunicorn..."
cd $PROJECT_ROOT/Web
gunicorn app:app --bind $WEB_BINDING --workers 1 --access-logfile ../logs/access.log --error-logfile ../logs/error.log

# Stop Nginx when done
$NGINX_STOP_CMD

cd $PROJECT_ROOT

# Deactivate virtual environment
deactivate

echo "All services stopped."