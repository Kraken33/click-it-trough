#!/usr/bin/env bash
# ==============================================================================
# USB Port Forwarding Tunnel for WebDriverAgent (Port 8100)
# Supports both modern iOS 17/18+ CoreDevice IPv6 tunnels and legacy usbmux
# ==============================================================================

set -euo pipefail

PORT="${1:-8100}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$DIR/.venv/bin/python3" ]; then
    exec "$DIR/.venv/bin/python3" "$DIR/scripts/start_tunnel.py" "$PORT"
elif command -v python3 &>/dev/null; then
    exec python3 "$DIR/scripts/start_tunnel.py" "$PORT"
else
    echo "❌ Error: Python 3 not found in .venv."
    exit 1
fi
