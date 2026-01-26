# Troubleshooting Guide - Local Device

## Common Issues

### 1. Device Not Authenticating

**Symptoms**: Agent shows "Authentication failed" or 401 errors.

**Solutions**:

```bash
# Check device_id is saved
cat /etc/rfid/device_id

# Check cloud URL
cat /etc/rfid/cloud_url

# Verify MAC address matches
cat /sys/class/net/eth0/address

# Test authentication manually
curl -X POST https://YOUR_CLOUD/api/devices/authenticate \
  -H "Content-Type: application/json" \
  -d '{"device_id": "YOUR_DEVICE_ID", "mac_address": "YOUR_MAC"}'
```

**If device_id is missing**: Run bootstrap again
```bash
/opt/rfid/scripts/bootstrap.sh
```

### 2. No RFID Readings

**Symptoms**: Log file is empty, no tags detected.

**Solutions**:

```bash
# Check USB connection
ls -la /dev/ttyUSB* /dev/ttyACM*

# If no device found, check dmesg
dmesg | grep -i usb | tail -20

# Check user permissions
groups $USER  # Should include: dialout, gpio

# Add missing permissions
sudo usermod -aG dialout $USER
sudo usermod -aG gpio $USER

# Logout and login again, or:
newgrp dialout

# Check reader service
sudo systemctl status rfid-reader
sudo journalctl -u rfid-reader -f
```

### 3. Agent Not Starting

**Symptoms**: `rfid-agent` service fails to start.

**Solutions**:

```bash
# Check service status
sudo systemctl status rfid-agent

# View detailed logs
sudo journalctl -u rfid-agent -n 100

# Check for missing files
ls -la /etc/rfid/
ls -la /opt/rfid/agent/

# Verify Python environment
python3 --version
python3 -c "import requests, pika, jwt"

# Run agent manually for debugging
cd /opt/rfid/agent
python3 device_agent.py
```

### 4. Offline Mode Issues

**Symptoms**: Device not caching data when cloud is unavailable.

**Solutions**:

```bash
# Check cache directory permissions
ls -la /var/cache/rfid/

# If permission denied:
sudo chown -R $USER:$USER /var/cache/rfid/

# Check cached readings
cat /var/cache/rfid/readings.json | python3 -m json.tool

# Check cached config
cat /var/cache/rfid/config.enc
```

### 5. High Memory Usage

**Symptoms**: System slowing down, out of memory errors.

**Solutions**:

```bash
# Check memory
free -h

# Check cached readings count
wc -l /var/cache/rfid/readings.json

# If too many cached readings, consider:
# - Improving network connectivity
# - Increasing max_offline_readings in cloud config
# - Clearing old cache (data will be lost!)
sudo rm /var/cache/rfid/readings.json
sudo systemctl restart rfid-agent
```

### 6. High CPU Temperature

**Symptoms**: Temperature warnings, thermal throttling.

**Solutions**:

```bash
# Check temperature
vcgencmd measure_temp

# If > 70°C:
# 1. Check ventilation
# 2. Add heatsink
# 3. Add active cooling (fan)

# Reduce CPU usage if needed
# Lower log level in cloud config: "log_level": "WARNING"
```

### 7. RabbitMQ Connection Failed

**Symptoms**: "RabbitMQ connection failed" errors.

**Solutions**:

```bash
# Test network connectivity
ping YOUR_CLOUD_SERVER

# Test RabbitMQ port
nc -zv YOUR_CLOUD_SERVER 5672

# If firewall blocking:
# On cloud server: sudo ufw allow from YOUR_PI_IP to any port 5672

# Check credentials in cloud config
curl -H "Authorization: Bearer YOUR_TOKEN" https://YOUR_CLOUD/api/config
```

## Diagnostic Commands

```bash
# System info
uname -a
cat /etc/os-release

# Network
ip addr
ping -c 3 google.com
ping -c 3 YOUR_CLOUD_SERVER

# Services
sudo systemctl status rfid-reader
sudo systemctl status rfid-agent

# Logs
tail -f /var/log/rfid/agent.log
tail -f /var/log/rfid/reader.log
tail -f /var/log/rfid/cm710-4.log

# Resources
free -h
df -h
vcgencmd measure_temp
```

## Re-bootstrap Device

If all else fails, re-bootstrap the device:

```bash
# Stop services
sudo systemctl stop rfid-agent
sudo systemctl stop rfid-reader

# Clear configuration
sudo rm -rf /etc/rfid/*
sudo rm -rf /var/cache/rfid/*

# Re-run bootstrap
RFID_CLOUD_URL="https://your-cloud.com" \
RFID_ADMIN_KEY="your-admin-key" \
/opt/rfid/scripts/bootstrap.sh

# Start services
sudo systemctl start rfid-reader
sudo systemctl start rfid-agent
```

## Contact Support

If issues persist:
1. Collect logs: `tar czf logs.tar.gz /var/log/rfid/`
2. Note device_id and MAC address
3. Describe the issue and steps tried
4. Open an issue on GitHub
