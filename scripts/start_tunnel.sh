#!/usr/bin/env bash
# ==============================================================================
# USB Port Forwarding Tunnel for WebDriverAgent (Port 8100)
# Uses pymobiledevice3 (in venv) or iproxy if available
# ==============================================================================

set -euo pipefail

PORT=8100
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔌 Initializing USB Port Forwarding on port $PORT..."

if command -v iproxy &>/dev/null; then
    echo "Using iproxy for port $PORT..."
    exec iproxy "$PORT" "$PORT"
elif [ -f "$DIR/.venv/bin/pymobiledevice3" ]; then
    echo "Using pymobiledevice3 usbmux forward $PORT $PORT..."
    exec "$DIR/.venv/bin/pymobiledevice3" usbmux forward "$PORT" "$PORT"
else
    echo "❌ Error: Neither iproxy nor pymobiledevice3 found."
    echo "Please activate .venv (source .venv/bin/activate) or install libimobiledevice."
    exit 1
fi
