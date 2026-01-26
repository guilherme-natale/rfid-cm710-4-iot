#!/bin/bash

echo "=========================================="
echo "  RFID System - Quick Setup"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}Warning: Not running on Raspberry Pi${NC}"
fi

echo "Step 1: Creating directories..."
mkdir -p /home/cpcon/cm710-4
echo -e "${GREEN}✓ Directories created${NC}"

echo ""
echo "Step 2: Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    echo -e "${GREEN}✓ Docker installed${NC}"
else
    echo -e "${GREEN}✓ Docker found${NC}"
fi

echo ""
echo "Step 3: Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    echo "Installing Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose
    echo -e "${GREEN}✓ Docker Compose installed${NC}"
else
    echo -e "${GREEN}✓ Docker Compose found${NC}"
fi

echo ""
echo "Step 4: Installing Python dependencies..."
pip3 install RPi.GPIO pyserial pymongo pika python-dotenv --user
echo -e "${GREEN}✓ Python dependencies installed${NC}"

echo ""
echo "Step 5: Starting Docker services..."
cd /app/docker
docker-compose up -d

# Wait for services
echo "Waiting for services to start..."
sleep 10

echo ""
echo "Step 6: Checking service status..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=========================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Start RFID reader: python3 /app/rfid_scripts/rfid_reader.py"
echo "2. Access RabbitMQ: http://$(hostname -I | awk '{print $1}'):15672"
echo "   User: rfid_user / Pass: rfid_password"
echo "3. Access Web Interface: http://$(hostname -I | awk '{print $1}'):3000"
echo ""
echo "Logs:"
echo "  - Producer: docker logs -f rfid_producer"
echo "  - RabbitMQ: docker logs -f rfid_rabbitmq"
echo ""
