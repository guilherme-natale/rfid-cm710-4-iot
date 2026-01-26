#!/usr/bin/env python3
"""
RFID Cloud API - Central Configuration & Device Management
Zero .env on client devices - All config comes from cloud
"""
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import hashlib
import secrets
import logging
import os
import jwt
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '../../backend/.env'))

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration from environment
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'rfid_cloud')
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', '24'))
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', secrets.token_hex(32))

# Database client
db_client: AsyncIOMotorClient = None
db = None

security = HTTPBearer()


# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db
    try:
        db_client = AsyncIOMotorClient(MONGO_URL)
        db = db_client[DB_NAME]
        await db.command('ping')
        logger.info(f"✅ Connected to MongoDB: {DB_NAME}")
        
        # Create indexes
        await db.devices.create_index("device_id", unique=True)
        await db.devices.create_index("mac_address", unique=True)
        await db.tokens.create_index("device_id")
        await db.tokens.create_index("expires_at", expireAfterSeconds=0)
        await db.rfid_readings.create_index([("timestamp", -1)])
        await db.rfid_readings.create_index("device_id")
        await db.rfid_readings.create_index("epc")
        logger.info("✅ Database indexes created")
        
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    yield
    
    if db_client:
        db_client.close()


app = FastAPI(
    title="RFID Cloud API",
    description="Central configuration and device management for RFID IoT devices",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MODELS ====================
class DeviceRegister(BaseModel):
    mac_address: str = Field(..., description="Device MAC address")
    device_name: Optional[str] = Field(None, description="Friendly device name")
    location: Optional[str] = Field(None, description="Physical location")

class DeviceConfig(BaseModel):
    rabbitmq_host: str = Field(..., description="RabbitMQ server host")
    rabbitmq_port: int = Field(5672, description="RabbitMQ server port")
    rabbitmq_user: str = Field(..., description="RabbitMQ username")
    rabbitmq_password: str = Field(..., description="RabbitMQ password")
    rabbitmq_vhost: str = Field("/", description="RabbitMQ virtual host")
    queue_prefix: str = Field("rfid_", description="Queue name prefix")
    log_level: str = Field("INFO", description="Logging level")
    heartbeat_interval: int = Field(60, description="Heartbeat interval in seconds")
    cache_ttl: int = Field(300, description="Local cache TTL in seconds")
    offline_mode_enabled: bool = Field(True, description="Enable offline operation")
    max_offline_readings: int = Field(10000, description="Max readings to cache offline")

class DeviceResponse(BaseModel):
    device_id: str
    mac_address: str
    device_name: Optional[str]
    location: Optional[str]
    status: str
    registered_at: str
    last_seen: Optional[str]
    is_revoked: bool

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    device_id: str

class DeviceAuth(BaseModel):
    device_id: str = Field(..., description="Unique device identifier")
    mac_address: str = Field(..., description="Device MAC address for verification")

class RFIDReading(BaseModel):
    timestamp: str
    device_id: str
    mac_address: str
    epc: str
    antenna: int
    rssi: float

class RFIDReadingBatch(BaseModel):
    readings: List[RFIDReading]

class DeviceHeartbeat(BaseModel):
    device_id: str
    device_status: str = "online"
    cpu_temp: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    uptime: Optional[int] = None


# ==================== HELPERS ====================
def generate_device_id(mac_address: str) -> str:
    """Generate unique device ID from MAC address"""
    return hashlib.sha256(f"rfid-device-{mac_address}".encode()).hexdigest()[:16]


def create_jwt_token(device_id: str, mac_address: str) -> tuple[str, datetime]:
    """Create JWT token for device authentication"""
    expires = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "device_id": device_id,
        "mac_address": mac_address,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "type": "device_access"
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires


async def verify_device_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return device info"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        device_id = payload.get("device_id")
        
        # Check if device exists and is not revoked
        device = await db.devices.find_one({"device_id": device_id})
        if not device:
            raise HTTPException(status_code=401, detail="Device not found")
        if device.get("is_revoked", False):
            raise HTTPException(status_code=401, detail="Device has been revoked")
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_admin_key(request: Request):
    """Verify admin API key from header"""
    api_key = request.headers.get("X-Admin-API-Key")
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin API key")
    return True


# ==================== PUBLIC ENDPOINTS ====================
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "RFID Cloud API",
        "version": "2.0.0",
        "status": "operational",
        "documentation": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        await db.command('ping')
        db_status = "healthy"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ==================== DEVICE AUTHENTICATION ====================
@app.post("/api/devices/authenticate", response_model=TokenResponse, tags=["Authentication"])
async def authenticate_device(auth: DeviceAuth):
    """
    Authenticate device and receive JWT token.
    Device must be registered first by admin.
    """
    device = await db.devices.find_one({
        "device_id": auth.device_id,
        "mac_address": auth.mac_address
    })
    
    if not device:
        raise HTTPException(status_code=401, detail="Device not registered or MAC mismatch")
    
    if device.get("is_revoked", False):
        raise HTTPException(status_code=401, detail="Device has been revoked")
    
    # Generate new token
    token, expires = create_jwt_token(auth.device_id, auth.mac_address)
    
    # Store token info
    await db.tokens.insert_one({
        "device_id": auth.device_id,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires
    })
    
    # Update last seen
    await db.devices.update_one(
        {"device_id": auth.device_id},
        {"$set": {"last_seen": datetime.now(timezone.utc).isoformat(), "status": "online"}}
    )
    
    logger.info(f"✅ Device authenticated: {auth.device_id}")
    
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        device_id=auth.device_id
    )


@app.post("/api/devices/refresh-token", response_model=TokenResponse, tags=["Authentication"])
async def refresh_token(device_info: dict = Depends(verify_device_token)):
    """Refresh JWT token before expiration"""
    device_id = device_info["device_id"]
    mac_address = device_info["mac_address"]
    
    token, expires = create_jwt_token(device_id, mac_address)
    
    await db.tokens.insert_one({
        "device_id": device_id,
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires
    })
    
    return TokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_HOURS * 3600,
        device_id=device_id
    )


# ==================== DEVICE CONFIG (Authenticated) ====================
@app.get("/api/config", response_model=DeviceConfig, tags=["Configuration"])
async def get_device_config(device_info: dict = Depends(verify_device_token)):
    """
    Get device configuration from cloud.
    This is the ONLY source of configuration for devices.
    No .env files on client!
    """
    device_id = device_info["device_id"]
    
    # Get device-specific config or default
    config = await db.device_configs.find_one({"device_id": device_id})
    
    if not config:
        # Return default configuration
        config = await db.device_configs.find_one({"device_id": "default"})
    
    if not config:
        # Create default config
        default_config = {
            "device_id": "default",
            "rabbitmq_host": os.environ.get("RABBITMQ_HOST", "localhost"),
            "rabbitmq_port": int(os.environ.get("RABBITMQ_PORT", 5672)),
            "rabbitmq_user": os.environ.get("RABBITMQ_USER", "rfid_user"),
            "rabbitmq_password": os.environ.get("RABBITMQ_PASSWORD", "rfid_password"),
            "rabbitmq_vhost": "/",
            "queue_prefix": "rfid_",
            "log_level": "INFO",
            "heartbeat_interval": 60,
            "cache_ttl": 300,
            "offline_mode_enabled": True,
            "max_offline_readings": 10000
        }
        await db.device_configs.insert_one(default_config)
        config = default_config
    
    # Update last config fetch time
    await db.devices.update_one(
        {"device_id": device_id},
        {"$set": {"last_config_fetch": datetime.now(timezone.utc).isoformat()}}
    )
    
    return DeviceConfig(
        rabbitmq_host=config["rabbitmq_host"],
        rabbitmq_port=config["rabbitmq_port"],
        rabbitmq_user=config["rabbitmq_user"],
        rabbitmq_password=config["rabbitmq_password"],
        rabbitmq_vhost=config.get("rabbitmq_vhost", "/"),
        queue_prefix=config.get("queue_prefix", "rfid_"),
        log_level=config.get("log_level", "INFO"),
        heartbeat_interval=config.get("heartbeat_interval", 60),
        cache_ttl=config.get("cache_ttl", 300),
        offline_mode_enabled=config.get("offline_mode_enabled", True),
        max_offline_readings=config.get("max_offline_readings", 10000)
    )


# ==================== READINGS (Authenticated) ====================
@app.post("/api/readings", tags=["Readings"])
async def submit_readings(batch: RFIDReadingBatch, device_info: dict = Depends(verify_device_token)):
    """Submit RFID readings to cloud"""
    device_id = device_info["device_id"]
    
    readings_to_insert = []
    for reading in batch.readings:
        readings_to_insert.append({
            "timestamp": reading.timestamp,
            "device_id": device_id,
            "mac_address": reading.mac_address,
            "epc": reading.epc,
            "antenna": reading.antenna,
            "rssi": reading.rssi,
            "received_at": datetime.now(timezone.utc).isoformat()
        })
    
    if readings_to_insert:
        await db.rfid_readings.insert_many(readings_to_insert)
    
    # Update device stats
    await db.devices.update_one(
        {"device_id": device_id},
        {
            "$set": {"last_seen": datetime.now(timezone.utc).isoformat()},
            "$inc": {"total_readings": len(readings_to_insert)}
        }
    )
    
    return {"status": "ok", "received": len(readings_to_insert)}


@app.get("/api/readings", tags=["Readings"])
async def get_readings(
    device_id: Optional[str] = None,
    epc: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 100,
    device_info: dict = Depends(verify_device_token)
):
    """Get RFID readings with filters"""
    query = {}
    
    if device_id:
        query["device_id"] = device_id
    if epc:
        query["epc"] = epc
    if start:
        query["timestamp"] = {"$gte": start}
    if end:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end
        else:
            query["timestamp"] = {"$lte": end}
    
    cursor = db.rfid_readings.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    readings = await cursor.to_list(length=limit)
    
    return {"readings": readings, "count": len(readings)}


# ==================== HEARTBEAT (Authenticated) ====================
@app.post("/api/heartbeat", tags=["Monitoring"])
async def device_heartbeat(heartbeat: DeviceHeartbeat, device_info: dict = Depends(verify_device_token)):
    """Receive device heartbeat with status info"""
    await db.devices.update_one(
        {"device_id": heartbeat.device_id},
        {
            "$set": {
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "status": heartbeat.status,
                "cpu_temp": heartbeat.cpu_temp,
                "memory_usage": heartbeat.memory_usage,
                "disk_usage": heartbeat.disk_usage,
                "uptime": heartbeat.uptime
            }
        }
    )
    
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ==================== ADMIN ENDPOINTS ====================
@app.post("/api/admin/devices/register", response_model=DeviceResponse, tags=["Admin"])
async def register_device(device: DeviceRegister, _: bool = Depends(verify_admin_key)):
    """
    Register a new device (Admin only).
    Returns device_id that must be provisioned on the Raspberry Pi.
    """
    device_id = generate_device_id(device.mac_address)
    
    # Check if already exists
    existing = await db.devices.find_one({"device_id": device_id})
    if existing:
        raise HTTPException(status_code=400, detail="Device already registered")
    
    now = datetime.now(timezone.utc).isoformat()
    device_doc = {
        "device_id": device_id,
        "mac_address": device.mac_address.upper(),
        "device_name": device.device_name,
        "location": device.location,
        "status": "registered",
        "registered_at": now,
        "last_seen": None,
        "is_revoked": False,
        "total_readings": 0
    }
    
    await db.devices.insert_one(device_doc)
    logger.info(f"✅ Device registered: {device_id} ({device.mac_address})")
    
    return DeviceResponse(
        device_id=device_id,
        mac_address=device.mac_address.upper(),
        device_name=device.device_name,
        location=device.location,
        status="registered",
        registered_at=now,
        last_seen=None,
        is_revoked=False
    )


@app.get("/api/admin/devices", response_model=List[DeviceResponse], tags=["Admin"])
async def list_devices(_: bool = Depends(verify_admin_key)):
    """List all registered devices (Admin only)"""
    cursor = db.devices.find({}, {"_id": 0})
    devices = await cursor.to_list(length=1000)
    return [DeviceResponse(**d) for d in devices]


@app.get("/api/admin/devices/{device_id}", response_model=DeviceResponse, tags=["Admin"])
async def get_device(device_id: str, _: bool = Depends(verify_admin_key)):
    """Get device details (Admin only)"""
    device = await db.devices.find_one({"device_id": device_id}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceResponse(**device)


@app.post("/api/admin/devices/{device_id}/revoke", tags=["Admin"])
async def revoke_device(device_id: str, _: bool = Depends(verify_admin_key)):
    """
    Revoke device access (Admin only).
    Device will no longer be able to authenticate.
    """
    result = await db.devices.update_one(
        {"device_id": device_id},
        {"$set": {"is_revoked": True, "status": "revoked"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Invalidate all tokens for this device
    await db.tokens.delete_many({"device_id": device_id})
    
    logger.info(f"🚫 Device revoked: {device_id}")
    return {"status": "revoked", "device_id": device_id}


@app.post("/api/admin/devices/{device_id}/reinstate", tags=["Admin"])
async def reinstate_device(device_id: str, _: bool = Depends(verify_admin_key)):
    """Reinstate a revoked device (Admin only)"""
    result = await db.devices.update_one(
        {"device_id": device_id},
        {"$set": {"is_revoked": False, "status": "registered"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    
    logger.info(f"✅ Device reinstated: {device_id}")
    return {"status": "reinstated", "device_id": device_id}


@app.put("/api/admin/config/{device_id}", tags=["Admin"])
async def update_device_config(device_id: str, config: DeviceConfig, _: bool = Depends(verify_admin_key)):
    """
    Update device configuration (Admin only).
    Use device_id="default" to update default config for all devices.
    """
    config_doc = config.model_dump()
    config_doc["device_id"] = device_id
    config_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.device_configs.update_one(
        {"device_id": device_id},
        {"$set": config_doc},
        upsert=True
    )
    
    logger.info(f"✅ Config updated for: {device_id}")
    return {"status": "updated", "device_id": device_id}


@app.get("/api/admin/statistics", tags=["Admin"])
async def get_statistics(_: bool = Depends(verify_admin_key)):
    """Get system statistics (Admin only)"""
    total_devices = await db.devices.count_documents({})
    online_devices = await db.devices.count_documents({"status": "online"})
    revoked_devices = await db.devices.count_documents({"is_revoked": True})
    total_readings = await db.rfid_readings.count_documents({})
    
    # Readings in last 24h
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    readings_24h = await db.rfid_readings.count_documents({"received_at": {"$gte": yesterday}})
    
    return {
        "devices": {
            "total": total_devices,
            "online": online_devices,
            "revoked": revoked_devices
        },
        "readings": {
            "total": total_readings,
            "last_24h": readings_24h
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
