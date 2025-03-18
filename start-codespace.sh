#!/bin/bash

# Get the local network IP address
NETWORK_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Set project root directory
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" || {
    echo "Failed to determine project root directory. Exiting."
    exit 1
}
VENV_DIR="$PROJECT_ROOT/.venv"

sudo apt install python3.12
sudo apt install python3.12-venv

# Create logs directory if it doesn't exist
sudo mkdir -p "$PROJECT_ROOT/logs"

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
                sudo apt-get update
                sudo apt-get install -y mongodb || sudo apt-get install -y mongodb-org || {
                    echo "Failed to install MongoDB. Please install manually."
                    echo "Instructions: https://docs.mongodb.com/manual/installation/"
                    
                    read -p "Continue without MongoDB? (y/n): " -n 1 -r
                    echo
                    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                        return 1
                    fi
                }
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

if [ ! -f "$PROJECT_ROOT/DeploymentCenter/app.py" ]; then
    echo "ERROR: DeploymentCenter application file DeploymentCenter/app.py not found!"
    exit 1
fi

echo "✓ Flask application files found"

echo "========================================================"
echo "           GENERATING SSL CERTIFICATES                  "
echo "========================================================"

# Generate SSL certificates if they don't exist
if [ ! -f $CERT_DIR/inventarsystem.crt ] || [ ! -f $CERT_DIR/inventarsystem.key ]; then
    echo "Generating SSL certificates..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout $CERT_DIR/inventarsystem.key -out $CERT_DIR/inventarsystem.crt \
        -subj "/C=DE/ST=State/L=City/O=Inventarsystem/CN=$NETWORK_IP"
    
    # Fix permissions
    chmod 600 $CERT_DIR/inventarsystem.key
    echo "✓ SSL certificates generated"
else
    echo "✓ SSL certificates already exist"
fi

# Set environment variables
export FLASK_ENV=production
export FLASK_APP=Web/app.py

# Add this after creating CERT_DIR and before checking virtual environment

# Check if running in a GitHub Codespace
if [ -n "$CODESPACES" ] && [ "$CODESPACES" = "true" ]; then
    echo "========================================================"
    echo "       DETECTED GITHUB CODESPACE ENVIRONMENT            "
    echo "========================================================"
    IS_CODESPACE=true
    
    # Use service instead of systemctl in Codespaces
    NGINX_START_CMD="sudo service nginx start"
    NGINX_STOP_CMD="sudo service nginx stop"
    
    # Use direct port binding instead of Unix sockets
    USE_DIRECT_PORTS=true
    WEB_BINDING="0.0.0.0:8443"
    DEPLOYMENT_BINDING="0.0.0.0:8444"
    
    echo "Configured for direct port binding in Codespace environment"
    echo "Ports 8443 and 8444 will be used directly"
    
    # Make sure GitHub CLI is available
    if ! command -v gh &> /dev/null; then
        echo "Installing GitHub CLI..."
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt update
        sudo apt install -y gh
    fi
else
    IS_CODESPACE=false
    
    # Use systemctl for standard environments
    NGINX_START_CMD="sudo systemctl restart nginx"
    NGINX_STOP_CMD="sudo systemctl stop nginx"
    
    # Use Unix sockets for standard environments
    USE_DIRECT_PORTS=false
    WEB_BINDING="unix:/tmp/inventarsystem.sock"
    DEPLOYMENT_BINDING="unix:/tmp/deployment.sock"
fi


if [ "$IS_CODESPACE" = true ]; then
    echo "========================================================"
    echo "           CONFIGURING MONGODB FOR CODESPACE            "
    echo "========================================================"
    
    # Check if MongoDB is installed
    if ! command -v mongod &> /dev/null; then
        echo "Installing MongoDB in Codespace environment..."
        # Add MongoDB apt repository
        curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
            sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg \
            --dearmor
        
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
            sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        
        sudo apt-get update
        sudo apt-get install -y mongodb-org
    fi
    
    # Create data directory if it doesn't exist
    echo "Setting up MongoDB data directory..."
    sudo mkdir -p /data/db
    sudo chmod 777 /data/db
    
    # Check if MongoDB is already running
    if pgrep mongod > /dev/null; then
        echo "MongoDB is already running."
    else
        echo "Starting MongoDB in the background..."
        mongod --fork --logpath "$PROJECT_ROOT/logs/mongodb.log" --bind_ip 127.0.0.1
        
        # Wait for MongoDB to start
        echo "Waiting for MongoDB to start..."
        sleep 5
        
        if pgrep mongod > /dev/null; then
            echo "✓ MongoDB started successfully"
        else
            echo "WARNING: MongoDB failed to start. Check logs at $PROJECT_ROOT/logs/mongodb.log"
        fi
    fi
    
    # Test MongoDB connection
    echo "Testing MongoDB connection..."
    if mongo --eval "db.version()" 127.0.0.1:27017 &>/dev/null; then
        echo "✓ MongoDB connection successful"
    else
        echo "WARNING: Could not connect to MongoDB. Your application might not work correctly."
        echo "You may need to manually run: mongod --fork --logpath $PROJECT_ROOT/logs/mongodb.log"
    fi
else
    # Standard MongoDB setup for non-Codespace environments
    # Verify MongoDB service using systemctl
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
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Exiting."
                exit 1
            fi
        fi
    else
        echo "✓ MongoDB is running"
    fi
fi

echo "========================================================"
echo "           CONFIGURING NGINX                            "
echo "========================================================"

# Create Nginx config file based on environment
echo "Creating Nginx configuration..."
if [ "$IS_CODESPACE" = true ]; then
    # Codespace-specific Nginx configuration
    sudo tee /etc/nginx/sites-available/inventarsystem.conf > /dev/null << EOF
# Main app configuration - Codespace-specific
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8443;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static {
        alias $PROJECT_ROOT/Web/static;
    }
}

# Deployment app configuration - Codespace-specific
server {
    listen 8080;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8444;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $PROJECT_ROOT/DeploymentCenter/static;
    }
}
EOF
else
    # Standard Nginx configuration with SSL
    sudo tee /etc/nginx/sites-available/inventarsystem.conf > /dev/null << EOF
# HTTPS for main app
server {
    listen 8443 ssl;
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

# HTTPS for deployment app
server {
    listen 8444 ssl;
    server_name _;
    
    ssl_certificate $CERT_DIR/inventarsystem.crt;
    ssl_certificate_key $CERT_DIR/inventarsystem.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    location / {
        proxy_pass http://unix:/tmp/deployment.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $PROJECT_ROOT/DeploymentCenter/static;
    }
}
EOF
fi

# Create symbolic link to enable the site
if [ ! -f /etc/nginx/sites-enabled/inventarsystem.conf ]; then
    sudo ln -s /etc/nginx/sites-available/inventarsystem.conf /etc/nginx/sites-enabled/
fi

# Check Nginx configuration
sudo nginx -t || {
    echo "ERROR: Nginx configuration is invalid."
    exit 1
}

# Ensure socket files are not present from previous runs
rm -f /tmp/inventarsystem.sock /tmp/deployment.sock

# Start Nginx using the appropriate command
$NGINX_START_CMD || {
    echo "ERROR: Failed to start Nginx. Continuing anyway..."
}
echo "✓ Nginx configured and started"

# Expose ports in Codespace if needed
if [ "$IS_CODESPACE" = true ]; then
    echo "========================================================"
    echo "           CONFIGURING PORT FORWARDING                  "
    echo "========================================================"
    
    # Try to make ports public
    echo "Making ports 8443 and 8444 public..."
    for PORT in 8443 8444; do
        echo "Setting port $PORT to public..."
        gh codespace ports visibility $PORT:public 2>/dev/null || echo "Failed to make port $PORT public via CLI"
    done
    
    echo "IMPORTANT: If ports are not public, please make them manually public in the PORTS tab."
fi

echo "========================================================"
echo "           STARTING APPLICATIONS                        "
echo "========================================================"

# Show access information
echo "========================================================"
echo "Access Information:"

if [ "$IS_CODESPACE" = true ]; then
    CODESPACE_NAME=$(gh codespace list --json name -q '.[0].name' 2>/dev/null)
    GITHUB_CODESPACE_DOMAIN=$(echo "$GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN" | sed 's/^\(.*\)$/\1/')
    
    echo "Codespace Web Interface: https://$CODESPACE_NAME-8443.$GITHUB_CODESPACE_DOMAIN"
    echo "Codespace DeploymentCenter: https://$CODESPACE_NAME-8444.$GITHUB_CODESPACE_DOMAIN"
    echo "Local Web Interface: http://localhost:8443"
    echo "Local DeploymentCenter: http://localhost:8444"
else
    echo "Web Interface: https://$NETWORK_IP:8443"
    echo "DeploymentCenter: https://$NETWORK_IP:8444"
fi

echo "========================================================"
echo "NOTE: Your browser may show a security warning because"
echo "      we're using a self-signed certificate."
echo "      This is normal and you can safely proceed."
echo "========================================================"

# Start DeploymentCenter in background
echo "Starting DeploymentCenter with Gunicorn..."
cd $PROJECT_ROOT/DeploymentCenter
gunicorn app:app --bind $DEPLOYMENT_BINDING --workers 1 --access-logfile ../logs/deployment-access.log --error-logfile ../logs/deployment-error.log &
DEPLOYMENT_PID=$!
echo "DeploymentCenter started with PID: $DEPLOYMENT_PID"
sleep 2

# Check if the deployment socket was created (if using sockets)
if [ "$USE_DIRECT_PORTS" = false ] && [ ! -S "/tmp/deployment.sock" ]; then
    echo "ERROR: Deployment socket not created. Check logs for errors:"
    cat ../logs/deployment-error.log
    echo "Attempting to continue anyway..."
fi

# Return to project directory
cd $PROJECT_ROOT

# Start main application with Gunicorn in foreground
echo "Starting Inventarsystem main application with Gunicorn..."
cd Web
gunicorn app:app --bind $WEB_BINDING --workers 1 --access-logfile ../logs/access.log --error-logfile ../logs/error.log

# Cleanup section remains the same, but use the appropriate command to stop Nginx
if ps -p $DEPLOYMENT_PID > /dev/null; then
    echo "Stopping DeploymentCenter (PID: $DEPLOYMENT_PID)..."
    kill $DEPLOYMENT_PID
fi

# Stop Nginx when done
$NGINX_STOP_CMD

cd $PROJECT_ROOT

# Deactivate virtual environment
deactivate

echo "All services stopped."
