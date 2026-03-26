#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
BACKUP_ROOT="$SCRIPT_DIR/backups"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
OUT_DIR="$BACKUP_ROOT/$STAMP"
ARCHIVE="$OUT_DIR/mongodb-${STAMP}.archive.gz"

mkdir -p "$LOG_DIR" "$OUT_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_DIR/backup.log"
}

if ! command -v docker >/dev/null 2>&1; then
    log "ERROR: docker not found"
    exit 1
fi

log "Ensuring mongodb container is running..."
docker compose up -d mongodb >/dev/null 2>&1 || true

if ! docker compose ps --status running mongodb | grep -q mongodb; then
    log "ERROR: mongodb service is not running"
    exit 1
fi

DB_NAME="${INVENTAR_MONGODB_DB:-Inventarsystem}"
log "Creating MongoDB backup for database: $DB_NAME"

if docker compose exec -T mongodb sh -c "mongodump --archive --gzip --db '$DB_NAME'" > "$ARCHIVE"; then
    log "Backup created: $ARCHIVE"
else
    log "ERROR: mongodump failed"
    rm -f "$ARCHIVE"
    exit 1
fi

# Keep last 14 days
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null || true
log "Backup retention cleanup complete"
