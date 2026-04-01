#!/usr/bin/env bash
set -euo pipefail

# Release-only updater for Docker deployment.
# Updates are pulled exclusively from GitHub Releases assets.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/update.log"
STATE_FILE="$PROJECT_DIR/.release-version"
REPO_SLUG="AIIrondev/Inventarsystem"
API_URL="https://api.github.com/repos/$REPO_SLUG/releases/latest"
BUNDLE_ASSET="inventarsystem-docker-bundle.tar.gz"
ENV_FILE="$PROJECT_DIR/.docker-build.env"
APP_IMAGE_REPO="ghcr.io/aiirondev/inventarsystem"

mkdir -p "$LOG_DIR"
chmod 777 "$LOG_DIR" 2>/dev/null || true

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log_message "ERROR: Required command not found: $1"
        exit 1
    fi
}

SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

apt_install() {
    $SUDO apt-get update -y
    $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

ensure_runtime_dependencies() {
    local missing=()

    if ! command -v docker >/dev/null 2>&1; then
        missing+=(docker.io)
    fi

    if ! docker compose version >/dev/null 2>&1; then
        missing+=(docker-compose-v2)
    fi

    if ! command -v openssl >/dev/null 2>&1; then
        missing+=(openssl)
    fi

    if ! command -v curl >/dev/null 2>&1; then
        missing+=(curl)
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        missing+=(python3)
    fi

    if [ "${#missing[@]}" -gt 0 ]; then
        log_message "Installing missing dependencies: ${missing[*]}"
        apt_install "${missing[@]}"
    fi

    if command -v systemctl >/dev/null 2>&1; then
        $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
    fi
}

ensure_tls_certificates() {
    local cert_dir cert_path key_path cn
    cert_dir="$PROJECT_DIR/certs"
    cert_path="$cert_dir/inventarsystem.crt"
    key_path="$cert_dir/inventarsystem.key"

    mkdir -p "$cert_dir"

    if [ -f "$cert_path" ] && [ -f "$key_path" ]; then
        return 0
    fi

    cn="${TLS_CN:-localhost}"
    log_message "No TLS certificates found. Generating self-signed certificate for CN=$cn"

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$key_path" \
        -out "$cert_path" \
        -subj "/C=DE/ST=NA/L=NA/O=Inventarsystem/OU=IT/CN=$cn" >/dev/null 2>&1

    chmod 600 "$key_path"
    chmod 644 "$cert_path"
}

create_backup() {
    log_message "Creating database backup before update..."
    if [ -x "$PROJECT_DIR/backup-docker.sh" ]; then
        if "$PROJECT_DIR/backup-docker.sh" >> "$LOG_FILE" 2>&1; then
            log_message "Docker backup completed"
            return 0
        else
            log_message "WARNING: Docker backup failed; trying legacy backup path"
        fi
    fi

    if [ -x "$PROJECT_DIR/run-backup.sh" ]; then
        if "$PROJECT_DIR/run-backup.sh" >> "$LOG_FILE" 2>&1; then
            log_message "Backup completed"
        else
            log_message "WARNING: Backup failed; continuing with release update"
        fi
    else
        log_message "WARNING: run-backup.sh not found; skipping backup"
    fi
}

fetch_release_metadata() {
    local meta_file
    meta_file="$1"
    curl -fsSL "$API_URL" -o "$meta_file"
}

parse_latest_tag() {
    local meta_file
    meta_file="$1"
    python3 - <<'PY' "$meta_file"
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('tag_name', '').strip())
PY
}

parse_asset_url() {
    local meta_file asset_name
    meta_file="$1"
    asset_name="$2"
    python3 - <<'PY' "$meta_file" "$asset_name"
import json, sys
meta_file, asset_name = sys.argv[1], sys.argv[2]
with open(meta_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
for asset in data.get('assets', []):
    if asset.get('name') == asset_name:
        print(asset.get('browser_download_url', '').strip())
        break
PY
}

download_and_extract_bundle() {
    local url tmp_dir archive
    url="$1"
    tmp_dir="$2"
    archive="$tmp_dir/$BUNDLE_ASSET"

    curl -fL "$url" -o "$archive"
    tar -xzf "$archive" -C "$tmp_dir"

    # The bundle must contain docker deployment files only.
    mkdir -p "$PROJECT_DIR/docker/nginx"
    cp -f "$tmp_dir/docker-compose.yml" "$PROJECT_DIR/docker-compose.yml"
    cp -f "$tmp_dir/docker/nginx/default.conf" "$PROJECT_DIR/docker/nginx/default.conf"
    cp -f "$tmp_dir/start.sh" "$PROJECT_DIR/start.sh"
    cp -f "$tmp_dir/stop.sh" "$PROJECT_DIR/stop.sh"

    if [ -f "$tmp_dir/restart.sh" ]; then
        cp -f "$tmp_dir/restart.sh" "$PROJECT_DIR/restart.sh"
    fi

    if [ -f "$tmp_dir/backup-docker.sh" ]; then
        cp -f "$tmp_dir/backup-docker.sh" "$PROJECT_DIR/backup-docker.sh"
    fi
    if [ -f "$tmp_dir/update.sh" ]; then
        cp -f "$tmp_dir/update.sh" "$PROJECT_DIR/update.sh"
    fi

    chmod +x "$PROJECT_DIR/start.sh" "$PROJECT_DIR/stop.sh" "$PROJECT_DIR/restart.sh" "$PROJECT_DIR/backup-docker.sh" "$PROJECT_DIR/update.sh"
}

deploy() {
    local tag="$1"
    local app_image="${APP_IMAGE_REPO}:${tag}"

    cd "$PROJECT_DIR"
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" <<EOF
NUITKA_BUILD=0
INVENTAR_HTTP_PORT=80
INVENTAR_HTTPS_PORT=443
INVENTAR_APP_IMAGE=$app_image
EOF
    elif grep -q '^INVENTAR_APP_IMAGE=' "$ENV_FILE"; then
        sed -i "s|^INVENTAR_APP_IMAGE=.*|INVENTAR_APP_IMAGE=$app_image|" "$ENV_FILE"
    else
        printf '\nINVENTAR_APP_IMAGE=%s\n' "$app_image" >> "$ENV_FILE"
    fi

    docker compose --env-file "$ENV_FILE" pull app nginx mongodb >> "$LOG_FILE" 2>&1
    docker compose --env-file "$ENV_FILE" up -d --remove-orphans >> "$LOG_FILE" 2>&1
}

verify_stack_health() {
    local compose_args running_services
    local https_port
    compose_args=(--env-file "$ENV_FILE")
    https_port="$(awk -F= '/^INVENTAR_HTTPS_PORT=/{print $2}' "$ENV_FILE" | tr -d ' ')"
    if [ -z "$https_port" ]; then
        https_port="443"
    fi

    for _ in $(seq 1 60); do
        running_services="$(docker compose "${compose_args[@]}" ps --status running --services 2>/dev/null || true)"
        if printf '%s\n' "$running_services" | grep -Fxq app && \
           printf '%s\n' "$running_services" | grep -Fxq nginx && \
           printf '%s\n' "$running_services" | grep -Fxq mongodb; then
            if docker compose "${compose_args[@]}" exec -T app python3 -c "import flask_jwt_extended, pymongo" >/dev/null 2>&1; then
                if curl -kfsS "https://127.0.0.1:$https_port" >/dev/null 2>&1; then
                    return 0
                fi
            fi
        fi
        sleep 2
    done

    docker compose "${compose_args[@]}" ps >> "$LOG_FILE" 2>&1 || true
    docker compose "${compose_args[@]}" logs --tail=120 app nginx mongodb >> "$LOG_FILE" 2>&1 || true
    return 1
}

main() {
    ensure_runtime_dependencies
    ensure_tls_certificates

    require_cmd curl
    require_cmd tar
    require_cmd docker
    require_cmd python3

    create_backup

    local tmp_dir meta_file latest_tag current_tag bundle_url
    tmp_dir="$(mktemp -d)"
    meta_file="$tmp_dir/release.json"

    trap 'rm -rf "$tmp_dir"' EXIT

    log_message "Checking latest GitHub release for $REPO_SLUG..."
    if ! fetch_release_metadata "$meta_file"; then
        log_message "WARNING: Could not fetch release metadata. Falling back to image-only deployment."
        deploy "latest"
        if verify_stack_health; then
            log_message "Fallback deployment completed"
        else
            log_message "ERROR: Fallback deployment failed health check"
            exit 1
        fi
        exit 0
    fi

    latest_tag="$(parse_latest_tag "$meta_file")"
    if [ -z "$latest_tag" ]; then
        log_message "WARNING: Could not determine latest release tag. Falling back to image-only deployment."
        deploy "latest"
        if verify_stack_health; then
            log_message "Fallback deployment completed"
        else
            log_message "ERROR: Fallback deployment failed health check"
            exit 1
        fi
        exit 0
    fi

    current_tag=""
    if [ -f "$STATE_FILE" ]; then
        current_tag="$(cat "$STATE_FILE")"
    fi

    if [ "$current_tag" = "$latest_tag" ]; then
        log_message "Already on latest release ($latest_tag). Refreshing containers from prebuilt image."
        deploy "$latest_tag"
        if verify_stack_health; then
            log_message "Container refresh completed"
        else
            log_message "ERROR: Container refresh failed health check"
            exit 1
        fi
        exit 0
    fi

    bundle_url="$(parse_asset_url "$meta_file" "$BUNDLE_ASSET")"
    if [ -z "$bundle_url" ]; then
        log_message "WARNING: Release asset not found: $BUNDLE_ASSET. Falling back to image-only deployment."
        deploy "$latest_tag"
        if verify_stack_health; then
            log_message "Image-only deployment completed"
        else
            log_message "ERROR: Image-only fallback failed health check"
            exit 1
        fi
        exit 0
    fi

    log_message "Updating from release $latest_tag"
    download_and_extract_bundle "$bundle_url" "$tmp_dir"
    deploy "$latest_tag"
    if ! verify_stack_health; then
        log_message "ERROR: Updated stack failed health check"
        exit 1
    fi

    echo "$latest_tag" > "$STATE_FILE"
    log_message "Update completed successfully to release $latest_tag"
}

main "$@"
