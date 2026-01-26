# Cloud API Documentation

## Base URL

```
https://your-cloud-server.com
```

## Authentication

### Device Authentication

Devices authenticate using their unique `device_id` and `mac_address`.

**Endpoint**: `POST /api/devices/authenticate`

**Request**:
```json
{
  "device_id": "abc123def456",
  "mac_address": "D8:3A:DD:B3:E0:7F"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "device_id": "abc123def456"
}
```

**Errors**:
- `401`: Device not registered or MAC mismatch
- `401`: Device has been revoked

### Token Refresh

**Endpoint**: `POST /api/devices/refresh-token`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "device_id": "abc123def456"
}
```

---

## Configuration

### Get Device Configuration

Devices fetch their configuration from the cloud. **No .env files on device!**

**Endpoint**: `GET /api/config`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Response** (200):
```json
{
  "rabbitmq_host": "cloud.example.com",
  "rabbitmq_port": 5672,
  "rabbitmq_user": "rfid_user",
  "rabbitmq_password": "secure_password",
  "rabbitmq_vhost": "/",
  "queue_prefix": "rfid_",
  "log_level": "INFO",
  "heartbeat_interval": 60,
  "cache_ttl": 300,
  "offline_mode_enabled": true,
  "max_offline_readings": 10000
}
```

---

## RFID Readings

### Submit Readings

**Endpoint**: `POST /api/readings`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request**:
```json
{
  "readings": [
    {
      "timestamp": "2024-01-27 10:30:00.123",
      "device_id": "abc123def456",
      "mac_address": "D8:3A:DD:B3:E0:7F",
      "epc": "E200001234567890",
      "antenna": 1,
      "rssi": -45.5
    },
    {
      "timestamp": "2024-01-27 10:30:01.456",
      "device_id": "abc123def456",
      "mac_address": "D8:3A:DD:B3:E0:7F",
      "epc": "E200009876543210",
      "antenna": 2,
      "rssi": -52.3
    }
  ]
}
```

**Response** (200):
```json
{
  "status": "ok",
  "received": 2
}
```

### Query Readings

**Endpoint**: `GET /api/readings`

**Headers**:
```
Authorization: Bearer {access_token}
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `device_id` | string | Filter by device |
| `epc` | string | Filter by EPC tag |
| `start` | string | Start datetime (ISO format) |
| `end` | string | End datetime (ISO format) |
| `limit` | int | Max results (default: 100) |

**Example**:
```
GET /api/readings?device_id=abc123&limit=50&start=2024-01-27T00:00:00Z
```

**Response** (200):
```json
{
  "readings": [
    {
      "timestamp": "2024-01-27T10:30:00.123Z",
      "device_id": "abc123def456",
      "mac_address": "D8:3A:DD:B3:E0:7F",
      "epc": "E200001234567890",
      "antenna": 1,
      "rssi": -45.5,
      "received_at": "2024-01-27T10:30:01.000Z"
    }
  ],
  "count": 1
}
```

---

## Heartbeat

### Send Heartbeat

**Endpoint**: `POST /api/heartbeat`

**Headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**Request**:
```json
{
  "device_id": "abc123def456",
  "device_status": "online",
  "cpu_temp": 52.3,
  "memory_usage": 45.2,
  "disk_usage": 23.1,
  "uptime": 86400
}
```

**Response** (200):
```json
{
  "status": "ok",
  "timestamp": "2024-01-27T10:30:00.000Z"
}
```

---

## Admin Endpoints

All admin endpoints require `X-Admin-API-Key` header.

### Register Device

**Endpoint**: `POST /api/admin/devices/register`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
Content-Type: application/json
```

**Request**:
```json
{
  "mac_address": "D8:3A:DD:B3:E0:7F",
  "device_name": "Warehouse Reader 01",
  "location": "Building A, Dock 3"
}
```

**Response** (200):
```json
{
  "device_id": "abc123def456",
  "mac_address": "D8:3A:DD:B3:E0:7F",
  "device_name": "Warehouse Reader 01",
  "location": "Building A, Dock 3",
  "status": "registered",
  "registered_at": "2024-01-27T10:30:00.000Z",
  "last_seen": null,
  "is_revoked": false
}
```

**Errors**:
- `400`: Device already registered
- `403`: Invalid admin API key

### List Devices

**Endpoint**: `GET /api/admin/devices`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
```

**Response** (200):
```json
[
  {
    "device_id": "abc123def456",
    "mac_address": "D8:3A:DD:B3:E0:7F",
    "device_name": "Warehouse Reader 01",
    "location": "Building A, Dock 3",
    "status": "online",
    "registered_at": "2024-01-27T10:30:00.000Z",
    "last_seen": "2024-01-27T12:00:00.000Z",
    "is_revoked": false
  }
]
```

### Get Device

**Endpoint**: `GET /api/admin/devices/{device_id}`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
```

**Response** (200):
```json
{
  "device_id": "abc123def456",
  "mac_address": "D8:3A:DD:B3:E0:7F",
  "device_name": "Warehouse Reader 01",
  "location": "Building A, Dock 3",
  "status": "online",
  "registered_at": "2024-01-27T10:30:00.000Z",
  "last_seen": "2024-01-27T12:00:00.000Z",
  "is_revoked": false
}
```

### Revoke Device

**Endpoint**: `POST /api/admin/devices/{device_id}/revoke`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
```

**Response** (200):
```json
{
  "status": "revoked",
  "device_id": "abc123def456"
}
```

### Reinstate Device

**Endpoint**: `POST /api/admin/devices/{device_id}/reinstate`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
```

**Response** (200):
```json
{
  "status": "reinstated",
  "device_id": "abc123def456"
}
```

### Update Device Configuration

**Endpoint**: `PUT /api/admin/config/{device_id}`

Use `device_id="default"` to update default configuration for all devices.

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
Content-Type: application/json
```

**Request**:
```json
{
  "rabbitmq_host": "cloud.example.com",
  "rabbitmq_port": 5672,
  "rabbitmq_user": "rfid_user",
  "rabbitmq_password": "new_secure_password",
  "rabbitmq_vhost": "/",
  "queue_prefix": "rfid_",
  "log_level": "DEBUG",
  "heartbeat_interval": 30,
  "cache_ttl": 600,
  "offline_mode_enabled": true,
  "max_offline_readings": 20000
}
```

**Response** (200):
```json
{
  "status": "updated",
  "device_id": "abc123def456"
}
```

### Get Statistics

**Endpoint**: `GET /api/admin/statistics`

**Headers**:
```
X-Admin-API-Key: {admin_api_key}
```

**Response** (200):
```json
{
  "devices": {
    "total": 10,
    "online": 8,
    "revoked": 1
  },
  "readings": {
    "total": 1500000,
    "last_24h": 25000
  },
  "timestamp": "2024-01-27T12:00:00.000Z"
}
```

---

## Health Check

### Check API Health

**Endpoint**: `GET /health`

**Response** (200):
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2024-01-27T12:00:00.000Z"
}
```

**Response** (503):
```json
{
  "status": "degraded",
  "database": "unhealthy",
  "timestamp": "2024-01-27T12:00:00.000Z"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message description"
}
```

### Common HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Server Error |
