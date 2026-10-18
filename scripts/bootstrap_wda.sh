#!/usr/bin/env bash
# ==============================================================================
# WebDriverAgent (WDA) Bootstrap & Build Helper
# Sets up and builds WebDriverAgentRunner on connected iPhone using Xcode
# ==============================================================================

set -euo pipefail

WDA_DIR="$(pwd)/WebDriverAgent"
WDA_REPO="https://github.com/appium/WebDriverAgent.git"

echo "=========================================================="
echo "   TikTok Automation - WebDriverAgent (WDA) Bootstrap     "
echo "=========================================================="

# 1. Verify Xcode installation
if ! command -v xcodebuild &>/dev/null; then
    echo "❌ Error: xcodebuild not found. Please install Xcode from the Mac App Store."
    exit 1
fi

XCODE_VER=$(xcodebuild -version | head -n 1)
echo "✅ Found $XCODE_VER"

# 2. Clone WebDriverAgent if not already present
if [ ! -d "$WDA_DIR" ]; then
    echo "📥 Cloning WebDriverAgent repository..."
    git clone --depth 1 "$WDA_REPO" "$WDA_DIR"
else
    echo "📁 Found existing WebDriverAgent directory at $WDA_DIR"
fi

# 3. Detect connected iOS devices
echo "🔍 Searching for connected iOS devices..."
DEVICES=$(xcrun xctrace list devices 2>&1 || true)
echo "$DEVICES"

echo ""
echo "----------------------------------------------------------"
echo "Next Steps to sign & build WebDriverAgent on your iPhone:"
echo "----------------------------------------------------------"
echo "1. Connect your iPhone via USB and unlock it (tap 'Trust this computer')."
echo "2. Open WebDriverAgent in Xcode:"
echo "      open $WDA_DIR/WebDriverAgent.xcodeproj"
echo "3. In Xcode:"
echo "   - Select 'WebDriverAgentRunner' target."
echo "   - Go to 'Signing & Capabilities'."
echo "   - Check 'Automatically manage signing'."
echo "   - Select your Personal Apple ID Team."
echo "   - Ensure Bundle Identifier is unique (e.g. com.yourname.WebDriverAgentRunner)."
echo "4. On your iPhone, ensure Developer Mode is enabled:"
echo "   - Settings -> Privacy & Security -> Developer Mode -> Turn ON (reboot required)."
echo "5. Run the test runner from terminal with your device UDID:"
echo "   xcodebuild -project $WDA_DIR/WebDriverAgent.xcodeproj \\"
echo "              -scheme WebDriverAgentRunner \\"
echo "              -destination 'id=<YOUR_IPHONE_UDID>' \\"
echo "              test"
echo ""
echo "Once WDA starts on the iPhone, run: ./scripts/start_tunnel.sh"
echo "=========================================================="
