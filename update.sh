#!/bin/bash

# Configuration
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
BACKUP_BASE_DIR="/var/backups"
LOG_FILE="$PROJECT_DIR/logs/daily_update.log"

# Parse command line arguments
RESTART_SERVER=false
COMPRESSION_LEVEL=9  # Default to maximum compression

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restart-server)
            RESTART_SERVER=true
            shift
            ;;
        --compression-level=*)
            COMPRESSION_LEVEL="${1#*=}"
            # Validate compression level (0-9, where 0 is no compression)
            if ! [[ "$COMPRESSION_LEVEL" =~ ^[0-9]$ ]]; then
                echo "Invalid compression level. Must be 0-9."
                echo "Usage: $0 [--restart-server] [--compression-level=0-9]"
                exit 1
            fi
            shift
            ;;
        --help)
            echo "Usage: $0 [--restart-server] [--compression-level=0-9]"
            echo "Options:"
            echo "  --restart-server        Restart the server after the update"
            echo "  --compression-level=N   Set compression level (0-9, default is 9)"
            exit 0
            ;;
        *)
            echo "Unknown parameter: $1"
            echo "Usage: $0 [--restart-server] [--compression-level=0-9]"
            exit 1
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"
# Ensure proper permissions for logs directory
if [ -d "$PROJECT_DIR/logs" ]; then
    chmod 777 "$PROJECT_DIR/logs" 2>/dev/null || true
fi

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to create backup
create_backup() {
    log_message "Starting backup process..."
    
    # Create date-formatted directory name
    CURRENT_DATE=$(date +"%Y-%m-%d")
    BACKUP_NAME="Inventarsystem-$CURRENT_DATE"
    BACKUP_DIR="$BACKUP_BASE_DIR/$BACKUP_NAME"
    BACKUP_ARCHIVE="$BACKUP_BASE_DIR/$BACKUP_NAME.tar.gz"
    
    # Create backup directory if it doesn't exist
    if [ ! -d "$BACKUP_BASE_DIR" ]; then
        sudo mkdir -p "$BACKUP_BASE_DIR"
        sudo chmod 755 "$BACKUP_BASE_DIR"
    fi
    
    # Remove existing backup with same date if it exists
    if [ -d "$BACKUP_DIR" ]; then
        log_message "Removing existing backup directory at $BACKUP_DIR"
        sudo rm -rf "$BACKUP_DIR"
    fi
    
    if [ -f "$BACKUP_ARCHIVE" ]; then
        log_message "Removing existing backup archive at $BACKUP_ARCHIVE"
        sudo rm -f "$BACKUP_ARCHIVE"
    fi
    
    # Create a temporary directory for backup
    log_message "Creating backup at $BACKUP_DIR"
    sudo mkdir -p "$BACKUP_DIR"
    sudo cp -r "$PROJECT_DIR"/* "$BACKUP_DIR"
    
    # Create database backup using Backup-DB.py
    log_message "Running database backup..."
    # Create mongodb_backup directory with appropriate permissions first
    sudo mkdir -p "$BACKUP_DIR/mongodb_backup"
    sudo chmod 777 "$BACKUP_DIR/mongodb_backup"  # Temporarily give write permissions
    
    # Install pymongo if not already installed
    log_message "Checking pymongo installation..."
    if ! python3 -c "import pymongo" &>/dev/null; then
        log_message "Installing pymongo..."
        # Try multiple installation methods
        if [ -f "$PROJECT_DIR/.venv/bin/pip" ]; then
            "$PROJECT_DIR/.venv/bin/pip" install pymongo==4.6.3 >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
                log_message "WARNING: Failed to install pymongo with virtualenv pip. Trying system pip."
                pip install pymongo==4.6.3 >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
                    log_message "WARNING: Failed to install pymongo with pip. Trying pip3."
                    pip3 install pymongo==4.6.3 >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
                        log_message "WARNING: All attempts to install pymongo failed. Will try to continue."
                    }
                }
            }
        else
            pip install pymongo==4.6.3 >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
                log_message "WARNING: Failed to install pymongo with pip. Trying pip3."
                pip3 install pymongo==4.6.3 >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
                    log_message "WARNING: All attempts to install pymongo failed. Will try to continue."
                }
            }
        fi
    fi
    
    # Run database backup with our helper script
    log_message "Executing database backup script..."
    sudo -E "$PROJECT_DIR/run-backup.sh" --db Inventarsystem --uri mongodb://localhost:27017/ --out "$BACKUP_DIR/mongodb_backup" >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 || {
        log_message "ERROR: Failed to backup database with original path"
        
        # Try an alternative approach - use a temporary directory
        log_message "Attempting backup via temporary directory..."
        tmp_backup_dir="/tmp/mongodb_backup_$$"
        mkdir -p "$tmp_backup_dir"
        
        "$PROJECT_DIR/run-backup.sh" --db Inventarsystem --uri mongodb://localhost:27017/ --out "$tmp_backup_dir" >> "$PROJECT_DIR/logs/Backup_db.log" 2>&1 && {
            log_message "Backup created in temporary directory, moving to backup location..."
            sudo cp -r "$tmp_backup_dir"/* "$BACKUP_DIR/mongodb_backup/" 
            rm -rf "$tmp_backup_dir"
        } || {
            log_message "ERROR: All attempts to backup database failed"
            # Continue with the backup process even if DB backup fails
        }
    }
    
    # Reset to more restrictive permissions after backup completes
    sudo chmod -R 755 "$BACKUP_DIR/mongodb_backup"
    
    # Verify that backup files were created
    csv_count=$(find "$BACKUP_DIR/mongodb_backup" -name "*.csv" 2>/dev/null | wc -l)
    if [ "$csv_count" -gt 0 ]; then
        log_message "Database backup successful: $csv_count collection(s) backed up"
    else
        log_message "WARNING: No CSV files found in backup directory, database backup may have failed"
    fi
    
    # Compress the backup
    if [ "$COMPRESSION_LEVEL" -gt 0 ]; then
        log_message "Compressing backup with level $COMPRESSION_LEVEL..."
        
        # Create compressed archive
        # Using standard tar without compression level option (not all tar versions support it)
        sudo tar -czf "$BACKUP_ARCHIVE" -C "$BACKUP_BASE_DIR" "$BACKUP_NAME" || {
            log_message "ERROR: Failed to compress backup"
            return 1
        }
        
        # Remove uncompressed directory after successful compression
        if [ -f "$BACKUP_ARCHIVE" ]; then
            log_message "Backup compressed successfully to $BACKUP_ARCHIVE"
            log_message "Removing uncompressed backup directory"
            sudo rm -rf "$BACKUP_DIR"
        else
            log_message "ERROR: Compressed backup file not found"
            return 1
        fi
    else
        log_message "Compression disabled, keeping uncompressed backup"
    fi
    
    # Set appropriate permissions
    if [ "$COMPRESSION_LEVEL" -gt 0 ]; then
        sudo chmod 644 "$BACKUP_ARCHIVE"
    else
        sudo chmod -R 755 "$BACKUP_DIR"
    fi
    
    # Clean up old backups (keep last 7 days)
    log_message "Cleaning up old backups..."
    # Clean up compressed backups
    find "$BACKUP_BASE_DIR" -maxdepth 1 -name "Inventarsystem-*.tar.gz" -type f -mtime +7 -exec sudo rm -f {} \;
    # Clean up uncompressed backups
    find "$BACKUP_BASE_DIR" -maxdepth 1 -name "Inventarsystem-*" -type d -mtime +7 -exec sudo rm -rf {} \;
    
    log_message "Backup completed successfully"
    return 0
}

# Function to update from git
update_from_git() {
    log_message "Updating from git repository..."
    
    # Navigate to project directory
    cd "$PROJECT_DIR" || {
        log_message "ERROR: Could not navigate to project directory"
        return 1
    }
    
    # Pull latest changes
    git pull || {
        log_message "ERROR: Git pull failed"
        return 1
    }
    
    log_message "Git update completed successfully"
    return 0
}

# Function to restart services
restart_services() {
    log_message "Restarting services..."
    
    # Navigate to project directory
    cd "$PROJECT_DIR" || {
        log_message "ERROR: Could not navigate to project directory"
        return 1
    }
    
    # Execute restart script
    ./restart.sh || {
        log_message "ERROR: Failed to restart services"
        return 1
    }
    
    log_message "Services restarted successfully"
    return 0
}

# Function to restart the server
restart_server() {
    log_message "Preparing for server restart..."
    
    # Make sure all buffers are written to disk
    sync
    
    # Schedule a reboot
    log_message "Initiating server reboot..."
    sudo shutdown -r +1 "Server restart initiated by daily update script" || {
        log_message "ERROR: Failed to initiate server restart"
        return 1
    }
    
    log_message "Server restart scheduled in 1 minute"
    return 0
}

# Function to setup cron job
setup_cron_job() {
    log_message "Checking cron job configuration..."
    
    # Define cron job to run daily at 2:00 AM
    CRON_JOB="0 2 * * * $PROJECT_DIR/update.sh"
    
    # Check if cron job already exists
    EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$PROJECT_DIR/update.sh")
    
    if [ -z "$EXISTING_CRON" ]; then
        log_message "Setting up daily cron job..."
        
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        
        if [ $? -eq 0 ]; then
            log_message "Cron job set up successfully"
        else
            log_message "ERROR: Failed to set up cron job"
        fi
    else
        log_message "Cron job already exists, skipping setup"
    fi
}

# Main execution
log_message "====== Starting daily update process ======"

# Create backup
create_backup

# Update from git
if update_from_git; then
    # Restart services if update successful
    restart_services
else
    log_message "WARNING: Skipping service restart due to git update failure"
fi

# Setup cron job if running manually (not from cron)
if [ -z "$CRONARG" ]; then
    setup_cron_job
fi

# Restart server if requested
if [ "$RESTART_SERVER" = true ]; then
    log_message "Server restart was requested"
    restart_server
    if [ $? -eq 0 ]; then
        log_message "====== Daily update process completed - SERVER WILL RESTART SOON ======"
        echo "SERVER WILL RESTART IN 1 MINUTE"
        exit 0
    else
        log_message "====== Daily update process completed with SERVER RESTART FAILURE ======"
    fi
else
    log_message "====== Daily update process completed ======"
fi
