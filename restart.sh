#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

"$SCRIPT_DIR/stop-docker.sh"
"$SCRIPT_DIR/start-docker.sh"