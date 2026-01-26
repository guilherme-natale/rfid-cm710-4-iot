# ☁️ Cloud Architecture

## Overview

The cloud component serves as the **single source of truth** for all RFID IoT devices. No configuration or secrets are stored on client devices.

## Components

### 1. Cloud API (FastAPI)

**Purpose**: Central authentication, configuration, and data management.

```
/cloud/api/
├── main.py          # Main FastAPI application
└── __init__.py
```

**Key Features**:
- JWT-based device authentication
- Configuration distribution
- RFID readings storage
- Device management
- Statistics and monitoring

### 2. MongoDB

**Collections**:

| Collection | Purpose |
|------------|---------|
| `devices` | Registered devices and status |
| `tokens` | Active JWT tokens (auto-expire) |
| `device_configs` | Per-device or default configs |
| `rfid_readings` | RFID tag readings |

**Indexes**:
- `devices.device_id` (unique)
- `devices.mac_address` (unique)
- `tokens.device_id`
- `tokens.expires_at` (TTL)
- `rfid_readings.timestamp`
- `rfid_readings.device_id`
- `rfid_readings.epc`

### 3. RabbitMQ

**Purpose**: Real-time message passing for RFID events.

**Queues**:
- `rfid_{device_id}` - Per-device queue for readings
- `events` - System events (device online/offline)

## Security Model

### Authentication Flow

```
┌──────────────┐                      ┌──────────────┐
│   Device     │                      │   Cloud API  │
└──────┬───────┘                      └──────┬───────┘
       │                                     │
       │  POST /api/devices/authenticate     │
       │  { device_id, mac_address }         │
       │────────────────────────────────────►│
       │                                     │
       │                                     │ Verify device_id
       │                                     │ Verify MAC match
       │                                     │ Check not revoked
       │                                     │
       │     200 OK                          │
       │     { access_token, expires_in }    │
       │◄────────────────────────────────────│
       │                                     │
       │  GET /api/config                    │
       │  Authorization: Bearer {token}      │
       │────────────────────────────────────►│
       │                                     │
       │     200 OK                          │
       │     { rabbitmq_host, ... }          │
       │◄────────────────────────────────────│
       │                                     │
```

### JWT Token Structure

```json
{
  "device_id": "abc123def456",
  "mac_address": "D8:3A:DD:B3:E0:7F",
  "exp": 1706400000,
  "iat": 1706313600,
  "type": "device_access"
}
```

### Admin API Key

Admin endpoints require `X-Admin-API-Key` header:
- Device registration
- Device revocation
- Configuration updates
- Statistics access

## Configuration Management

### Default Configuration

Stored in `device_configs` with `device_id: "default"`:

```json
{
  "device_id": "default",
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

### Per-Device Configuration

Override default for specific devices:

```json
{
  "device_id": "abc123def456",
  "log_level": "DEBUG",
  "heartbeat_interval": 30
}
```

## Data Flow

### RFID Reading Submission

```
Device → POST /api/readings → MongoDB → (Optional) RabbitMQ
```

### Batch Processing

Devices can submit multiple readings in a single request:

```json
{
  "readings": [
    {
      "timestamp": "2024-01-27 10:30:00.123",
      "device_id": "abc123",
      "mac_address": "D8:3A:DD:B3:E0:7F",
      "epc": "E200001234",
      "antenna": 1,
      "rssi": -45.5
    }
  ]
}
```

## Monitoring

### Device Status

| Status | Description |
|--------|-------------|
| `registered` | Device registered, never connected |
| `online` | Device currently online |
| `offline` | Last heartbeat > 5 minutes ago |
| `revoked` | Device access revoked |

### Health Checks

```
GET /health
```

Returns:
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2024-01-27T10:30:00Z"
}
```

## Deployment

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGO_URL` | MongoDB connection string | Yes |
| `DB_NAME` | Database name | No (default: rfid_cloud) |
| `JWT_SECRET` | Secret for JWT signing | Yes |
| `JWT_EXPIRATION_HOURS` | Token validity | No (default: 24) |
| `ADMIN_API_KEY` | Admin API authentication | Yes |
| `RABBITMQ_HOST` | RabbitMQ server | Yes |
| `RABBITMQ_PORT` | RabbitMQ port | No (default: 5672) |
| `RABBITMQ_USER` | RabbitMQ username | Yes |
| `RABBITMQ_PASSWORD` | RabbitMQ password | Yes |
| `CORS_ORIGINS` | Allowed CORS origins | No (default: *) |

### Docker Deployment

```yaml
version: '3.8'

services:
  api:
    build: ./cloud/api
    ports:
      - "8001:8001"
    environment:
      MONGO_URL: mongodb://mongo:27017
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_API_KEY: ${ADMIN_API_KEY}
    depends_on:
      - mongo
      - rabbitmq

  mongo:
    image: mongo:7
    volumes:
      - mongo_data:/data/db

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"

volumes:
  mongo_data:
```

## Scaling

### Horizontal Scaling

- API: Stateless, scale behind load balancer
- MongoDB: Replica set for high availability
- RabbitMQ: Cluster for message distribution

### Performance

- Use MongoDB indexes for queries
- Enable connection pooling
- Consider Redis for caching tokens
