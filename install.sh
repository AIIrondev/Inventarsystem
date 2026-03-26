#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/Inventarsystem"
REPO_SLUG="AIIrondev/Inventarsystem"
API_URL="https://api.github.com/repos/$REPO_SLUG/releases/latest"
BUNDLE_ASSET="inventarsystem-docker-bundle.tar.gz"

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: missing command: $1"
        exit 1
    fi
}

install_docker_if_missing() {
    if command -v docker >/dev/null 2>&1; then
        return 0
    fi

    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose-v2 curl python3
    sudo systemctl enable --now docker
}

latest_tag_and_bundle_url() {
    local meta_file
    meta_file="$1"

    curl -fsSL "$API_URL" -o "$meta_file"

    python3 - <<'PY' "$meta_file" "$BUNDLE_ASSET"
import json, sys
meta_file, asset_name = sys.argv[1], sys.argv[2]
with open(meta_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
tag = data.get('tag_name', '').strip()
url = ''
for asset in data.get('assets', []):
    if asset.get('name') == asset_name:
        url = asset.get('browser_download_url', '').strip()
        break
print(tag)
print(url)
PY
}

main() {
    install_docker_if_missing
    need_cmd docker
    need_cmd tar
    need_cmd python3
    need_cmd curl

    local tmp_dir meta_file tag bundle_url
    tmp_dir="$(mktemp -d)"
    meta_file="$tmp_dir/release.json"
    trap 'rm -rf "$tmp_dir"' EXIT

    mapfile -t release_info < <(latest_tag_and_bundle_url "$meta_file")
    tag="${release_info[0]:-}"
    bundle_url="${release_info[1]:-}"

    if [ -z "$tag" ] || [ -z "$bundle_url" ]; then
        echo "Error: latest release metadata is incomplete."
        echo "Expected release asset: $BUNDLE_ASSET"
        exit 1
    fi

    echo "Installing Inventarsystem release $tag into $PROJECT_DIR"
    sudo mkdir -p "$PROJECT_DIR"

    curl -fL "$bundle_url" -o "$tmp_dir/$BUNDLE_ASSET"
    sudo tar -xzf "$tmp_dir/$BUNDLE_ASSET" -C "$PROJECT_DIR"

    if [ ! -f "$PROJECT_DIR/start.sh" ]; then
        echo "Error: release bundle is missing start.sh"
        exit 1
    fi
    if [ ! -f "$PROJECT_DIR/stop.sh" ]; then
        echo "Error: release bundle is missing stop.sh"
        exit 1
    fi
    if [ ! -f "$PROJECT_DIR/restart.sh" ]; then
        cat > "$tmp_dir/restart.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/stop.sh"
"$SCRIPT_DIR/start.sh"
EOF
        sudo install -m 755 "$tmp_dir/restart.sh" "$PROJECT_DIR/restart.sh"
    fi

    sudo chmod +x "$PROJECT_DIR/start.sh" "$PROJECT_DIR/stop.sh" "$PROJECT_DIR/restart.sh"

    echo "$tag" | sudo tee "$PROJECT_DIR/.release-version" >/dev/null

    echo "Starting stack..."
    sudo bash "$PROJECT_DIR/start.sh"

    echo "Installation complete."
    echo "Open: https://localhost"
}

main "$@"
