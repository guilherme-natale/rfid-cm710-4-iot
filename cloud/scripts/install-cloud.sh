#!/bin/bash
# ============================================================
# RFID Cloud API - Installation Script
# Run this on your cloud server (Ubuntu 22.04+ recommended)
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
echo "  RFID Cloud API - Installation"
echo "============================================================"
echo -e "${NC}"

# ============================================================
# CONFIGURATION
# ============================================================

INSTALL_DIR="${INSTALL_DIR:-/opt/rfid-cloud}"
MONGO_VERSION="${MONGO_VERSION:-7.0}"
USE_DOCKER="${USE_DOCKER:-true}"

# ============================================================
# PRE-FLIGHT CHECKS
# ============================================================

echo -e "${YELLOW}[1/7] Pre-flight checks...${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

# Check OS
if ! grep -q "Ubuntu\|Debian" /etc/os-release 2>/dev/null; then
    echo -e "${YELLOW}Warning: This script is tested on Ubuntu/Debian${NC}"
fi

echo -e "${GREEN}✅ Pre-flight checks passed${NC}"

# ============================================================
# INSTALL SYSTEM DEPENDENCIES
# ============================================================

echo -e "${YELLOW}[2/7] Installing system dependencies...${NC}"

apt-get update -qq
apt-get install -y -qq \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    python3-venv \
    openssl \
    jq

echo -e "${GREEN}✅ System dependencies installed${NC}"

# ============================================================
# INSTALL DOCKER (if enabled)
# ============================================================

if [ "$USE_DOCKER" = "true" ]; then
    echo -e "${YELLOW}[3/7] Installing Docker...${NC}"
    
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
    fi
    
    # Install docker-compose
    if ! command -v docker-compose &> /dev/null; then
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    
    echo -e "${GREEN}✅ Docker installed${NC}"
else
    echo -e "${YELLOW}[3/7] Skipping Docker (USE_DOCKER=false)${NC}"
fi

# ============================================================
# CREATE INSTALLATION DIRECTORY
# ============================================================

echo -e "${YELLOW}[4/7] Setting up installation directory...${NC}"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Copy source files (assumes script is run from repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/../src" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/../docker" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/../requirements.txt" "$INSTALL_DIR/"

echo -e "${GREEN}✅ Installation directory ready${NC}"

# ============================================================
# GENERATE SECRETS
# ============================================================

echo -e "${YELLOW}[5/7] Generating secure secrets...${NC}"

JWT_SECRET=$(openssl rand -hex 32)
ADMIN_API_KEY=$(openssl rand -hex 32)
RABBITMQ_PASSWORD=$(openssl rand -hex 16)

# Create .env file
cat > "$INSTALL_DIR/.env" << EOF
# RFID Cloud API Configuration
# Generated on $(date -Iseconds)
# ⚠️  DO NOT COMMIT THIS FILE TO VERSION CONTROL

# MongoDB
MONGO_URL=mongodb://mongo:27017
DB_NAME=rfid_cloud

# JWT Security
JWT_SECRET=$JWT_SECRET
JWT_EXPIRATION_HOURS=24

# Admin API Key
ADMIN_API_KEY=$ADMIN_API_KEY

# RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=rfid_user
RABBITMQ_PASSWORD=$RABBITMQ_PASSWORD

# CORS (adjust for production)
CORS_ORIGINS=*
EOF

chmod 600 "$INSTALL_DIR/.env"

echo -e "${GREEN}✅ Secrets generated and saved to .env${NC}"
echo ""
echo -e "${YELLOW}📝 IMPORTANT - Save these credentials:${NC}"
echo -e "   ADMIN_API_KEY: ${BLUE}$ADMIN_API_KEY${NC}"
echo ""

# ============================================================
# SETUP PYTHON ENVIRONMENT (non-Docker)
# ============================================================

if [ "$USE_DOCKER" != "true" ]; then
    echo -e "${YELLOW}[6/7] Setting up Python environment...${NC}"
    
    python3 -m venv "$INSTALL_DIR/venv"
    source "$INSTALL_DIR/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "$INSTALL_DIR/requirements.txt"
    
    # Create systemd service
    cat > /etc/systemd/system/rfid-cloud-api.service << EOF
[Unit]
Description=RFID Cloud API
After=network.target mongodb.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/src/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable rfid-cloud-api
    
    echo -e "${GREEN}✅ Python environment ready${NC}"
else
    echo -e "${YELLOW}[6/7] Skipping Python setup (using Docker)${NC}"
fi

# ============================================================
# START SERVICES
# ============================================================

echo -e "${YELLOW}[7/7] Starting services...${NC}"

if [ "$USE_DOCKER" = "true" ]; then
    cd "$INSTALL_DIR"
    
    # Create docker-compose if not exists
    if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
        cp "$SCRIPT_DIR/../docker/docker-compose.yml" "$INSTALL_DIR/" 2>/dev/null || \
        cat > "$INSTALL_DIR/docker-compose.yml" << 'COMPOSE'
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8001:8001"
    env_file:
      - .env
    depends_on:
      - mongo
      - rabbitmq
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  mongo:
    image: mongo:7
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: rfid_user
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

volumes:
  mongo_data:
  rabbitmq_data:
COMPOSE
    fi
    
    docker-compose up -d
    
    echo -e "${GREEN}✅ Docker services started${NC}"
else
    systemctl start rfid-cloud-api
    echo -e "${GREEN}✅ API service started${NC}"
fi

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
echo -e "${BLUE}Service URLs:${NC}"
echo "   API:        http://localhost:8001"
echo "   Swagger:    http://localhost:8001/docs"
echo "   Health:     http://localhost:8001/health"
if [ "$USE_DOCKER" = "true" ]; then
echo "   RabbitMQ:   http://localhost:15672"
fi
echo ""
echo -e "${BLUE}Credentials:${NC}"
echo "   Admin API Key: $ADMIN_API_KEY"
echo "   Config file:   $INSTALL_DIR/.env"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "   1. Configure firewall (ufw allow 8001)"
echo "   2. Setup HTTPS with nginx/certbot"
echo "   3. Register your first device:"
echo ""
echo -e "${BLUE}   curl -X POST http://localhost:8001/api/admin/devices/register \\${NC}"
echo -e "${BLUE}     -H 'Content-Type: application/json' \\${NC}"
echo -e "${BLUE}     -H 'X-Admin-API-Key: $ADMIN_API_KEY' \\${NC}"
echo -e "${BLUE}     -d '{\"mac_address\": \"AA:BB:CC:DD:EE:FF\", \"device_name\": \"My Device\"}'${NC}"
echo ""
