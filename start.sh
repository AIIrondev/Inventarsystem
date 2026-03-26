#!/usr/bin/env bash
set -euo pipefail

# Copyright 2025-2026 Maximilian Gruendinger

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/start-docker.sh"
