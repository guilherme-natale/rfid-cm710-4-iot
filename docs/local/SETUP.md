# 🏠 Local Device Setup (Raspberry Pi)

## Overview

The local component runs on Raspberry Pi devices and handles:
- RFID tag reading via CM710-4 module
- Authentication with cloud
- Configuration fetching
- Data publishing to cloud
- Offline caching

## ⚠️ Important: NO .env FILES

**The device stores NO secrets locally.**

Only two files are stored:
- `/etc/rfid/device_id` - Unique device identifier
- `/etc/rfid/cloud_url` - Cloud API URL

All sensitive configuration (credentials, passwords) comes from the cloud API.

## Components

### 1. Device Agent (`device_agent.py`)

Main agent that:
- Authenticates with cloud using device_id + MAC
- Fetches configuration from cloud
- Monitors RFID log file
- Publishes readings to RabbitMQ
- Sends heartbeats
- Handles offline mode

### 2. RFID Reader (`rfid_reader.py`)

Hardware interface that:
- Communicates with CM710-4 via USB serial
- Controls GPIO pins (buzzer, enable)
- Writes readings to log file
- Handles signal interrupts

### 3. Systemd Services

| Service | Purpose |
|---------|---------|
| `rfid-reader.service` | Runs RFID hardware reader |
| `rfid-agent.service` | Runs cloud communication agent |

## Installation

### Prerequisites

- Raspberry Pi 4 (recommended)
- Raspberry Pi OS (Bullseye or newer)
- CM710-4 RFID module
- Network connectivity

### Step 1: System Installation

```bash
# Download the project
git clone https://github.com/your-repo/rfid-cm710-4-iot.git
cd rfid-cm710-4-iot

# Run installation script
./local/scripts/install.sh
```

This installs:
- Python 3 and virtual environment
- Required Python packages
- System directories
- User permissions

### Step 2: Bootstrap Device

```bash
# Set cloud URL and admin key
export RFID_CLOUD_URL="https://your-cloud-server.com"
export RFID_ADMIN_KEY="your-admin-api-key"

# Run bootstrap
./local/scripts/bootstrap.sh
```

The bootstrap script:
1. Registers device with cloud (gets device_id)
2. Saves device_id locally
3. Verifies authentication works
4. Installs systemd service

### Step 3: Start Services

```bash
# Start the agent
sudo systemctl start rfid-agent

# Check status
sudo systemctl status rfid-agent

# View logs
tail -f /var/log/rfid/agent.log
```

## Configuration Flow

```
┌─────────────────┐
│   Bootstrap     │
│   (run once)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌─────────────────┐
│  Cloud API      │      │  Device Agent   │
│  Registration   │─────►│  Receives       │
│                 │      │  device_id      │
└─────────────────┘      └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  /etc/rfid/     │
                         │  device_id      │
                         │  (ONLY secret)  │
                         └────────┬────────┘
                                  │
                         On every start:
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Authenticate   │
                         │  with Cloud     │
                         │  (JWT Token)    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Fetch Config   │
                         │  (in memory)    │
                         │  NO FILE!       │
                         └─────────────────┘
```

## Offline Mode

When cloud is unavailable:

1. **Token**: Use cached JWT (until expiration)
2. **Config**: Use cached config from `/var/cache/rfid/config.enc`
3. **Readings**: Store in `/var/cache/rfid/readings.json`
4. **Reconnect**: Try every 60 seconds
5. **Sync**: Upload cached readings when online

### Cache Limits

| Item | Limit | Behavior |
|------|-------|----------|
| Config cache | 24 hours | Warn but continue |
| Readings cache | 10,000 | Remove oldest |
| Token | JWT expiry | Re-authenticate |

## Hardware Setup

### CM710-4 Connection

```
Raspberry Pi          CM710-4
┌──────────┐          ┌──────────┐
│          │          │          │
│  USB ────┼──────────┼── USB    │
│          │          │          │
│  GPIO 18 ┼──────────┼── EN     │
│          │          │          │
│  GPIO 17 ┼──────────┼── BUZZER │
│          │          │          │
└──────────┘          └──────────┘
```

### GPIO Pins

| Pin | Function |
|-----|----------|
| GPIO 18 | Module Enable |
| GPIO 17 | Buzzer Control |

## Files and Directories

### Configuration Files

| Path | Content |
|------|---------|
| `/etc/rfid/device_id` | Unique device identifier |
| `/etc/rfid/cloud_url` | Cloud API URL |

### Cache Files

| Path | Content |
|------|---------|
| `/var/cache/rfid/config.enc` | Cached configuration |
| `/var/cache/rfid/readings.json` | Offline readings |

### Log Files

| Path | Content |
|------|---------|
| `/var/log/rfid/agent.log` | Agent logs |
| `/var/log/rfid/reader.log` | RFID reader logs |
| `/var/log/rfid/cm710-4.log` | Raw RFID readings |

## Troubleshooting

### Device not authenticating

```bash
# Check device_id exists
cat /etc/rfid/device_id

# Test authentication manually
curl -X POST https://your-cloud.com/api/devices/authenticate \
  -H "Content-Type: application/json" \
  -d '{"device_id": "YOUR_ID", "mac_address": "YOUR_MAC"}'
```

### No RFID readings

```bash
# Check USB connection
ls -la /dev/ttyUSB* /dev/ttyACM*

# Check user permissions
groups $USER  # Should include: dialout, gpio

# Check reader service
sudo systemctl status rfid-reader
sudo journalctl -u rfid-reader -f
```

### Agent not starting

```bash
# Check service status
sudo systemctl status rfid-agent

# Check logs
tail -100 /var/log/rfid/agent-error.log

# Check cloud connectivity
curl -I https://your-cloud.com/health
```

### High memory usage

```bash
# Check cached readings count
wc -l /var/cache/rfid/readings.json

# Clear cache if needed (data will be lost!)
sudo rm /var/cache/rfid/readings.json
sudo systemctl restart rfid-agent
```

## Security Best Practices

1. **Keep firmware updated**: `sudo apt update && sudo apt upgrade`
2. **Use firewall**: Only allow outbound to cloud
3. **Rotate tokens**: Tokens auto-refresh, but audit in cloud
4. **Monitor logs**: Set up log rotation
5. **Physical security**: Secure the Raspberry Pi

## Commands Reference

```bash
# Start/Stop services
sudo systemctl start rfid-agent
sudo systemctl stop rfid-agent
sudo systemctl restart rfid-agent

# View logs
tail -f /var/log/rfid/agent.log
journalctl -u rfid-agent -f

# Check device info
cat /etc/rfid/device_id
cat /sys/class/net/eth0/address

# Check system stats
vcgencmd measure_temp
free -h
df -h

# Re-bootstrap (if needed)
sudo rm /etc/rfid/device_id
/opt/rfid/scripts/bootstrap.sh
```
