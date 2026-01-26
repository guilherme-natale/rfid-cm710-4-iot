#!/usr/bin/env python3
"""
RFID Cloud API - REST API para consultar dados do InfluxDB e PostgreSQL
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import os
import logging
from influxdb_client import InfluxDBClient
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
INFLUXDB_URL = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
INFLUXDB_TOKEN = os.environ.get('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.environ.get('INFLUXDB_ORG', 'rfid_org')
INFLUXDB_BUCKET = os.environ.get('INFLUXDB_BUCKET', 'rfid_readings')

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', 5432))
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'rfid_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'rfid_password')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'rfid_metadata')

app = FastAPI(title="RFID Cloud API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clients globais
influx_client = None
postgres_conn = None


# ==================== MODELS ====================

class RFIDReading(BaseModel):
    timestamp: str
    mac_address: str
    epc: str
    antenna: int
    rssi: float


class Device(BaseModel):
    mac_address: str
    device_name: Optional[str] = None
    location: Optional[str] = None
    last_seen: Optional[str] = None
    status: str = "active"


class Statistics(BaseModel):
    total_readings: int
    unique_epcs: int
    unique_devices: int
    time_range: str
    by_device: dict
    by_antenna: dict


# ==================== STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup():
    global influx_client, postgres_conn
    
    # InfluxDB
    try:
        influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG
        )
        logger.info("✅ Conectado ao InfluxDB")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar InfluxDB: {e}")
    
    # PostgreSQL
    try:
        postgres_conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            dbname=POSTGRES_DB
        )
        logger.info("✅ Conectado ao PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")


@app.on_event("shutdown")
async def shutdown():
    if influx_client:
        influx_client.close()
    if postgres_conn:
        postgres_conn.close()


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "message": "RFID Cloud API",
        "version": "1.0.0",
        "endpoints": {
            "readings": "/api/readings",
            "devices": "/api/devices",
            "statistics": "/api/statistics"
        }
    }


@app.get("/api/readings", response_model=List[RFIDReading])
async def get_readings(
    mac_address: Optional[str] = None,
    epc: Optional[str] = None,
    start: Optional[str] = None,
    stop: Optional[str] = None,
    limit: int = Query(default=100, le=1000)
):
    """
    Obtém leituras RFID do InfluxDB
    
    - **mac_address**: Filtrar por MAC do dispositivo
    - **epc**: Filtrar por EPC específico
    - **start**: Data/hora início (ISO format)
    - **stop**: Data/hora fim (ISO format)
    - **limit**: Número máximo de resultados
    """
    try:
        query_api = influx_client.query_api()
        
        # Construir query Flux
        filters = []
        if mac_address:
            filters.append(f'r["mac_address"] == "{mac_address}"')
        if epc:
            filters.append(f'r["epc"] == "{epc}"')
        
        filter_clause = " and ".join(filters) if filters else "true"
        
        # Range padrão: últimas 24 horas
        if not start:
            start = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
        if not stop:
            stop = datetime.utcnow().isoformat() + "Z"
        
        flux_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading")
            |> filter(fn: (r) => {filter_clause})
            |> limit(n: {limit})
            |> sort(columns: ["_time"], desc: true)
        '''
        
        result = query_api.query(flux_query)
        
        readings = []
        for table in result:
            for record in table.records:
                readings.append({
                    "timestamp": record.get_time().isoformat(),
                    "mac_address": record.values.get("mac_address"),
                    "epc": record.values.get("epc"),
                    "antenna": int(record.values.get("antenna", 0)),
                    "rssi": float(record.values.get("_value", 0))
                })
        
        return readings
        
    except Exception as e:
        logger.error(f"Erro ao consultar readings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/devices", response_model=List[Device])
async def get_devices():
    """Obtém lista de dispositivos registrados"""
    try:
        cursor = postgres_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT mac_address, device_name, location, 
                   last_seen::text, status
            FROM devices
            ORDER BY last_seen DESC
        """)
        devices = cursor.fetchall()
        cursor.close()
        return devices
    except Exception as e:
        logger.error(f"Erro ao consultar devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics", response_model=Statistics)
async def get_statistics(
    mac_address: Optional[str] = None,
    hours: int = Query(default=24, le=168)  # Max 7 days
):
    """
    Obtém estatísticas das leituras RFID
    
    - **mac_address**: Filtrar por dispositivo específico
    - **hours**: Período em horas (padrão 24h, máximo 168h/7dias)
    """
    try:
        query_api = influx_client.query_api()
        
        start_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
        stop_time = datetime.utcnow().isoformat() + "Z"
        
        mac_filter = f'and r["mac_address"] == "{mac_address}"' if mac_address else ""
        
        # Total de leituras
        flux_query_total = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading" {mac_filter})
            |> count()
        '''
        
        result = query_api.query(flux_query_total)
        total_readings = 0
        if result and len(result) > 0 and len(result[0].records) > 0:
            total_readings = result[0].records[0].get_value()
        
        # EPCs únicos
        flux_query_epcs = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading" {mac_filter})
            |> distinct(column: "epc")
            |> count()
        '''
        
        result = query_api.query(flux_query_epcs)
        unique_epcs = 0
        if result and len(result) > 0 and len(result[0].records) > 0:
            unique_epcs = result[0].records[0].get_value()
        
        # Dispositivos únicos
        flux_query_devices = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading")
            |> distinct(column: "mac_address")
            |> count()
        '''
        
        result = query_api.query(flux_query_devices)
        unique_devices = 0
        if result and len(result) > 0 and len(result[0].records) > 0:
            unique_devices = result[0].records[0].get_value()
        
        # Por dispositivo
        flux_query_by_device = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading")
            |> group(columns: ["mac_address"])
            |> count()
        '''
        
        result = query_api.query(flux_query_by_device)
        by_device = {}
        for table in result:
            for record in table.records:
                mac = record.values.get("mac_address")
                count = record.get_value()
                by_device[mac] = count
        
        # Por antena
        flux_query_by_antenna = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "rfid_reading" {mac_filter})
            |> group(columns: ["antenna"])
            |> count()
        '''
        
        result = query_api.query(flux_query_by_antenna)
        by_antenna = {}
        for table in result:
            for record in table.records:
                ant = record.values.get("antenna")
                count = record.get_value()
                by_antenna[ant] = count
        
        return {
            "total_readings": total_readings,
            "unique_epcs": unique_epcs,
            "unique_devices": unique_devices,
            "time_range": f"Last {hours} hours",
            "by_device": by_device,
            "by_antenna": by_antenna
        }
        
    except Exception as e:
        logger.error(f"Erro ao calcular estatísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    influx_status = "ok" if influx_client else "error"
    postgres_status = "ok" if postgres_conn else "error"
    
    return {
        "status": "healthy" if influx_status == "ok" and postgres_status == "ok" else "degraded",
        "influxdb": influx_status,
        "postgresql": postgres_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
