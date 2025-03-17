#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p /logs

# Create certificates directory if it doesn't exist
CERT_DIR="/certs"
mkdir -p $CERT_DIR

# Get the local network IP address
NETWORK_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -n 1)

# Set project root directory
PROJECT_ROOT="/"
VENV_DIR="$PROJECT_ROOT/.venv"

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

echo "========================================================"
echo "           CONFIGURING NGINX                            "
echo "========================================================"

# Create Nginx config file
echo "Creating Nginx configuration..."
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

# Restart Nginx to apply configuration
sudo systemctl restart nginx || {
    echo "ERROR: Failed to restart Nginx."
    exit 1
}
echo "✓ Nginx configured and started"

echo "========================================================"
echo "           STARTING APPLICATIONS                        "
echo "========================================================"

# Show access information
echo "========================================================"
echo "Access Information:"
echo "Web Interface: https://$NETWORK_IP:8443"
echo "DeploymentCenter: https://$NETWORK_IP:8444"
echo "========================================================"
echo "NOTE: Your browser may show a security warning because"
echo "      we're using a self-signed certificate."
echo "      This is normal and you can safely proceed."
echo "========================================================"

# Start DeploymentCenter in background
echo "Starting DeploymentCenter with Gunicorn..."
cd $PROJECT_ROOT/DeploymentCenter
gunicorn app:app --bind unix:/tmp/deployment.sock --workers 1 --access-logfile ../logs/deployment-access.log --error-logfile ../logs/deployment-error.log &
DEPLOYMENT_PID=$!
echo "DeploymentCenter started with PID: $DEPLOYMENT_PID"
sleep 2

# Check if the deployment socket was created
if [ ! -S "/tmp/deployment.sock" ]; then
    echo "ERROR: Deployment socket not created. Check logs for errors:"
    cat ../logs/deployment-error.log
    echo "Attempting to continue anyway..."
fi

# Return to project directory
cd $PROJECT_ROOT

# Start main application with Gunicorn in foreground
echo "Starting Inventarsystem main application with Gunicorn..."
cd Web
gunicorn app:app --bind unix:/tmp/inventarsystem.sock --workers 1 --access-logfile ../logs/access.log --error-logfile ../logs/error.log

# If we get here, kill the background DeploymentCenter process
if ps -p $DEPLOYMENT_PID > /dev/null; then
    echo "Stopping DeploymentCenter (PID: $DEPLOYMENT_PID)..."
    kill $DEPLOYMENT_PID
fi

# Stop Nginx when done
sudo systemctl stop nginx

cd $PROJECT_ROOT

# Deactivate virtual environment
deactivate

echo "All services stopped."