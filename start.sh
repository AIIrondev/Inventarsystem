#!/bin/bash
set -euo pipefail

# Copyright 2025-2026 Maximilian Gruendinger
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Discover local IP (fallback to localhost)
NETWORK_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127\.0\.0\.1' | head -n 1 || true)
if [ -z "${NETWORK_IP:-}" ]; then NETWORK_IP="localhost"; fi

# Detect OS ID (best-effort)
OS_ID=$(awk -F= '/^ID=/{print $2}' /etc/os-release | tr -d '"' || echo "linux")

# Project paths
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )" || { echo "Cannot resolve PROJECT_ROOT"; exit 1; }
VENV_DIR="$PROJECT_ROOT/.venv"
CERT_DIR="$PROJECT_ROOT/certs"
LOG_DIR="$PROJECT_ROOT/logs"
ERROR_DIR="/var/www/errors"

echo "========================================================"
echo " Inventarsystem - setup and start (project: $PROJECT_ROOT)"
echo "========================================================"

sudo mkdir -p "$LOG_DIR" "$CERT_DIR" "$ERROR_DIR"
sudo chown -R "${SUDO_USER:-$USER}:${SUDO_USER:-$USER}" "$LOG_DIR" "$CERT_DIR"
sudo chmod 755 "$LOG_DIR" "$CERT_DIR"

echo "========================================================"
echo " Generating error pages"
echo "========================================================"

sudo bash -c "cat > $ERROR_DIR/404.html" <<'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>404 - Page Not Found</title>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    <p>The page you requested could not be found.</p>
</body>
</html>
EOF

sudo bash -c "cat > $ERROR_DIR/50x.html" <<'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Server Error</title>
</head>
<body>
    <h1>Server Error</h1>
    <p>An internal server error occurred.</p>
</body>
</html>
EOF

# Helpers
have_cmd() { command -v "$1" >/dev/null 2>&1; }
apt_install() { sudo apt-get update -y && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"; }

write_nginx_wrapper_service() {
    cat <<EOF | sudo tee /etc/systemd/system/inventarsystem-nginx.service >/dev/null
[Unit]
Description=Nginx for Inventarsystem
After=network.target inventarsystem-gunicorn.service
Requires=inventarsystem-gunicorn.service

[Service]
Type=forking
PIDFile=/run/nginx.pid
ExecStartPre=/usr/sbin/nginx -t
ExecStart=/usr/sbin/nginx
ExecReload=/usr/sbin/nginx -s reload
ExecStop=/bin/kill -s QUIT \$MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
}

write_nginx_tuning_conf() {
    cat <<EOF | sudo tee /etc/nginx/conf.d/inventarsystem-tuning.conf >/dev/null
proxy_headers_hash_max_size 1024;
proxy_headers_hash_bucket_size 128;
EOF
}

find_running_nginx_master() {
    local pid

    while read -r pid; do
        if [ -z "$pid" ]; then
            continue
        fi

        if [ "$(ps -o comm= -p "$pid" 2>/dev/null | tr -d ' ')" != "nginx" ]; then
            continue
        fi

        if [ "$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')" = "1" ]; then
            echo "$pid"
            return 0
        fi
    done < <(
        sudo ss -ltnp '( sport = :80 or sport = :443 or sport = :8080 )' 2>/dev/null \
            | grep -oE 'pid=[0-9]+' \
            | cut -d= -f2 \
            | sort -nu
    )

    return 1
}

repair_nginx_pidfile() {
    local master_pid

    master_pid="$(find_running_nginx_master || true)"
    if [ -z "$master_pid" ]; then
        return 1
    fi

    echo "Repairing nginx PID file using running master process $master_pid"
    printf '%s\n' "$master_pid" | sudo tee /run/nginx.pid >/dev/null
}

start_or_reload_standard_nginx() {
    sudo systemctl enable nginx >/dev/null 2>&1 || true
    echo "Starting/Reloading Nginx..."

    if sudo systemctl is-active --quiet nginx; then
        sudo /usr/sbin/nginx -t
        sudo systemctl reload nginx || sudo /usr/sbin/nginx -s reload
        return 0
    fi

    if repair_nginx_pidfile; then
        sudo /usr/sbin/nginx -t
        sudo /usr/sbin/nginx -s reload
        return 0
    fi

    sudo systemctl reset-failed nginx || true
    sudo systemctl start nginx || sudo systemctl restart nginx
}


echo "========================================================"
echo " Checking/creating Python virtual environment"
echo "========================================================"

if ! have_cmd python3; then
    echo "Installing python3..."
    apt_install python3 || { echo "Failed to install python3"; exit 1; }
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "Installing python3-venv..."
    apt_install python3-venv || { echo "Failed to install python3-venv"; exit 1; }
fi

# (Re)create venv if missing or broken
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Creating virtualenv at $VENV_DIR ..."
    rm -rf "$VENV_DIR" 2>/dev/null || true
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel setuptools || true

check_and_install() {
    echo "Checking for $1..."
    if ! command -v $1 &> /dev/null; then
        echo "Installing $1..."
        case $1 in
            nginx)
		# sudo apt-get update
                sudo apt-get install -y nginx || return 1
                ;;
            gunicorn)
                pip install gunicorn || return 1
                ;;
            openssl)
                # sudo apt-get update
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
                # Add MongoDB repository depending on OS (Ubuntu Server or Linux Mint)
                echo "=== Adding MongoDB repository ==="
                # Prefer Ubuntu base codename from /etc/os-release when available
                UBUNTU_BASE_CODENAME=$(awk -F= '/^UBUNTU_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
                if [ -z "$UBUNTU_BASE_CODENAME" ]; then
                    UBUNTU_BASE_CODENAME=$(lsb_release -cs 2>/dev/null || awk -F= '/^VERSION_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
                fi
                if [ "$OS_ID" = "linuxmint" ]; then
                    # Map Linux Mint codename to Ubuntu base codename when needed
                    MINT_CODENAME=$(lsb_release -cs 2>/dev/null || awk -F= '/^VERSION_CODENAME=/{print $2}' /etc/os-release | tr -d '"')
                    if [ -z "$UBUNTU_BASE_CODENAME" ] || [ "$UBUNTU_BASE_CODENAME" = "$MINT_CODENAME" ]; then
                        case "$MINT_CODENAME" in
                            xia) UBUNTU_BASE_CODENAME="noble" ;;
                            vanessa|vera|victoria) UBUNTU_BASE_CODENAME="jammy" ;;
                            ulyana|ulyssa|uma|una) UBUNTU_BASE_CODENAME="focal" ;;
                        esac
                    fi
                    echo "Detected Linux Mint ($MINT_CODENAME) → using Ubuntu base '$UBUNTU_BASE_CODENAME'"
                elif [ "$OS_ID" = "ubuntu" ];
                then
                    echo "Detected Ubuntu ($UBUNTU_BASE_CODENAME)"
                else
                    echo "Non-Ubuntu/Mint OS detected ($OS_ID). Skipping MongoDB apt setup."
                    return 1
                fi
                # Select MongoDB series per Ubuntu base codename
                case "$UBUNTU_BASE_CODENAME" in
                    noble|jammy)
                        MONGO_SERIES="7.0" ;;
                    focal)
                        MONGO_SERIES="6.0" ;;
                    *)
                        echo "Unknown Ubuntu codename '$UBUNTU_BASE_CODENAME', defaulting to 7.0"
                        MONGO_SERIES="7.0" ;;
                esac
                # Use jammy repo path for noble until MongoDB publishes noble (avoid 404)
                MONGO_APT_CODENAME="$UBUNTU_BASE_CODENAME"
                if [ "$UBUNTU_BASE_CODENAME" = "noble" ]; then
                    MONGO_APT_CODENAME="jammy"
                    echo "Using jammy repo path for MongoDB on noble"
                fi
                # Install repo key and list using series and apt codename
                wget -qO - https://www.mongodb.org/static/pgp/server-${MONGO_SERIES}.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg
                echo "deb [signed-by=/usr/share/keyrings/mongodb-server-${MONGO_SERIES}.gpg arch=amd64,arm64] https://repo.mongodb.org/apt/ubuntu ${MONGO_APT_CODENAME}/mongodb-org/${MONGO_SERIES} multiverse" | \
                    sudo tee /etc/apt/sources.list.d/mongodb-org-${MONGO_SERIES}.list
                # Install MongoDB
                sudo apt-get update || return 1
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

check_and_install nginx || { echo "Failed to install nginx. Exiting."; exit 1; }

check_and_install gunicorn || { echo "Failed to install gunicorn. Exiting."; exit 1; }

check_and_install openssl || { echo "Failed to install openssl. Exiting."; exit 1; }

check_and_install mongod || echo "MongoDB installation incomplete. Continuing anyway..."

sudo systemctl start mongod || true

echo "========================================================"
echo " Installing Python dependencies"
echo "========================================================"
cd "$PROJECT_ROOT"
if [ -f requirements.txt ]; then
    tmp_req1="$(mktemp)"; tmp_req2="$(mktemp)"
    grep -vE '^\s*bson(==|>=|<=|\s|$)' requirements.txt > "$tmp_req1" || true
    grep -vE '^\s*pymongo(==|>=|<=|\s|$)' "$tmp_req1" > "$tmp_req2" || true
    python -m pip install -r "$tmp_req2" || { echo "Failed to install base requirements"; exit 1; }
    rm -f "$tmp_req1" "$tmp_req2"
fi

# Ensure gunicorn installed in venv
if ! have_cmd gunicorn; then
    python -m pip install gunicorn
fi

# Fix PyMongo/BSON compatibility
python -m pip uninstall -y bson pymongo >/dev/null 2>&1 || true
python -m pip install "pymongo==4.6.3"

echo "========================================================"
echo " Checking system packages (nginx, openssl, ufw)"
echo "========================================================"
if ! have_cmd nginx; then apt_install nginx; fi
if ! have_cmd openssl; then apt_install openssl; fi
if ! have_cmd ufw; then apt_install ufw || true; fi

echo "========================================================"
echo " Verifying MongoDB service (optional)"
echo "========================================================"
MONGODB_SERVICE=""
for svc in mongod mongodb; do
    if systemctl --no-pager list-unit-files "${svc}.service" 2>/dev/null | grep -qE "^${svc}\.service"; then
        MONGODB_SERVICE="$svc"
        break
    fi
done
if [ -n "$MONGODB_SERVICE" ]; then
    if ! systemctl is-active --quiet "$MONGODB_SERVICE"; then
        echo "Starting MongoDB service: $MONGODB_SERVICE"
        sudo systemctl start "$MONGODB_SERVICE" || true
    fi
    if systemctl is-active --quiet "$MONGODB_SERVICE"; then echo "✓ MongoDB is running"; else echo "Note: MongoDB not running (continuing)"; fi
else
    echo "Note: MongoDB service not detected (mongod/mongodb). Continuing."
fi

echo "========================================================"
echo " Checking Flask application files"
echo "========================================================"
if [ ! -f "$PROJECT_ROOT/Web/app.py" ]; then
    echo "ERROR: Web/app.py not found at $PROJECT_ROOT/Web/app.py"; exit 1;
fi
echo "✓ Flask app found"

echo "========================================================"
echo " SSL certificate setup"
echo "========================================================"
CERT_PATH="${CUSTOM_CERT_PATH:-$CERT_DIR/inventarsystem.crt}"
KEY_PATH="${CUSTOM_KEY_PATH:-$CERT_DIR/inventarsystem.key}"

if [ -n "${CUSTOM_CERT_PATH:-}" ] && [ -n "${CUSTOM_KEY_PATH:-}" ]; then
    if [ -f "$CUSTOM_CERT_PATH" ] && [ -f "$CUSTOM_KEY_PATH" ]; then
        CERT_PATH="$CUSTOM_CERT_PATH"; KEY_PATH="$CUSTOM_KEY_PATH"
    else
        echo "Custom cert paths invalid, falling back to $CERT_DIR"
    fi
fi

if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    echo "Generating self-signed certificate into $CERT_DIR ..."
    sudo chown -R "${SUDO_USER:-$USER}:${SUDO_USER:-$USER}" "$CERT_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/inventarsystem.key" -out "$CERT_DIR/inventarsystem.crt" \
        -subj "/C=DE/ST=NA/L=NA/O=Inventarsystem/OU=IT/CN=$NETWORK_IP" >/dev/null 2>&1
    chmod 600 "$CERT_DIR/inventarsystem.key"
    CERT_PATH="$CERT_DIR/inventarsystem.crt"; KEY_PATH="$CERT_DIR/inventarsystem.key"
fi
echo "✓ SSL cert: $CERT_PATH"

echo "========================================================"
echo " Writing systemd unit for Gunicorn"
echo "========================================================"
cat <<EOF | sudo tee /etc/systemd/system/inventarsystem-gunicorn.service >/dev/null
[Unit]
Description=Inventarsystem Gunicorn daemon
After=network.target${MONGODB_SERVICE:+ ${MONGODB_SERVICE}.service}
${MONGODB_SERVICE:+Requires=${MONGODB_SERVICE}.service}

[Service]
User=${SUDO_USER:-$USER}
Group=$(id -gn ${SUDO_USER:-$USER})
WorkingDirectory=$PROJECT_ROOT/Web
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$VENV_DIR/bin/gunicorn app:app \
    --bind unix:/tmp/inventarsystem.sock \
    --workers 3 \
    --timeout 60 \
    --graceful-timeout 20 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --capture-output \
    --log-level info \
    --access-logfile $LOG_DIR/access.log \
    --error-logfile $LOG_DIR/error.log
Restart=always
RestartSec=5
SyslogIdentifier=inventarsystem-gunicorn

[Install]
WantedBy=multi-user.target
EOF

echo "========================================================"
echo " Writing Nginx config"
echo "========================================================"
write_nginx_tuning_conf
SERVER_NAME="$NETWORK_IP"
cat <<EOF | sudo tee /etc/nginx/sites-available/inventarsystem >/dev/null
server {
        listen 80;
        server_name ${SERVER_NAME};
    return 301 https://\$server_name\$request_uri;
}

server {
        listen 443 ssl;
        server_name ${SERVER_NAME};
        server_tokens off;

        client_max_body_size 50M;
        autoindex off;

        ssl_certificate     ${CERT_PATH};
        ssl_certificate_key ${KEY_PATH};
        ssl_session_tickets off;

        # Serve static files directly
        location /static/ {
                alias $PROJECT_ROOT/Web/static/;
                access_log off;
                expires 30d;
        }

        location / {
                include proxy_params;
                proxy_hide_header X-Powered-By;
                proxy_pass http://unix:/tmp/inventarsystem.sock;
                proxy_read_timeout 300;
				add_header Cache-Control "public";
        }

        error_page 404 /404.html;
        error_page 500 502 503 504 /50x.html;

        location = /404.html {
            root /var/www/errors;
            internal;
        }

        location = /50x.html {
            root /var/www/errors;
            internal;
        }
        
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default || true
sudo ln -sf /etc/nginx/sites-available/inventarsystem /etc/nginx/sites-enabled/inventarsystem

echo "Testing Nginx configuration..."
sudo nginx -t

echo "========================================================"
echo " Enabling services"
echo "========================================================"
sudo mkdir -p /tmp && sudo chmod 1777 /tmp
# Prefer standard nginx.service; allow opting into a wrapper with USE_NGINX_WRAPPER=true
USE_WRAPPER="${USE_NGINX_WRAPPER:-false}"
if [ "$USE_WRAPPER" = true ]; then
    write_nginx_wrapper_service
fi
sudo systemctl daemon-reload
sudo systemctl enable inventarsystem-gunicorn.service

# If a legacy wrapper exists but wrapper not desired, disable it to avoid conflicts
if [ "$USE_WRAPPER" != true ] && [ -f "/etc/systemd/system/inventarsystem-nginx.service" ]; then
    echo "Disabling legacy inventarsystem-nginx.service wrapper"
    sudo systemctl disable --now inventarsystem-nginx.service || true
fi

echo "Starting Gunicorn..."
sudo systemctl restart inventarsystem-gunicorn.service

if [ "$USE_WRAPPER" = true ]; then
    echo "Detected inventarsystem-nginx.service; using wrapper service for nginx"
    sudo systemctl enable inventarsystem-nginx.service || true
    # Avoid conflicts with native nginx service
    sudo systemctl disable --now nginx || true
    echo "Reloading Nginx (wrapper)..."
    sudo systemctl reload inventarsystem-nginx.service || sudo systemctl restart inventarsystem-nginx.service
else
    start_or_reload_standard_nginx
fi

echo "========================================================"
echo " Firewall (ufw) rules"
echo "========================================================"
if have_cmd ufw; then
    sudo ufw --force enable || true
    sudo ufw allow 22/tcp || true
    sudo ufw allow 80/tcp || true
    sudo ufw allow 443/tcp || true
    sudo ufw allow 8080/tcp || true
fi

echo "========================================================"
echo " Access Information"
echo "========================================================"
echo "Web Interface: https://${NETWORK_IP}"
echo "Gunicorn socket: /tmp/inventarsystem.sock"
echo "Logs: $LOG_DIR (access.log, error.log)"
echo "MongoDB (optional): mongodb://localhost:27017"
echo "========================================================"
echo "✓ Nginx configuration created and tested"
