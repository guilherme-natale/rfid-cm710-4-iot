#!/bin/bash
# ============================================================
# RFID Device Bootstrap Script
# Run this ONCE during initial device setup
# NO .env files - only device_id stored locally
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
echo "  RFID Device Bootstrap"
echo "  Zero-Config Local Setup"
echo "============================================================"
echo -e "${NC}"

# ============================================================
# CONFIGURATION - SET BEFORE RUNNING
# ============================================================
CLOUD_URL="${RFID_CLOUD_URL:-}"
ADMIN_API_KEY="${RFID_ADMIN_KEY:-}"
DEVICE_NAME="${DEVICE_NAME:-}"
DEVICE_LOCATION="${DEVICE_LOCATION:-}"

# ============================================================
# FUNCTIONS
# ============================================================

get_mac_address() {
    for iface in eth0 wlan0 enp0s3; do
        if [ -f "/sys/class/net/$iface/address" ]; then
            cat "/sys/class/net/$iface/address" | tr '[:lower:]' '[:upper:]'
            return
        fi
    done
    # Fallback
    ip link | grep 'link/ether' | head -1 | awk '{print $2}' | tr '[:lower:]' '[:upper:]'
}

check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"
    
    local missing=()
    
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v jq >/dev/null 2>&1 || missing+=("jq")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Missing dependencies: ${missing[*]}${NC}"
        echo "Installing..."
        sudo apt-get update
        sudo apt-get install -y "${missing[@]}"
    fi
    
    echo -e "${GREEN}✅ Dependencies OK${NC}"
}

install_python_deps() {
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    
    pip3 install --user requests pika PyJWT >/dev/null 2>&1 || \
    pip3 install requests pika PyJWT >/dev/null 2>&1
    
    echo -e "${GREEN}✅ Python dependencies installed${NC}"
}

create_directories() {
    echo -e "${YELLOW}Creating directories...${NC}"
    
    sudo mkdir -p /etc/rfid
    sudo mkdir -p /var/cache/rfid
    sudo mkdir -p /var/log/rfid
    
    sudo chown -R $USER:$USER /var/cache/rfid
    sudo chown -R $USER:$USER /var/log/rfid
    
    echo -e "${GREEN}✅ Directories created${NC}"
}

prompt_config() {
    echo ""
    
    if [ -z "$CLOUD_URL" ]; then
        echo -e "${YELLOW}Enter Cloud API URL (e.g., https://rfid.example.com):${NC}"
        read -p "> " CLOUD_URL
    fi
    
    if [ -z "$ADMIN_API_KEY" ]; then
        echo -e "${YELLOW}Enter Admin API Key:${NC}"
        read -s -p "> " ADMIN_API_KEY
        echo ""
    fi
    
    if [ -z "$DEVICE_NAME" ]; then
        echo -e "${YELLOW}Enter Device Name (optional, press Enter to skip):${NC}"
        read -p "> " DEVICE_NAME
    fi
    
    if [ -z "$DEVICE_LOCATION" ]; then
        echo -e "${YELLOW}Enter Device Location (optional, press Enter to skip):${NC}"
        read -p "> " DEVICE_LOCATION
    fi
}

register_device() {
    echo ""
    echo -e "${YELLOW}Registering device with cloud...${NC}"
    
    MAC_ADDRESS=$(get_mac_address)
    echo "   MAC Address: $MAC_ADDRESS"
    
    # Build request body
    local body="{\"mac_address\": \"$MAC_ADDRESS\""
    [ -n "$DEVICE_NAME" ] && body="$body, \"device_name\": \"$DEVICE_NAME\""
    [ -n "$DEVICE_LOCATION" ] && body="$body, \"location\": \"$DEVICE_LOCATION\""
    body="$body}"
    
    # Register with cloud
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "${CLOUD_URL}/api/admin/devices/register" \
        -H "Content-Type: application/json" \
        -H "X-Admin-API-Key: $ADMIN_API_KEY" \
        -d "$body")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        DEVICE_ID=$(echo "$BODY" | jq -r '.device_id')
        
        if [ -n "$DEVICE_ID" ] && [ "$DEVICE_ID" != "null" ]; then
            echo -e "${GREEN}✅ Device registered!${NC}"
            echo "   Device ID: $DEVICE_ID"
            return 0
        fi
    elif [ "$HTTP_CODE" = "400" ]; then
        # Device already registered - get existing ID
        echo -e "${YELLOW}Device already registered, fetching existing ID...${NC}"
        
        # Generate device_id locally (same algorithm as cloud)
        DEVICE_ID=$(echo -n "rfid-device-$MAC_ADDRESS" | sha256sum | cut -c1-16)
        echo "   Device ID: $DEVICE_ID"
        return 0
    fi
    
    echo -e "${RED}❌ Registration failed: $HTTP_CODE${NC}"
    echo "$BODY"
    return 1
}

save_device_config() {
    echo ""
    echo -e "${YELLOW}Saving device configuration...${NC}"
    
    # Save device ID (ONLY thing stored locally)
    echo "$DEVICE_ID" | sudo tee /etc/rfid/device_id > /dev/null
    sudo chmod 600 /etc/rfid/device_id
    
    # Save cloud URL
    echo "$CLOUD_URL" | sudo tee /etc/rfid/cloud_url > /dev/null
    sudo chmod 644 /etc/rfid/cloud_url
    
    echo -e "${GREEN}✅ Configuration saved${NC}"
    echo "   /etc/rfid/device_id"
    echo "   /etc/rfid/cloud_url"
}

verify_authentication() {
    echo ""
    echo -e "${YELLOW}Verifying authentication...${NC}"
    
    MAC_ADDRESS=$(get_mac_address)
    
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "${CLOUD_URL}/api/devices/authenticate" \
        -H "Content-Type: application/json" \
        -d "{\"device_id\": \"$DEVICE_ID\", \"mac_address\": \"$MAC_ADDRESS\"}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Authentication successful!${NC}"
        
        # Verify config fetch
        TOKEN=$(echo "$BODY" | jq -r '.access_token')
        
        CONFIG_RESPONSE=$(curl -s -w "\n%{http_code}" \
            -X GET "${CLOUD_URL}/api/config" \
            -H "Authorization: Bearer $TOKEN")
        
        CONFIG_CODE=$(echo "$CONFIG_RESPONSE" | tail -1)
        
        if [ "$CONFIG_CODE" = "200" ]; then
            echo -e "${GREEN}✅ Configuration fetch successful!${NC}"
            return 0
        fi
    fi
    
    echo -e "${RED}❌ Authentication verification failed${NC}"
    return 1
}

install_systemd_service() {
    echo ""
    echo -e "${YELLOW}Installing systemd service...${NC}"
    
    # Get the script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    AGENT_PATH="$(dirname "$SCRIPT_DIR")/agent/device_agent.py"
    
    # Create service file
    sudo tee /etc/systemd/system/rfid-agent.service > /dev/null << EOF
[Unit]
Description=RFID Device Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Environment=RFID_CLOUD_URL=$CLOUD_URL
ExecStart=/usr/bin/python3 $AGENT_PATH
Restart=always
RestartSec=10
StandardOutput=append:/var/log/rfid/agent.log
StandardError=append:/var/log/rfid/agent-error.log

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/cache/rfid /var/log/rfid

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable rfid-agent
    
    echo -e "${GREEN}✅ Service installed${NC}"
}

print_summary() {
    echo ""
    echo -e "${GREEN}"
    echo "============================================================"
    echo "  BOOTSTRAP COMPLETE!"
    echo "============================================================"
    echo -e "${NC}"
    echo ""
    echo -e "${BLUE}Device Information:${NC}"
    echo "   Device ID:    $DEVICE_ID"
    echo "   MAC Address:  $(get_mac_address)"
    echo "   Cloud URL:    $CLOUD_URL"
    echo ""
    echo -e "${BLUE}Files Created:${NC}"
    echo "   /etc/rfid/device_id    - Unique device identifier"
    echo "   /etc/rfid/cloud_url    - Cloud API URL"
    echo ""
    echo -e "${BLUE}NO .env FILES - All config from cloud!${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "   1. Start the agent:"
    echo "      sudo systemctl start rfid-agent"
    echo ""
    echo "   2. Check status:"
    echo "      sudo systemctl status rfid-agent"
    echo ""
    echo "   3. View logs:"
    echo "      tail -f /var/log/rfid/agent.log"
    echo ""
    echo -e "${GREEN}The device will automatically:${NC}"
    echo "   • Authenticate with cloud on startup"
    echo "   • Fetch configuration from cloud"
    echo "   • Reconnect if cloud is temporarily unavailable"
    echo "   • Cache readings when offline"
    echo "   • Sync cached data when back online"
    echo ""
}

# ============================================================
# MAIN
# ============================================================

main() {
    check_dependencies
    install_python_deps
    create_directories
    prompt_config
    
    if ! register_device; then
        echo -e "${RED}Bootstrap failed at registration${NC}"
        exit 1
    fi
    
    save_device_config
    
    if ! verify_authentication; then
        echo -e "${YELLOW}Warning: Authentication verification failed${NC}"
        echo "The device may not be properly configured in the cloud"
    fi
    
    install_systemd_service
    print_summary
}

main "$@"
