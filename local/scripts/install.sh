#!/bin/bash
# ============================================================
# RFID Local System Installation Script
# For Raspberry Pi / Debian-based systems
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================================"
echo "  RFID Local System - Installation"
echo "  For Raspberry Pi / Debian-based systems"
echo "============================================================"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run as root. Run as normal user with sudo access.${NC}"
    exit 1
fi

# ============================================================
# SYSTEM REQUIREMENTS
# ============================================================

echo -e "${YELLOW}[1/6] Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

echo -e "${YELLOW}[2/6] Installing system dependencies...${NC}"
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    jq \
    build-essential \
    libssl-dev \
    libffi-dev

# ============================================================
# PYTHON DEPENDENCIES
# ============================================================

echo -e "${YELLOW}[3/6] Installing Python dependencies...${NC}"

# Create virtual environment
python3 -m venv /home/$USER/.rfid-venv

# Activate and install
source /home/$USER/.rfid-venv/bin/activate
pip install --upgrade pip
pip install \
    requests \
    pika \
    PyJWT \
    pyserial \
    RPi.GPIO 2>/dev/null || pip install \
    requests \
    pika \
    PyJWT \
    pyserial

deactivate

echo -e "${GREEN}✅ Python environment ready${NC}"

# ============================================================
# DIRECTORIES
# ============================================================

echo -e "${YELLOW}[4/6] Creating directories...${NC}"

sudo mkdir -p /etc/rfid
sudo mkdir -p /var/cache/rfid
sudo mkdir -p /var/log/rfid
sudo mkdir -p /opt/rfid/scripts
sudo mkdir -p /opt/rfid/agent

sudo chown -R $USER:$USER /var/cache/rfid
sudo chown -R $USER:$USER /var/log/rfid
sudo chown -R $USER:$USER /opt/rfid

echo -e "${GREEN}✅ Directories created${NC}"

# ============================================================
# USER PERMISSIONS
# ============================================================

echo -e "${YELLOW}[5/6] Setting up user permissions...${NC}"

# Add user to required groups
sudo usermod -aG dialout $USER 2>/dev/null || true
sudo usermod -aG gpio $USER 2>/dev/null || true

echo -e "${GREEN}✅ User permissions configured${NC}"

# ============================================================
# COPY FILES
# ============================================================

echo -e "${YELLOW}[6/6] Installing RFID agent files...${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$(dirname "$SCRIPT_DIR")"

# Copy agent
cp "$LOCAL_DIR/agent/device_agent.py" /opt/rfid/agent/

# Copy scripts
cp "$LOCAL_DIR/scripts/bootstrap.sh" /opt/rfid/scripts/
cp "$LOCAL_DIR/scripts/start.sh" /opt/rfid/scripts/ 2>/dev/null || true

chmod +x /opt/rfid/scripts/*.sh

echo -e "${GREEN}✅ Files installed${NC}"

# ============================================================
# SUMMARY
# ============================================================

echo ""
echo -e "${GREEN}"
echo "============================================================"
echo "  INSTALLATION COMPLETE!"
echo "============================================================"
echo -e "${NC}"
echo ""
echo -e "${BLUE}Installed Components:${NC}"
echo "   • Python 3 with virtual environment"
echo "   • RFID Agent in /opt/rfid/agent/"
echo "   • Scripts in /opt/rfid/scripts/"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "   1. Run the bootstrap script:"
echo "      /opt/rfid/scripts/bootstrap.sh"
echo ""
echo "   2. Provide when prompted:"
echo "      • Cloud API URL"
echo "      • Admin API Key"
echo "      • Device name (optional)"
echo "      • Location (optional)"
echo ""
echo -e "${BLUE}NO .env FILES REQUIRED!${NC}"
echo "All configuration will be fetched from the cloud."
echo ""
