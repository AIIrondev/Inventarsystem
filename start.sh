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

echo "========================================================"
echo "           CONFIGURING SYSTEMD SERVICES                 "
echo "========================================================"

echo "Fixing systemd service configuration..."

# Detect which MongoDB service is actually available on this system
MONGODB_SERVICE=""
for SERVICE in mongodb mongod; do
    if systemctl list-unit-files | grep -q $SERVICE; then
        MONGODB_SERVICE="$SERVICE"
        echo "✓ Detected MongoDB service: $MONGODB_SERVICE.service"
        break
    fi
done

if [ -z "$MONGODB_SERVICE" ]; then
    echo "Warning: Could not detect MongoDB service. Configuring services without MongoDB dependency."
    
    # Create the gunicorn service file without MongoDB dependency
    sudo tee /etc/systemd/system/inventarsystem-gunicorn.service > /dev/null << EOF
[Unit]
Description=Inventarsystem Gunicorn daemon
After=network.target

[Service]
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$PROJECT_ROOT/Web
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/gunicorn app:app --bind unix:/tmp/inventarsystem.sock --workers 1 --access-logfile $PROJECT_ROOT/logs/access.log --error-logfile $PROJECT_ROOT/logs/error.log
Restart=always
RestartSec=5
SyslogIdentifier=inventarsystem-gunicorn

[Install]
WantedBy=multi-user.target
EOF
else
    # Create the gunicorn service file with correct MongoDB service
    sudo tee /etc/systemd/system/inventarsystem-gunicorn.service > /dev/null << EOF
[Unit]
Description=Inventarsystem Gunicorn daemon
After=network.target $MONGODB_SERVICE.service
Requires=$MONGODB_SERVICE.service

[Service]
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$PROJECT_ROOT/Web
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/gunicorn app:app --bind unix:/tmp/inventarsystem.sock --workers 1 --access-logfile $PROJECT_ROOT/logs/access.log --error-logfile $PROJECT_ROOT/logs/error.log
Restart=always
RestartSec=5
SyslogIdentifier=inventarsystem-gunicorn

[Install]
WantedBy=multi-user.target
EOF
fi

echo "========================================================"
echo "           CONFIGURING NGINX SERVER                     "
echo "========================================================"

# Fix directory permissions for Nginx to access static files
echo "Setting proper permissions for static file access..."
sudo chmod 755 /home/$(whoami)
sudo chmod 755 $PROJECT_ROOT/Web/static || {
    echo "ERROR: Failed to set permissions for static files. Exiting."
    exit 1
}

# Create Nginx server configuration file
sudo tee /etc/nginx/sites-available/inventarsystem > /dev/null << EOF
server {
    listen 80;
    server_name $NETWORK_IP;
    
    # Redirect all HTTP requests to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $NETWORK_IP;
    
    # Add this line to increase the upload limit to 50MB
    client_max_body_size 50M;
    
    # SSL configuration
    ssl_certificate $CERT_PATH;
    ssl_certificate_key $KEY_PATH;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';
    
    # Proxy settings
    location / {
        proxy_pass http://unix:/tmp/inventarsystem.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # Static files
    location /static {
        alias $PROJECT_ROOT/Web/static;
        add_header 'Access-Control-Allow-Origin' '*';
        expires 30d;
        access_log off;
        autoindex off;
        try_files \$uri \$uri/ =404;
    }
    
    # Explicitly handle CSS files
    location ~ ^/static/css/(.+\.css)$ {
        alias $PROJECT_ROOT/Web/static/css/\$1;
        add_header Content-Type text/css;
        expires 30d;
        access_log off;
    }
    
    # Explicitly handle favicon.ico
    location = /favicon.ico {
        alias $PROJECT_ROOT/Web/static/favicon.ico;
        access_log off;
        expires 30d;
    }
}
EOF

# Remove default site if it exists
sudo rm -f /etc/nginx/sites-enabled/default

# Enable the Inventarsystem site
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled/

# Test Nginx configuration
echo "Testing Nginx configuration..."
sudo nginx -t || {
    echo "ERROR: Nginx configuration test failed. Check the error message above."
    exit 1
}

echo "✓ Nginx configuration created and tested"

# Create the nginx service file
sudo tee /etc/systemd/system/inventarsystem-nginx.service > /dev/null << EOF
[Unit]
Description=Nginx for Inventarsystem
After=network.target inventarsystem-gunicorn.service
Requires=inventarsystem-gunicorn.service

[Service]
Type=forking
ExecStartPre=/usr/sbin/nginx -t
ExecStart=/usr/sbin/nginx
ExecReload=/usr/sbin/nginx -s reload
Restart=always
RestartSec=5
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

# Make sure socket directory has correct permissions
sudo mkdir -p /tmp
sudo chmod 1777 /tmp

# Stop the standard nginx service first to avoid conflicts
echo "Stopping standard nginx service if running..."
sudo systemctl stop nginx 2>/dev/null || true

# Reload systemd configuration
echo "Reloading systemd configuration..."
sudo systemctl daemon-reload

# Enable and start the services
echo "Enabling and starting services..."
sudo systemctl enable inventarsystem-gunicorn.service
sudo systemctl enable inventarsystem-nginx.service

# Start gunicorn first
sudo systemctl start inventarsystem-gunicorn.service || {
    echo "ERROR: Failed to start gunicorn service. Check status with: sudo systemctl status inventarsystem-gunicorn.service"
    exit 1
}

# Then start nginx 
sudo systemctl start inventarsystem-nginx.service || {
    echo "ERROR: Failed to start nginx service. Checking status..."
    sudo systemctl status inventarsystem-nginx.service
    echo "For more details run: sudo journalctl -xeu inventarsystem-nginx.service"
    
    # Try to start standard nginx as fallback
    echo "Attempting to start standard nginx as fallback..."
    sudo systemctl start nginx
    exit 1
}

echo "✓ Services configured and started successfully"
echo "To check status: sudo systemctl status inventarsystem-nginx.service"
echo "To view logs: sudo journalctl -u inventarsystem-nginx.service -f"

# Restart Nginx service
sudo systemctl restart inventarsystem-nginx.service

echo "✓ Nginx service restarted"

# Make sure socket directory has correct permissions
sudo mkdir -p /tmp
sudo chmod 1777 /tmp

# Reload systemd configuration
sudo systemctl daemon-reload

# Enable and start the services
sudo systemctl enable inventarsystem-gunicorn.service
sudo systemctl enable inventarsystem-nginx.service
sudo systemctl start inventarsystem-gunicorn.service
sudo systemctl start inventarsystem-nginx.service

echo "✓ Services configured and started"
echo "To check status: sudo systemctl status inventarsystem-gunicorn.service"
echo "To view logs: sudo journalctl -u inventarsystem-gunicorn.service -f"

echo "========================================================"
echo "Access Information:"
echo "========================================================"

echo "Web Interface: https://$NETWORK_IP"
echo "Web Interface (Unix Socket): http://unix:/tmp/inventarsystem.sock"
echo "MongoDB: mongodb://localhost:27017"
echo "========================================================"