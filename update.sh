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

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
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
    
    python Backup-DB.py --db Inventarsystem --uri mongodb://localhost:27017/ $BACKUP_DIR >> $LOG_FILE/Backup_db.log
    
    # Compress the backup
    if [ "$COMPRESSION_LEVEL" -gt 0 ]; then
        log_message "Compressing backup with level $COMPRESSION_LEVEL..."
        
        # Create compressed archive
        sudo tar -czf "$BACKUP_ARCHIVE" -C "$BACKUP_BASE_DIR" "$BACKUP_NAME" \
            --options="compression-level=$COMPRESSION_LEVEL" || {
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
    CRON_JOB="0 2 * * * $PROJECT_DIR/new_daily_update.sh"
    
    # Check if cron job already exists
    EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$PROJECT_DIR/new_daily_update.sh")
    
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

# Make this script executable
chmod +x "$0"
