#!/bin/bash
# ============================================================
# RFID Agent Start Script
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(dirname "$SCRIPT_DIR")/agent"

# Check if device is bootstrapped
if [ ! -f /etc/rfid/device_id ]; then
    echo "❌ Device not bootstrapped!"
    echo "   Run: /opt/rfid/scripts/bootstrap.sh"
    exit 1
fi

# Load cloud URL
if [ -f /etc/rfid/cloud_url ]; then
    export RFID_CLOUD_URL=$(cat /etc/rfid/cloud_url)
fi

echo "🚀 Starting RFID Agent..."
echo "   Device ID: $(cat /etc/rfid/device_id)"
echo "   Cloud URL: $RFID_CLOUD_URL"
echo ""

# Activate virtual environment if exists
if [ -f /home/$USER/.rfid-venv/bin/activate ]; then
    source /home/$USER/.rfid-venv/bin/activate
fi

# Run agent
python3 "$AGENT_DIR/device_agent.py"
