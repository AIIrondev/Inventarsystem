#!/bin/bash

# Comprehensive script to fix all permission issues in the Inventarsystem
# This script should be run with sudo privileges

# Get the script directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
LOG_FILE="$SCRIPT_DIR/logs/permission_fixes.log"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"
touch "$LOG_FILE"
chmod 777 "$SCRIPT_DIR/logs"
chmod 666 "$LOG_FILE"

log_message "Starting comprehensive permission fixes"

# Fix ownership of the entire project directory
log_message "Setting ownership of project directory..."
chown -R $(logname):$(logname) "$SCRIPT_DIR" 2>/dev/null || {
    log_message "WARNING: Could not set ownership for the entire project directory."
}

# Fix permissions for logs directory
log_message "Setting permissions for logs directory..."
chmod -R 777 "$SCRIPT_DIR/logs" || {
    log_message "ERROR: Failed to set permissions on logs directory."
}

# Create and set permissions for Backup_db.log
log_message "Setting permissions for Backup_db.log..."
touch "$SCRIPT_DIR/logs/Backup_db.log" 2>/dev/null
chmod 666 "$SCRIPT_DIR/logs/Backup_db.log" || {
    log_message "WARNING: Failed to set permissions on Backup_db.log."
}

# Fix permissions for all script files
log_message "Making all shell scripts executable..."
find "$SCRIPT_DIR" -name "*.sh" -exec chmod +x {} \; || {
    log_message "WARNING: Could not make some script files executable."
}

# Fix git repository permissions
log_message "Setting git repository as safe directory..."
git config --global --add safe.directory "$SCRIPT_DIR" || {
    log_message "WARNING: Failed to add repository to git safe.directory."
}

# Fix permissions for virtual environment
if [ -d "$SCRIPT_DIR/.venv" ]; then
    log_message "Setting permissions for virtual environment..."
    chmod -R 755 "$SCRIPT_DIR/.venv" || {
        log_message "WARNING: Could not set permissions on virtual environment."
    }
    find "$SCRIPT_DIR/.venv" -type d -exec chmod 755 {} \; 2>/dev/null
    find "$SCRIPT_DIR/.venv" -type f -exec chmod 644 {} \; 2>/dev/null
    find "$SCRIPT_DIR/.venv/bin" -type f -exec chmod 755 {} \; 2>/dev/null
    log_message "✓ Virtual environment permissions set"
else
    log_message "Virtual environment not found, skipping permission fix."
fi

# Fix permissions for web directory
if [ -d "$SCRIPT_DIR/Web" ]; then
    log_message "Setting permissions for Web directory..."
    chmod -R 755 "$SCRIPT_DIR/Web" || {
        log_message "WARNING: Could not set permissions on Web directory."
    }
    
    # Fix permissions for uploads and QRCodes directories
    for dir in "$SCRIPT_DIR/Web/uploads" "$SCRIPT_DIR/Web/QRCodes" "$SCRIPT_DIR/Web/thumbnails" "$SCRIPT_DIR/Web/previews"; do
        if [ -d "$dir" ]; then
            log_message "Setting permissions for $dir..."
            chmod -R 777 "$dir" || {
                log_message "WARNING: Could not set permissions on $dir."
            }
        else
            log_message "Creating and setting permissions for $dir..."
            mkdir -p "$dir"
            chmod -R 777 "$dir" || {
                log_message "WARNING: Could not set permissions on $dir."
            }
        fi
    done
    
    log_message "✓ Web directory permissions set"
else
    log_message "Web directory not found, skipping permission fix."
fi

# Fix permissions for backup directory
if [ -d "/var/backups" ]; then
    log_message "Setting permissions for backup directory..."
    chmod 755 "/var/backups" || {
        log_message "WARNING: Could not set permissions on backup directory."
    }
    log_message "✓ Backup directory permissions set"
else
    log_message "Backup directory not found, skipping permission fix."
fi

# Verify mongo access
log_message "Verifying MongoDB access..."
if command -v mongod &> /dev/null; then
    # Ensure mongodb data directory has right permissions
    if [ -d "/var/lib/mongodb" ]; then
        chmod 750 /var/lib/mongodb || {
            log_message "WARNING: Could not set permissions on MongoDB data directory."
        }
        chown -R mongodb:mongodb /var/lib/mongodb || {
            log_message "WARNING: Could not set ownership on MongoDB data directory."
        }
        log_message "✓ MongoDB directory permissions set"
    else
        log_message "MongoDB data directory not found, skipping permission fix."
    fi
else
    log_message "MongoDB not found, skipping MongoDB permission fixes."
fi

# Fix permissions for systemd service files
if [ -f "/etc/systemd/system/inventarsystem-gunicorn.service" ]; then
    log_message "Setting permissions for systemd service files..."
    chmod 644 /etc/systemd/system/inventarsystem-gunicorn.service || {
        log_message "WARNING: Could not set permissions on gunicorn service file."
    }
    chmod 644 /etc/systemd/system/inventarsystem-nginx.service 2>/dev/null || {
        log_message "WARNING: Could not set permissions on nginx service file (may not exist)."
    }
    systemctl daemon-reload
    log_message "✓ Systemd service file permissions set"
else
    log_message "Systemd service files not found, skipping permission fix."
fi

log_message "Comprehensive permission fixes completed"
log_message "If you still experience permission issues, consider running 'sudo chmod -R 755 $SCRIPT_DIR'"

exit 0
