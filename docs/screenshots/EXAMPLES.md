# Screenshots - RFID Cloud IoT System

## 1. Health Check Endpoint

**Request:**
```bash
GET /health
```

**Response:**
```json
{
    "status": "healthy",
    "database": "healthy",
    "timestamp": "2026-01-26T16:41:09.244958+00:00"
}
```

---

## 2. Swagger UI (API Documentation)

**URL:** `http://localhost:8001/docs`

**Available Endpoints:**
```
GET    /                                    Root info
GET    /health                              Health check
POST   /api/devices/authenticate            Device authentication
POST   /api/devices/refresh-token           Refresh JWT token
GET    /api/config                          Get device config
POST   /api/readings                        Submit RFID readings
GET    /api/readings                        Query readings
POST   /api/heartbeat                       Device heartbeat
POST   /api/admin/devices/register          Register new device
GET    /api/admin/devices                   List all devices
GET    /api/admin/devices/{device_id}       Get device details
POST   /api/admin/devices/{id}/revoke       Revoke device access
POST   /api/admin/devices/{id}/reinstate    Reinstate device
PUT    /api/admin/config/{device_id}        Update device config
GET    /api/admin/statistics                System statistics
```

---

## 3. Device Registration

**Request:**
```bash
POST /api/admin/devices/register
Headers: X-Admin-API-Key: <admin_key>
```

```json
{
    "mac_address": "D8:3A:DD:B3:E0:7F",
    "device_name": "Warehouse Reader 01",
    "location": "Building A, Dock 3"
}
```

**Response:**
```json
{
    "device_id": "3411f744cf302eb2",
    "mac_address": "D8:3A:DD:B3:E0:7F",
    "device_name": "Warehouse Reader 01",
    "location": "Building A, Dock 3",
    "status": "registered",
    "registered_at": "2026-01-26T16:24:11.958120+00:00",
    "last_seen": null,
    "is_revoked": false
}
```

---

## 4. Device Authentication (JWT)

**Request:**
```bash
POST /api/devices/authenticate
```

```json
{
    "device_id": "3411f744cf302eb2",
    "mac_address": "D8:3A:DD:B3:E0:7F"
}
```

**Response:**
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "device_id": "3411f744cf302eb2"
}
```

---

## 5. Get Configuration (From Cloud)

**Request:**
```bash
GET /api/config
Headers: Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
    "rabbitmq_host": "localhost",
    "rabbitmq_port": 5672,
    "rabbitmq_user": "rfid_user",
    "rabbitmq_password": "rfid_password",
    "rabbitmq_vhost": "/",
    "queue_prefix": "rfid_",
    "log_level": "INFO",
    "heartbeat_interval": 60,
    "cache_ttl": 300,
    "offline_mode_enabled": true,
    "max_offline_readings": 10000
}
```

> ⚠️ **Note:** This config is received in memory only. Never stored on device!

---

## 6. Submit RFID Readings

**Request:**
```bash
POST /api/readings
Headers: Authorization: Bearer <jwt_token>
```

```json
{
    "readings": [
        {
            "timestamp": "2024-01-27 10:30:00.123",
            "device_id": "3411f744cf302eb2",
            "mac_address": "D8:3A:DD:B3:E0:7F",
            "epc": "E200001234567890",
            "antenna": 1,
            "rssi": -45.5
        }
    ]
}
```

**Response:**
```json
{
    "status": "ok",
    "received": 1
}
```

---

## 7. System Statistics

**Request:**
```bash
GET /api/admin/statistics
Headers: X-Admin-API-Key: <admin_key>
```

**Response:**
```json
{
    "devices": {
        "total": 2,
        "online": 2,
        "revoked": 0
    },
    "readings": {
        "total": 6,
        "last_24h": 6
    },
    "timestamp": "2026-01-26T16:41:09.244958+00:00"
}
```

---

## 8. Bootstrap Output (Raspberry Pi)

```
============================================================
  RFID Device Bootstrap
  Zero-Config Local Setup
============================================================

Checking dependencies... ✅
Installing Python dependencies... ✅
Creating directories... ✅

Enter Cloud API URL: https://rfid.example.com
Enter Admin API Key: ****

Registering device with cloud...
   MAC Address: D8:3A:DD:B3:E0:7F
✅ Device registered!
   Device ID: 3411f744cf302eb2

Saving device configuration...
✅ Configuration saved
   /etc/rfid/device_id
   /etc/rfid/cloud_url

Verifying authentication...
✅ Authentication successful!
✅ Configuration fetch successful!

Installing systemd service...
✅ Service installed

============================================================
  BOOTSTRAP COMPLETE!
============================================================

Device Information:
   Device ID:    3411f744cf302eb2
   MAC Address:  D8:3A:DD:B3:E0:7F
   Cloud URL:    https://rfid.example.com

Files Created:
   /etc/rfid/device_id    - Unique device identifier
   /etc/rfid/cloud_url    - Cloud API URL

NO .env FILES - All config from cloud!

Next Steps:
   1. Start the agent:
      sudo systemctl start rfid-agent

   2. Check status:
      sudo systemctl status rfid-agent

   3. View logs:
      tail -f /var/log/rfid/agent.log
```

---

## 9. Device Agent Running

```
==============================================================
🚀 RFID Device Agent Starting
   Cloud URL: https://rfid.example.com
==============================================================
   Device ID: 3411f744cf302eb2
   MAC Address: D8:3A:DD:B3:E0:7F

🔐 Authenticating with cloud...
✅ Authentication successful (expires in 86400s)

📥 Fetching configuration from cloud...
✅ Configuration received:
   RabbitMQ: rabbitmq.example.com:5672
   Log Level: INFO
   Offline Mode: True

🐰 Connecting to RabbitMQ: rabbitmq.example.com...
✅ RabbitMQ connected, queue: rfid_3411f744cf302eb2

📖 Monitoring RFID log: /var/log/rfid/cm710-4.log

✅ EPC=E200001234567890 ANT=1 RSSI=-45.5
✅ EPC=E200009876543210 ANT=2 RSSI=-52.3
💓 Heartbeat sent
```
