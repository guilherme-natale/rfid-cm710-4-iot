from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import subprocess
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (Atlas ou local)
mongo_url = os.environ.get('MONGODB_URL') or os.environ.get('MONGO_URL')
if not mongo_url:
    raise ValueError("MONGODB_URL or MONGO_URL environment variable is required")

client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'rfid_db')]

app = FastAPI(
    title="RFID CM710-4 API",
    description="API para gerenciamento do sistema RFID",
    version="2.0.0"
)

api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class RFIDReading(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str
    mac_address: str
    epc: str
    antenna: int
    rssi: float
    processed_at: Optional[str] = None

class RFIDReadingResponse(BaseModel):
    readings: List[RFIDReading]
    total: int
    page: int
    per_page: int

class CM710Config(BaseModel):
    potencia: Optional[int] = Field(None, ge=5, le=30, description="Potência em dBm (5-30)")
    regiao: Optional[str] = Field(None, description="Região: 01, 02, 04, 08, 3C, etc.")
    antenas: Optional[str] = Field(None, description="Máscara antenas (hex): 01, 02, 04, 08, 0F")
    frequencia: Optional[int] = Field(None, description="Frequência fixa em kHz ou None para hopping")
    fastid: Optional[str] = Field(None, description="FastID: 01 ligado, 00 desligado")

class CM710ConfigResponse(BaseModel):
    firmware: Optional[str] = None
    temperatura: Optional[float] = None
    potencia: Optional[float] = None
    regiao: Optional[str] = None
    regiao_desc: Optional[str] = None
    antenas: Optional[int] = None
    antenas_desc: Optional[str] = None

class NetworkConfig(BaseModel):
    interface: str = Field(default="eth0", description="Interface de rede")
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None
    dns: Optional[str] = None
    dhcp: bool = True

class WiFiConfig(BaseModel):
    ssid: str
    password: str
    security: str = "WPA2"

class SystemStatus(BaseModel):
    rfid_reader_status: str
    rabbitmq_status: str
    mongodb_status: str
    cpu_temp: Optional[float] = None
    uptime: Optional[str] = None

# ==================== RFID READINGS APIs ====================

@api_router.get("/rfid/readings", response_model=RFIDReadingResponse)
async def get_rfid_readings(
    page: int = 1,
    per_page: int = 50,
    mac_address: Optional[str] = None,
    epc: Optional[str] = None
):
    """Obtém leituras RFID com paginação e filtros"""
    skip = (page - 1) * per_page
    query = {}
    
    if mac_address:
        query['mac_address'] = mac_address
    if epc:
        query['epc'] = epc
    
    total = await db.rfid_readings.count_documents(query)
    readings = await db.rfid_readings.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(per_page).to_list(per_page)
    
    return {
        "readings": readings,
        "total": total,
        "page": page,
        "per_page": per_page
    }

@api_router.get("/rfid/readings/latest")
async def get_latest_readings(limit: int = 10):
    """Obtém últimas leituras RFID"""
    readings = await db.rfid_readings.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"readings": readings}

@api_router.get("/rfid/readings/stats")
async def get_rfid_stats():
    """Obtém estatísticas das leituras RFID"""
    total = await db.rfid_readings.count_documents({})
    unique_epcs = await db.rfid_readings.distinct("epc")
    
    pipeline = [
        {"$group": {"_id": "$antenna", "count": {"$sum": 1}}}
    ]
    antenna_stats = await db.rfid_readings.aggregate(pipeline).to_list(None)
    
    return {
        "total_readings": total,
        "unique_epcs": len(unique_epcs),
        "by_antenna": {stat["_id"]: stat["count"] for stat in antenna_stats}
    }

# ==================== CM710-4 CONFIG APIs ====================

@api_router.get("/cm710/config", response_model=CM710ConfigResponse)
async def get_cm710_config():
    """Obtém configuração atual do módulo CM710-4"""
    try:
        script_path = "/app/rfid_scripts/check_config.py"
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            config = json.loads(result.stdout)
            await db.cm710_configs.insert_one({
                **config,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return config
        else:
            raise HTTPException(status_code=500, detail=f"Erro ao ler config: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout ao ler configuração")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/cm710/config")
async def set_cm710_config(config: CM710Config):
    """Configura o módulo CM710-4"""
    try:
        script_path = "/app/rfid_scripts/set_config.py"
        config_json = config.model_dump(exclude_none=True)
        
        result = subprocess.run(
            ["python3", script_path, json.dumps(config_json)],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            response = json.loads(result.stdout)
            await db.cm710_configs.insert_one({
                "config_sent": config_json,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return {"success": True, "response": response}
        else:
            raise HTTPException(status_code=500, detail=f"Erro ao configurar: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout ao configurar módulo")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/cm710/config/history")
async def get_config_history(limit: int = 10):
    """Obtém histórico de configurações"""
    configs = await db.cm710_configs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"configs": configs}

# ==================== NETWORK CONFIG APIs ====================

@api_router.get("/network/status")
async def get_network_status():
    """Obtém status da rede"""
    try:
        result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
        ip_addresses = result.stdout.strip().split()
        
        result = subprocess.run(["ip", "addr"], capture_output=True, text=True)
        interfaces = result.stdout
        
        return {
            "ip_addresses": ip_addresses,
            "interfaces_info": interfaces
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/network/config")
async def set_network_config(config: NetworkConfig):
    """Configura rede"""
    try:
        if config.dhcp:
            dhcpcd_conf = f"interface {config.interface}\ndhcp\n"
        else:
            dhcpcd_conf = f"""interface {config.interface}
static ip_address={config.ip_address}/{config.netmask}
static routers={config.gateway}
static domain_name_servers={config.dns}
"""
        
        await db.network_configs.insert_one({
            **config.model_dump(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "message": "Configuração salva. Requer aplicação manual.",
            "config_preview": dhcpcd_conf
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/network/wifi")
async def set_wifi_config(config: WiFiConfig):
    """Configura WiFi"""
    try:
        wpa_conf = f"""network={{
    ssid="{config.ssid}"
    psk="{config.password}"
    key_mgmt={config.security}
}}
"""
        await db.wifi_configs.insert_one({
            "ssid": config.ssid,
            "security": config.security,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "message": "Configuração WiFi salva",
            "config_preview": wpa_conf
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SYSTEM STATUS APIs ====================

@api_router.get("/system/status", response_model=SystemStatus)
async def get_system_status():
    """Obtém status do sistema"""
    try:
        cpu_temp = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = float(f.read()) / 1000.0
        except:
            pass
        
        uptime = None
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                uptime = f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
        except:
            pass
        
        rfid_status = "unknown"
        rabbitmq_status = "unknown"
        mongodb_status = "unknown"
        
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=rfid_rabbitmq", "--format", "{{.Status}}"], 
                capture_output=True, text=True, timeout=5
            )
            rabbitmq_status = "running" if "Up" in result.stdout else "stopped"
        except:
            pass
        
        try:
            await db.admin.command('ping')
            mongodb_status = "running"
        except:
            mongodb_status = "stopped"
        
        return {
            "rfid_reader_status": rfid_status,
            "rabbitmq_status": rabbitmq_status,
            "mongodb_status": mongodb_status,
            "cpu_temp": cpu_temp,
            "uptime": uptime
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/system/restart-service")
async def restart_service(service: str):
    """Reinicia serviço"""
    try:
        if service in ["rabbitmq", "producer"]:
            result = subprocess.run(
                ["docker", "restart", f"rfid_{service}"],
                capture_output=True,
                text=True,
                timeout=30
            )
            return {"success": result.returncode == 0, "message": result.stdout}
        else:
            return {"success": False, "message": "Serviço inválido"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ROOT ROUTE ====================

@api_router.get("/")
async def root():
    return {
        "message": "RFID Tracking System API",
        "version": "2.0.0",
        "endpoints": {
            "rfid_readings": "/api/rfid/readings",
            "cm710_config": "/api/cm710/config",
            "network": "/api/network/status",
            "system": "/api/system/status"
        }
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
