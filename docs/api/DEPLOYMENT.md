# Cloud Deployment Guide

## Quick Deploy

### Prerequisites
- Ubuntu 22.04 LTS server
- Docker & Docker Compose
- Domain name (optional, for HTTPS)

### 1. Clone Repository

```bash
git clone <your-repo>
cd rfid-cm710-4-iot
```

### 2. Generate Secrets

```bash
# Generate secure JWT secret
export JWT_SECRET=$(openssl rand -hex 32)
echo "JWT_SECRET: $JWT_SECRET"

# Generate admin API key
export ADMIN_API_KEY=$(openssl rand -hex 32)
echo "ADMIN_API_KEY: $ADMIN_API_KEY"
```

### 3. Create Environment File

```bash
cat > /app/backend/.env << EOF
MONGO_URL=mongodb://mongo:27017
DB_NAME=rfid_cloud
JWT_SECRET=$JWT_SECRET
JWT_EXPIRATION_HOURS=24
ADMIN_API_KEY=$ADMIN_API_KEY
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=rfid_user
RABBITMQ_PASSWORD=$(openssl rand -hex 16)
CORS_ORIGINS=*
EOF
```

### 4. Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: cloud/Dockerfile
    ports:
      - "8001:8001"
    env_file:
      - backend/.env
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
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 30s
      timeout: 10s
      retries: 3

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: rfid_user
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-rfid_password}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped

volumes:
  mongo_data:
  rabbitmq_data:
```

### 5. Start Services

```bash
docker compose up -d
docker compose logs -f
```

### 6. Verify Deployment

```bash
curl http://localhost:8001/health
```

## Production Checklist

- [ ] Change all default passwords
- [ ] Configure firewall (ufw)
- [ ] Enable HTTPS with SSL certificate
- [ ] Set up log rotation
- [ ] Configure MongoDB backup
- [ ] Monitor disk space
- [ ] Set up alerting

## Nginx Reverse Proxy (HTTPS)

```nginx
server {
    listen 443 ssl http2;
    server_name rfid.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/rfid.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/rfid.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name rfid.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

## Monitoring

### Health Check
```bash
curl http://localhost:8001/health
```

### View Statistics
```bash
curl -H "X-Admin-API-Key: YOUR_KEY" http://localhost:8001/api/admin/statistics
```

### View Logs
```bash
docker compose logs -f api
```
