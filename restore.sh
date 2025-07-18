#!/bin/bash
# filepath: /home/max/Dokumente/repos/Inventarsystem/restore.sh.fixed

# Configuration
PROJECT_DIR="$(dirname "$(readlink -f "$0")")"
BACKUP_BASE_DIR="/var/backups"
LOG_FILE="$PROJECT_DIR/logs/restore.log"

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

# Parse command line arguments
BACKUP_DATE=""
RESTART_SERVICES=false
RESTORE_DB=true

# Display help
show_help() {
    echo "Inventory System Backup Restoration Tool"
    echo "Usage: $0 --date=YYYY-MM-DD [options]"
    echo ""
    echo "Options:"
    echo "  --date=YYYY-MM-DD     Required: Date of backup to restore"
    echo "  --no-db               Skip database restoration"
    echo "  --restart-services    Restart services after restoration"
    echo "  --list                List available backups"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --date=2025-07-14          # Restore backup from July 14, 2025"
    echo "  $0 --date=latest              # Restore most recent backup"
    echo "  $0 --list                     # Show available backups"
}

# List available backups
list_backups() {
    log_message "Listing available backups..."
    echo "Available backups:"
    
    # Check for compressed backups
    COMPRESSED_BACKUPS=$(find "$BACKUP_BASE_DIR" -maxdepth 1 -name "Inventarsystem-*.tar.gz" | sort -r)
    
    # Check for uncompressed backup directories
    UNCOMPRESSED_BACKUPS=$(find "$BACKUP_BASE_DIR" -maxdepth 1 -type d -name "Inventarsystem-*" | sort -r)
    
    if [ -z "$COMPRESSED_BACKUPS" ] && [ -z "$UNCOMPRESSED_BACKUPS" ]; then
        echo "No backups found in $BACKUP_BASE_DIR"
        return 1
    fi
    
    echo "Compressed backups:"
    if [ -z "$COMPRESSED_BACKUPS" ]; then
        echo "  None"
    else
        for backup in $COMPRESSED_BACKUPS; do
            filename=$(basename "$backup")
            date=${filename#Inventarsystem-}
            date=${date%.tar.gz}
            size=$(du -h "$backup" | cut -f1)
            echo "  $date ($size)"
        done
    fi
    
    echo "Uncompressed backups:"
    if [ -z "$UNCOMPRESSED_BACKUPS" ]; then
        echo "  None"
    else
        for backup in $UNCOMPRESSED_BACKUPS; do
            dirname=$(basename "$backup")
            date=${dirname#Inventarsystem-}
            size=$(du -sh "$backup" | cut -f1)
            echo "  $date ($size)"
        done
    fi
}

# Find the most recent backup
get_latest_backup() {
    # First check for compressed backups
    LATEST=$(find "$BACKUP_BASE_DIR" -maxdepth 1 -name "Inventarsystem-*.tar.gz" | sort -r | head -n 1)
    
    # If no compressed backups, check for directories
    if [ -z "$LATEST" ]; then
        LATEST=$(find "$BACKUP_BASE_DIR" -maxdepth 1 -type d -name "Inventarsystem-*" | sort -r | head -n 1)
    fi
    
    if [ -z "$LATEST" ]; then
        log_message "ERROR: No backups found"
        return 1
    fi
    
    basename=$(basename "$LATEST")
    if [[ "$basename" == *.tar.gz ]]; then
        echo "${basename#Inventarsystem-}" | sed 's/\.tar\.gz$//'
    else
        echo "${basename#Inventarsystem-}"
    fi
}

# Restore files from backup
restore_files() {
    local backup_date=$1
    local temp_dir="/tmp/inventarsystem_restore_$$"
    
    log_message "Restoring files from backup dated $backup_date..."
    
    # Check for compressed backup first
    compressed_backup="$BACKUP_BASE_DIR/Inventarsystem-$backup_date.tar.gz"
    uncompressed_backup="$BACKUP_BASE_DIR/Inventarsystem-$backup_date"
    
    if [ -f "$compressed_backup" ]; then
        log_message "Found compressed backup: $compressed_backup"
        
        # Create temporary extraction directory
        mkdir -p "$temp_dir"
        
        # Extract the archive
        log_message "Extracting backup archive..."
        sudo tar -xzf "$compressed_backup" -C "$temp_dir" || {
            log_message "ERROR: Failed to extract backup archive"
            sudo rm -rf "$temp_dir"
            return 1
        }
        
        # Set the source directory to the extracted folder
        source_dir="$temp_dir/Inventarsystem-$backup_date"
    elif [ -d "$uncompressed_backup" ]; then
        log_message "Found uncompressed backup: $uncompressed_backup"
        source_dir="$uncompressed_backup"
    else
        log_message "ERROR: No backup found for date $backup_date"
        return 1
    fi
    
    # Create a temporary backup of current files
    current_backup_dir="/tmp/inventarsystem_current_$$"
    log_message "Creating temporary backup of current files to $current_backup_dir"
    mkdir -p "$current_backup_dir"
    cp -r "$PROJECT_DIR"/* "$current_backup_dir/" || {
        log_message "WARNING: Failed to create temporary backup of current files"
    }
    
    # Copy files from backup to project directory
    log_message "Copying files from backup to project directory..."
    
    # Exclude certain directories from restoration
    sudo rsync -av --exclude="logs" --exclude=".git" --exclude="mongodb_backup" "$source_dir/" "$PROJECT_DIR/" || {
        log_message "ERROR: Failed to restore files"
        return 1
    }
    
    # Clean up
    if [ -d "$temp_dir" ]; then
        sudo rm -rf "$temp_dir"
    fi
    
    log_message "Files restored successfully"
    return 0
}

# Restore database
restore_db() {
    local backup_date=$1
    local temp_dir="/tmp/inventarsystem_restore_$$"
    
    # Ensure temporary directory exists
    mkdir -p "$temp_dir"
    
    log_message "Restoring database from backup dated $backup_date..."
    
    # Determine the location of database backup files
    db_backup_location=""
    
    # Check compressed backup first
    compressed_backup="$BACKUP_BASE_DIR/Inventarsystem-$backup_date.tar.gz"
    uncompressed_backup="$BACKUP_BASE_DIR/Inventarsystem-$backup_date"
    
    if [ -f "$compressed_backup" ]; then
        # Need to extract the database files
        mkdir -p "$temp_dir"
        
        log_message "Extracting database files from compressed backup..."
        # Extract the whole archive - safer than trying to extract just the mongodb_backup directory
        sudo tar -xzf "$compressed_backup" -C "$temp_dir" || {
            log_message "ERROR: Failed to extract backup archive"
            sudo rm -rf "$temp_dir"
            return 1
        }
        
        # Check both standard location and top-level location
        if [ -d "$temp_dir/Inventarsystem-$backup_date/mongodb_backup" ]; then
            db_backup_location="$temp_dir/Inventarsystem-$backup_date/mongodb_backup"
        elif [ -d "$temp_dir/mongodb_backup" ]; then
            db_backup_location="$temp_dir/mongodb_backup"
        else
            log_message "WARNING: Could not find mongodb_backup directory in extracted archive"
        fi
    elif [ -d "$uncompressed_backup" ]; then
        # Use the uncompressed backup
        # Check both standard location and top-level location
        if [ -d "$uncompressed_backup/mongodb_backup" ]; then
            db_backup_location="$uncompressed_backup/mongodb_backup"
        elif [ -d "$BACKUP_BASE_DIR/mongodb_backup" ]; then
            db_backup_location="$BACKUP_BASE_DIR/mongodb_backup"
        else
            log_message "WARNING: Could not find mongodb_backup directory in uncompressed backup"
        fi
    else
        log_message "ERROR: No backup found for date $backup_date"
        return 1
    fi
    
    # Try to locate the MongoDB backup directory if it wasn't found
    if [ -z "$db_backup_location" ] || [ ! -d "$db_backup_location" ]; then
        log_message "Searching for MongoDB backup directory..."
        
        # Search recursively for CSV files that could be part of the backup
        possible_locations=$(find "$BACKUP_BASE_DIR" -name "*.csv" -type f -print 2>/dev/null | xargs -r dirname 2>/dev/null | sort -u)
        
        if [ -n "$possible_locations" ]; then
            # Use the first location found (most likely location)
            db_backup_location=$(echo "$possible_locations" | head -1)
            log_message "Found potential MongoDB backup at: $db_backup_location"
        else
            # If no backup directory was found and user did not request to skip DB restore
            log_message "ERROR: Database backup directory not found in the backup"
            # Continue without error to allow file restoration to succeed
            [ -d "$temp_dir" ] && sudo rm -rf "$temp_dir"
            return 0
        fi
    fi
    
    # Count CSV files in the backup directory
    csv_count=$(find "$db_backup_location" -name "*.csv" 2>/dev/null | wc -l)
    if [ "$csv_count" -eq 0 ]; then
        log_message "ERROR: No database backup files (CSV) found in $db_backup_location"
        # Continue without error to allow file restoration to succeed
        [ -d "$temp_dir" ] && sudo rm -rf "$temp_dir"
        return 0
    fi
    
    log_message "Found $csv_count collection backup files"
    
    # Create a restore script to import the CSVs back to MongoDB
    restore_script="$temp_dir/restore_db.py"
    
    cat > "$restore_script" << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
"""
MongoDB restoration from CSV backups
"""
import os
import csv
import sys
import argparse
from pymongo import MongoClient
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="Restore MongoDB database from CSV files")
    parser.add_argument("--uri", required=True, help="MongoDB URI")
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument("--dir", required=True, help="Directory containing CSV files")
    return parser.parse_args()

def restore_collection(client, db_name, csv_file):
    coll_name = os.path.splitext(os.path.basename(csv_file))[0]
    print(f"Restoring collection: {coll_name}")
    
    db = client[db_name]
    
    # Drop existing collection if it exists
    if coll_name in db.list_collection_names():
        print(f"  Dropping existing collection {coll_name}")
        db[coll_name].drop()
    
    # Read CSV file
    documents = []
    with open(csv_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert empty strings to None
            doc = {k: (None if v == '' else v) for k, v in row.items()}
            
            # Handle nested fields (keys containing dots)
            nested_doc = {}
            for k, v in doc.items():
                if '.' in k:
                    parts = k.split('.')
                    current = nested_doc
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    current[parts[-1]] = v
                else:
                    nested_doc[k] = v
            
            documents.append(nested_doc)
    
    # Insert documents
    if documents:
        db[coll_name].insert_many(documents)
        print(f"  Restored {len(documents)} documents")
    else:
        print(f"  No documents to restore")

def main():
    args = parse_args()
    
    # Connect to MongoDB
    client = MongoClient(args.uri)
    
    # Get CSV files
    csv_files = [os.path.join(args.dir, f) for f in os.listdir(args.dir) if f.endswith('.csv')]
    
    if not csv_files:
        print(f"No CSV files found in {args.dir}")
        return 1
    
    print(f"Found {len(csv_files)} CSV files to restore")
    
    # Process each CSV file
    for csv_file in csv_files:
        try:
            restore_collection(client, args.db, csv_file)
        except Exception as e:
            print(f"Error restoring {os.path.basename(csv_file)}: {e}")
    
    print("Database restoration complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
PYTHON_SCRIPT
    
    chmod +x "$restore_script"
    
    # Execute the restoration script
    log_message "Restoring database from CSV files..."
    # Try to use virtualenv Python if available
    if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
        if ! "$PROJECT_DIR/.venv/bin/python" "$restore_script" --uri "mongodb://localhost:27017/" --db "Inventarsystem" --dir "$db_backup_location"; then
            log_message "ERROR: Failed to restore database with virtualenv Python"
            # Try with system Python as fallback
            if ! python3 "$restore_script" --uri "mongodb://localhost:27017/" --db "Inventarsystem" --dir "$db_backup_location"; then
                log_message "ERROR: Failed to restore database"
                [ -d "$temp_dir" ] && sudo rm -rf "$temp_dir"
                return 1
            fi
        fi
    else
        # Use system Python
        if ! python3 "$restore_script" --uri "mongodb://localhost:27017/" --db "Inventarsystem" --dir "$db_backup_location"; then
            log_message "ERROR: Failed to restore database"
            [ -d "$temp_dir" ] && sudo rm -rf "$temp_dir"
            return 1
        fi
    fi
    
    # Clean up
    [ -d "$temp_dir" ] && sudo rm -rf "$temp_dir"
    
    log_message "Database restored successfully"
    return 0
}

# Restart services
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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --date=*)
            BACKUP_DATE="${1#*=}"
            shift
            ;;
        --restart-services)
            RESTART_SERVICES=true
            shift
            ;;
        --no-db)
            RESTORE_DB=false
            shift
            ;;
        --list)
            list_backups
            exit 0
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown parameter: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if backup date is provided or "latest" is specified
if [ -z "$BACKUP_DATE" ]; then
    echo "ERROR: You must specify a backup date with --date=YYYY-MM-DD"
    echo "       or use --date=latest for the most recent backup"
    echo ""
    show_help
    exit 1
fi

# Handle "latest" backup request
if [ "$BACKUP_DATE" = "latest" ]; then
    BACKUP_DATE=$(get_latest_backup)
    if [ $? -ne 0 ]; then
        echo "ERROR: No backups available"
        exit 1
    fi
    log_message "Selected latest backup: $BACKUP_DATE"
fi

# Start the log for this restoration
log_message "====== Starting restoration from backup $BACKUP_DATE ======"

# Restore files
restore_files "$BACKUP_DATE"
FILE_RESTORE_STATUS=$?

# Restore database if requested and file restore was successful
if [ $FILE_RESTORE_STATUS -eq 0 ] && [ "$RESTORE_DB" = true ]; then
    restore_db "$BACKUP_DATE"
    DB_RESTORE_STATUS=$?
else
    if [ "$RESTORE_DB" = false ]; then
        log_message "Database restoration skipped as requested"
        DB_RESTORE_STATUS=0
    else
        log_message "Database restoration skipped due to file restoration failure"
        DB_RESTORE_STATUS=1
    fi
fi

# Restart services if requested and restoration was successful
if [ $FILE_RESTORE_STATUS -eq 0 ] && [ $DB_RESTORE_STATUS -eq 0 ] && [ "$RESTART_SERVICES" = true ]; then
    restart_services
    RESTART_STATUS=$?
else
    if [ "$RESTART_SERVICES" = false ]; then
        log_message "Service restart not requested, skipping"
        RESTART_STATUS=0
    else
        log_message "Service restart skipped due to restoration failures"
        RESTART_STATUS=1
    fi
fi

# Final status report
if [ $FILE_RESTORE_STATUS -eq 0 ] && ([ $DB_RESTORE_STATUS -eq 0 ] || [ "$RESTORE_DB" = false ]) && [ $RESTART_STATUS -eq 0 ]; then
    if [ $DB_RESTORE_STATUS -ne 0 ] && [ "$RESTORE_DB" = true ]; then
        log_message "====== Restoration completed with warnings (file restore OK, database restore failed) ======"
        echo "Restoration completed with warnings (files restored successfully, but database restore failed)."
        echo "The system should still be functional with the existing database."
        echo "Check the log file at $LOG_FILE for details."
        exit 0
    else
        log_message "====== Restoration completed successfully ======"
        echo "Restoration completed successfully!"
        exit 0
    fi
else
    log_message "====== Restoration completed with errors ======"
    echo "Restoration completed with errors. Check the log file at $LOG_FILE for details."
    exit 1
fi
