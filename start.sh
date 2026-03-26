#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.docker-build.env"

SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

NUITKA_BUILD_VALUE="0"
HTTP_PORT_VALUE="80"
HTTPS_PORT_VALUE="443"

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

    if ! command -v crontab >/dev/null 2>&1; then
        missing+=(cron)
    fi

    if [ "${#missing[@]}" -gt 0 ]; then
        echo "Installing missing dependencies: ${missing[*]}"
        apt_install "${missing[@]}"
    fi

    if command -v systemctl >/dev/null 2>&1; then
        $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
        $SUDO systemctl enable --now cron >/dev/null 2>&1 || true
    fi
}

setup_scheduled_jobs() {
    if ! command -v crontab >/dev/null 2>&1; then
        echo "Warning: crontab not available, skipping nightly update setup"
        return 0
    fi

    local update_line backup_line
    update_line="0 3 * * * cd $SCRIPT_DIR && ./update.sh >> $SCRIPT_DIR/logs/update.log 2>&1"
    backup_line="30 2 * * * cd $SCRIPT_DIR && ./backup-docker.sh >> $SCRIPT_DIR/logs/backup.log 2>&1"

    if [ "$(id -u)" -eq 0 ]; then
        (crontab -l 2>/dev/null | grep -vF "$SCRIPT_DIR/update.sh" | grep -vF "$SCRIPT_DIR/backup-docker.sh"; echo "$backup_line"; echo "$update_line") | crontab -
    else
        ($SUDO crontab -l 2>/dev/null | grep -vF "$SCRIPT_DIR/update.sh" | grep -vF "$SCRIPT_DIR/backup-docker.sh"; echo "$backup_line"; echo "$update_line") | $SUDO crontab -
    fi

    echo "Nightly backup scheduled at 02:30"
    echo "Nightly auto-update scheduled at 03:00"
}

ensure_tls_certificates() {
    local cert_dir cert_path key_path cn
    cert_dir="$SCRIPT_DIR/certs"
    cert_path="$cert_dir/inventarsystem.crt"
    key_path="$cert_dir/inventarsystem.key"

    mkdir -p "$cert_dir"

    if [ -f "$cert_path" ] && [ -f "$key_path" ]; then
        return 0
    fi

    cn="${TLS_CN:-localhost}"
    echo "No TLS certificates found. Generating self-signed certificate for CN=$cn"

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$key_path" \
        -out "$cert_path" \
        -subj "/C=DE/ST=NA/L=NA/O=Inventarsystem/OU=IT/CN=$cn" >/dev/null 2>&1

    chmod 600 "$key_path"
    chmod 644 "$cert_path"
}

configure_nuitka_mode() {
    local nuitka_mode

    if [ "${NUITKA_SERVICE:-false}" = "true" ]; then
        nuitka_mode="1"
    else
        nuitka_mode="0"
    fi

    if [ -f "$ENV_FILE" ] && [ -z "${NUITKA_SERVICE+x}" ]; then
        nuitka_mode="$(awk -F= '/^NUITKA_BUILD=/{print $2}' "$ENV_FILE" | tr -d ' ' || true)"
        if [ -z "$nuitka_mode" ]; then
            nuitka_mode="0"
        fi
    fi

    NUITKA_BUILD_VALUE="$nuitka_mode"

    if [ "$nuitka_mode" = "1" ]; then
        echo "Nuitka service mode: enabled (compiled app module)"
    else
        echo "Nuitka service mode: disabled (standard Python app module)"
    fi
}

port_in_use() {
    local port="$1"

    if ! command -v ss >/dev/null 2>&1; then
        return 1
    fi

    ss -ltn "( sport = :$port )" 2>/dev/null | awk 'NR>1 {print $4}' | grep -q .
}

find_free_port() {
    local port="$1"
    while port_in_use "$port"; do
        port=$((port + 1))
    done
    echo "$port"
}

stop_host_nginx_services() {
    local stopped_any=false
    local service_name

    if ! command -v systemctl >/dev/null 2>&1; then
        return 1
    fi

    while IFS= read -r service_name; do
        [ -z "$service_name" ] && continue
        echo "Stopping host service $service_name to free web ports..."
        $SUDO systemctl stop "$service_name" >/dev/null 2>&1 || true
        stopped_any=true
    done < <(systemctl list-units --type=service --state=active --no-pager 2>/dev/null | awk '{print $1}' | grep -E '(^nginx\.service$|nginx)' || true)

    if [ "$stopped_any" = true ]; then
        sleep 2
    fi

    # Some systems run nginx directly (not via systemd unit).
    if pgrep -x nginx >/dev/null 2>&1; then
        echo "Stopping unmanaged host nginx process to free web ports..."
        $SUDO nginx -s quit >/dev/null 2>&1 || true
        sleep 1
        if pgrep -x nginx >/dev/null 2>&1; then
            $SUDO pkill -x nginx >/dev/null 2>&1 || true
            sleep 1
        fi
        stopped_any=true
    fi

    if [ "$stopped_any" = true ]; then
        return 0
    fi

    return 1
}

configure_host_ports() {
    local requested_http requested_https

    requested_http=""
    if [ -f "$ENV_FILE" ]; then
        requested_http="$(awk -F= '/^INVENTAR_HTTP_PORT=/{print $2}' "$ENV_FILE" | tr -d ' ' || true)"
    fi
    if [ -z "$requested_http" ]; then
        requested_http="80"
    fi

    requested_https=""
    if [ -f "$ENV_FILE" ]; then
        requested_https="$(awk -F= '/^INVENTAR_HTTPS_PORT=/{print $2}' "$ENV_FILE" | tr -d ' ' || true)"
    fi

    if [ -z "$requested_https" ]; then
        requested_https="443"
    fi

    if port_in_use "$requested_http"; then
        stop_host_nginx_services || true

        if ! port_in_use "$requested_http"; then
            HTTP_PORT_VALUE="$requested_http"
            echo "Freed HTTP port $requested_http by stopping host nginx service"
        else
            HTTP_PORT_VALUE="$(find_free_port 8080)"
            echo "HTTP port 80 is in use. Using fallback HTTP port: $HTTP_PORT_VALUE"
        fi
    else
        HTTP_PORT_VALUE="$requested_http"
    fi

    if port_in_use "$requested_https"; then
        stop_host_nginx_services || true

        if ! port_in_use "$requested_https"; then
            HTTPS_PORT_VALUE="$requested_https"
            echo "Freed HTTPS port $requested_https by stopping host nginx service"
            return
        fi

        HTTPS_PORT_VALUE="$(find_free_port 8443)"
        echo "HTTPS port 443 is in use. Using fallback HTTPS port: $HTTPS_PORT_VALUE"
    else
        HTTPS_PORT_VALUE="$requested_https"
    fi
}

write_env_file() {
    cat > "$ENV_FILE" <<EOF
NUITKA_BUILD=$NUITKA_BUILD_VALUE
INVENTAR_HTTP_PORT=$HTTP_PORT_VALUE
INVENTAR_HTTPS_PORT=$HTTPS_PORT_VALUE
EOF
}

ensure_runtime_dependencies
ensure_tls_certificates
setup_scheduled_jobs
configure_nuitka_mode
configure_host_ports
write_env_file

echo "Starting Inventarsystem Docker stack (app + mongodb)..."
docker compose --env-file "$ENV_FILE" up -d --build

echo "Stack started."
echo "Open: https://<server-ip>:$HTTPS_PORT_VALUE"
