#!/usr/bin/env python3
"""
RFID Local Agent - Runs on Raspberry Pi
NO .env file - All configuration from cloud
"""
import os
import sys
import time
import json
import signal
import hashlib
import logging
import threading
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

import requests
import pika

# ==================== CONSTANTS ====================
DEVICE_ID_FILE = "/etc/rfid/device_id"
CONFIG_CACHE_FILE = "/var/cache/rfid/config.enc"
READINGS_CACHE_FILE = "/var/cache/rfid/readings.json"
LOG_FILE = "/var/log/rfid/agent.log"
RFID_LOG_FILE = "/var/log/rfid/cm710-4.log"

# Cloud API URL - ONLY hardcoded value allowed
CLOUD_API_URL = os.environ.get('RFID_CLOUD_URL', 'https://your-cloud-server.com')

# ==================== LOGGING ====================
def setup_logging():
    log_dir = Path(LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()


# ==================== DATA CLASSES ====================
@dataclass
class DeviceConfig:
    rabbitmq_host: str
    rabbitmq_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    rabbitmq_vhost: str
    queue_prefix: str
    log_level: str
    heartbeat_interval: int
    cache_ttl: int
    offline_mode_enabled: bool
    max_offline_readings: int
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceConfig':
        return cls(
            rabbitmq_host=data.get('rabbitmq_host', 'localhost'),
            rabbitmq_port=data.get('rabbitmq_port', 5672),
            rabbitmq_user=data.get('rabbitmq_user', ''),
            rabbitmq_password=data.get('rabbitmq_password', ''),
            rabbitmq_vhost=data.get('rabbitmq_vhost', '/'),
            queue_prefix=data.get('queue_prefix', 'rfid_'),
            log_level=data.get('log_level', 'INFO'),
            heartbeat_interval=data.get('heartbeat_interval', 60),
            cache_ttl=data.get('cache_ttl', 300),
            offline_mode_enabled=data.get('offline_mode_enabled', True),
            max_offline_readings=data.get('max_offline_readings', 10000)
        )


# ==================== DEVICE AGENT ====================
class RFIDDeviceAgent:
    """
    Main agent running on Raspberry Pi.
    Handles:
    - Authentication with cloud
    - Configuration fetching
    - RFID log monitoring
    - RabbitMQ publishing
    - Offline caching
    - Heartbeat reporting
    """
    
    def __init__(self, cloud_url: str):
        self.cloud_url = cloud_url.rstrip('/')
        self.device_id: Optional[str] = None
        self.mac_address: Optional[str] = None
        self.access_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.config: Optional[DeviceConfig] = None
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.queue_name: Optional[str] = None
        self.running = True
        self.offline_mode = False
        self.cached_readings = []
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info("🛑 Shutdown signal received")
        self.running = False
    
    def get_mac_address(self) -> str:
        """Get device MAC address"""
        try:
            # Try eth0 first, then wlan0
            for interface in ['eth0', 'wlan0', 'enp0s3']:
                path = f'/sys/class/net/{interface}/address'
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return f.read().strip().upper()
            
            # Fallback to uuid
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) 
                          for i in range(0, 48, 8)][::-1]).upper()
            return mac
        except Exception as e:
            logger.error(f"Failed to get MAC address: {e}")
            raise
    
    def load_device_id(self) -> str:
        """Load device_id from local file"""
        try:
            device_id_path = Path(DEVICE_ID_FILE)
            if device_id_path.exists():
                return device_id_path.read_text().strip()
            else:
                raise FileNotFoundError(f"Device ID not found at {DEVICE_ID_FILE}")
        except Exception as e:
            logger.error(f"Failed to load device ID: {e}")
            raise
    
    def authenticate(self) -> bool:
        """Authenticate with cloud and get JWT token"""
        try:
            logger.info("🔐 Authenticating with cloud...")
            
            response = requests.post(
                f"{self.cloud_url}/api/devices/authenticate",
                json={
                    "device_id": self.device_id,
                    "mac_address": self.mac_address
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                expires_in = data['expires_in']
                self.token_expires = datetime.now(timezone.utc) + \
                    __import__('datetime').timedelta(seconds=expires_in - 300)  # 5min margin
                logger.info(f"✅ Authentication successful (expires in {expires_in}s)")
                return True
            else:
                logger.error(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Authentication request failed: {e}")
            return False
    
    def refresh_token(self) -> bool:
        """Refresh JWT token before expiration"""
        try:
            logger.info("🔄 Refreshing token...")
            
            response = requests.post(
                f"{self.cloud_url}/api/devices/refresh-token",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data['access_token']
                expires_in = data['expires_in']
                self.token_expires = datetime.now(timezone.utc) + \
                    __import__('datetime').timedelta(seconds=expires_in - 300)
                logger.info("✅ Token refreshed")
                return True
            else:
                logger.warning(f"Token refresh failed: {response.status_code}")
                return self.authenticate()  # Full re-auth
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    def fetch_config(self) -> bool:
        """Fetch configuration from cloud"""
        try:
            logger.info("📥 Fetching configuration from cloud...")
            
            response = requests.get(
                f"{self.cloud_url}/api/config",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                config_data = response.json()
                self.config = DeviceConfig.from_dict(config_data)
                
                # Cache config (encrypted in production)
                self._cache_config(config_data)
                
                logger.info("✅ Configuration received:")
                logger.info(f"   RabbitMQ: {self.config.rabbitmq_host}:{self.config.rabbitmq_port}")
                logger.info(f"   Log Level: {self.config.log_level}")
                logger.info(f"   Offline Mode: {self.config.offline_mode_enabled}")
                return True
            else:
                logger.error(f"❌ Config fetch failed: {response.status_code}")
                return self._load_cached_config()
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Cloud unreachable, using cached config: {e}")
            return self._load_cached_config()
    
    def _cache_config(self, config_data: dict):
        """Cache configuration locally (for offline mode)"""
        try:
            cache_dir = Path(CONFIG_CACHE_FILE).parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # In production, encrypt this data
            cache_data = {
                "config": config_data,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "device_id": self.device_id
            }
            
            with open(CONFIG_CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            
            logger.debug("Config cached locally")
        except Exception as e:
            logger.warning(f"Failed to cache config: {e}")
    
    def _load_cached_config(self) -> bool:
        """Load cached configuration for offline mode"""
        try:
            if not os.path.exists(CONFIG_CACHE_FILE):
                logger.error("No cached config available")
                return False
            
            with open(CONFIG_CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            # Check cache TTL
            cached_at = datetime.fromisoformat(cache_data['cached_at'].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - cached_at).total_seconds()
            
            if age > 86400:  # 24h max cache
                logger.warning("⚠️ Cached config is too old, but using anyway")
            
            self.config = DeviceConfig.from_dict(cache_data['config'])
            self.offline_mode = True
            logger.info(f"📦 Using cached config (age: {int(age/3600)}h)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load cached config: {e}")
            return False
    
    def connect_rabbitmq(self) -> bool:
        """Connect to RabbitMQ server"""
        try:
            logger.info(f"🐰 Connecting to RabbitMQ: {self.config.rabbitmq_host}...")
            
            credentials = pika.PlainCredentials(
                self.config.rabbitmq_user,
                self.config.rabbitmq_password
            )
            
            parameters = pika.ConnectionParameters(
                host=self.config.rabbitmq_host,
                port=self.config.rabbitmq_port,
                virtual_host=self.config.rabbitmq_vhost,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300,
                connection_attempts=3,
                retry_delay=5
            )
            
            self.rabbitmq_connection = pika.BlockingConnection(parameters)
            self.rabbitmq_channel = self.rabbitmq_connection.channel()
            
            # Declare queue
            self.queue_name = f"{self.config.queue_prefix}{self.device_id}"
            self.rabbitmq_channel.queue_declare(queue=self.queue_name, durable=True)
            
            logger.info(f"✅ RabbitMQ connected, queue: {self.queue_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ RabbitMQ connection failed: {e}")
            return False
    
    def publish_reading(self, reading: dict) -> bool:
        """Publish RFID reading to RabbitMQ"""
        try:
            if not self.rabbitmq_channel:
                raise Exception("RabbitMQ not connected")
            
            message = json.dumps(reading)
            
            self.rabbitmq_channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            return True
            
        except Exception as e:
            logger.warning(f"Failed to publish reading: {e}")
            self._cache_reading(reading)
            return False
    
    def _cache_reading(self, reading: dict):
        """Cache reading for later sync"""
        if not self.config.offline_mode_enabled:
            return
        
        if len(self.cached_readings) >= self.config.max_offline_readings:
            self.cached_readings.pop(0)  # Remove oldest
        
        self.cached_readings.append(reading)
        self._save_cached_readings()
    
    def _save_cached_readings(self):
        """Save cached readings to disk"""
        try:
            cache_dir = Path(READINGS_CACHE_FILE).parent
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            with open(READINGS_CACHE_FILE, 'w') as f:
                json.dump(self.cached_readings, f)
        except Exception as e:
            logger.warning(f"Failed to save cached readings: {e}")
    
    def _load_cached_readings(self):
        """Load cached readings from disk"""
        try:
            if os.path.exists(READINGS_CACHE_FILE):
                with open(READINGS_CACHE_FILE, 'r') as f:
                    self.cached_readings = json.load(f)
                logger.info(f"📦 Loaded {len(self.cached_readings)} cached readings")
        except Exception as e:
            logger.warning(f"Failed to load cached readings: {e}")
    
    def sync_cached_readings(self):
        """Sync cached readings when back online"""
        if not self.cached_readings:
            return
        
        logger.info(f"🔄 Syncing {len(self.cached_readings)} cached readings...")
        
        synced = 0
        failed = []
        
        for reading in self.cached_readings:
            if self.publish_reading(reading):
                synced += 1
            else:
                failed.append(reading)
        
        self.cached_readings = failed
        self._save_cached_readings()
        
        logger.info(f"✅ Synced {synced} readings, {len(failed)} remaining")
    
    def send_heartbeat(self):
        """Send heartbeat to cloud"""
        try:
            # Get system stats
            cpu_temp = self._get_cpu_temp()
            memory_usage = self._get_memory_usage()
            disk_usage = self._get_disk_usage()
            uptime = self._get_uptime()
            
            response = requests.post(
                f"{self.cloud_url}/api/heartbeat",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "device_id": self.device_id,
                    "status": "online",
                    "cpu_temp": cpu_temp,
                    "memory_usage": memory_usage,
                    "disk_usage": disk_usage,
                    "uptime": uptime
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug("💓 Heartbeat sent")
                self.offline_mode = False
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
            self.offline_mode = True
    
    def _get_cpu_temp(self) -> Optional[float]:
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                return float(f.read().strip()) / 1000
        except (FileNotFoundError, ValueError, OSError):
            return None
    
    def _get_memory_usage(self) -> Optional[float]:
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            total = int([line for line in lines if 'MemTotal' in line][0].split()[1])
            available = int([line for line in lines if 'MemAvailable' in line][0].split()[1])
            return round((1 - available/total) * 100, 1)
        except (FileNotFoundError, ValueError, IndexError, OSError):
            return None
    
    def _get_disk_usage(self) -> Optional[float]:
        try:
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            return round((1 - free/total) * 100, 1)
        except (OSError, ZeroDivisionError):
            return None
    
    def _get_uptime(self) -> Optional[int]:
        try:
            with open('/proc/uptime', 'r') as f:
                return int(float(f.read().split()[0]))
        except (FileNotFoundError, ValueError, OSError):
            return None
    
    def parse_rfid_log_line(self, line: str) -> Optional[dict]:
        """Parse RFID log line"""
        try:
            parts = line.strip().split()
            if len(parts) >= 6:
                return {
                    "timestamp": f"{parts[0]} {parts[1]}",
                    "device_id": self.device_id,
                    "mac_address": parts[2],
                    "epc": parts[3],
                    "antenna": int(parts[4]),
                    "rssi": float(parts[5])
                }
        except Exception as e:
            logger.debug(f"Failed to parse line: {line} - {e}")
        return None
    
    def monitor_rfid_log(self):
        """Monitor RFID log file and publish readings"""
        logger.info(f"📖 Monitoring RFID log: {RFID_LOG_FILE}")
        
        # Wait for log file
        while not os.path.exists(RFID_LOG_FILE) and self.running:
            logger.info("⏳ Waiting for RFID log file...")
            time.sleep(5)
        
        if not self.running:
            return
        
        with open(RFID_LOG_FILE, 'r') as f:
            # Seek to end
            f.seek(0, 2)
            
            while self.running:
                line = f.readline()
                
                if line:
                    reading = self.parse_rfid_log_line(line)
                    if reading:
                        success = self.publish_reading(reading)
                        status = "✅" if success else "📦 cached"
                        logger.info(f"{status} EPC={reading['epc']} ANT={reading['antenna']} RSSI={reading['rssi']}")
                else:
                    time.sleep(0.1)
    
    def heartbeat_loop(self):
        """Background thread for heartbeat and maintenance"""
        last_heartbeat = 0
        last_token_check = 0
        last_sync = 0
        
        while self.running:
            now = time.time()
            
            # Heartbeat
            if now - last_heartbeat >= self.config.heartbeat_interval:
                self.send_heartbeat()
                last_heartbeat = now
            
            # Token refresh check
            if now - last_token_check >= 300:  # Every 5 min
                if self.token_expires and datetime.now(timezone.utc) >= self.token_expires:
                    self.refresh_token()
                last_token_check = now
            
            # Sync cached readings
            if now - last_sync >= 60 and self.cached_readings:
                if not self.offline_mode:
                    self.sync_cached_readings()
                last_sync = now
            
            # Reconnect RabbitMQ if needed
            if self.rabbitmq_connection and self.rabbitmq_connection.is_closed:
                logger.warning("🔄 RabbitMQ disconnected, reconnecting...")
                self.connect_rabbitmq()
            
            time.sleep(10)
    
    def run(self):
        """Main agent loop"""
        logger.info("=" * 60)
        logger.info("🚀 RFID Device Agent Starting")
        logger.info(f"   Cloud URL: {self.cloud_url}")
        logger.info("=" * 60)
        
        # Load device ID and MAC
        try:
            self.device_id = self.load_device_id()
            self.mac_address = self.get_mac_address()
            logger.info(f"   Device ID: {self.device_id}")
            logger.info(f"   MAC Address: {self.mac_address}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            logger.error("   Run bootstrap.sh first to provision this device!")
            sys.exit(1)
        
        # Authenticate
        if not self.authenticate():
            logger.warning("⚠️ Authentication failed, trying cached config...")
            if not self._load_cached_config():
                logger.error("❌ Cannot start without config")
                sys.exit(1)
        else:
            # Fetch config
            if not self.fetch_config():
                logger.error("❌ Failed to get configuration")
                sys.exit(1)
        
        # Load any cached readings
        self._load_cached_readings()
        
        # Connect to RabbitMQ
        if not self.connect_rabbitmq():
            if self.config.offline_mode_enabled:
                logger.warning("⚠️ RabbitMQ unavailable, running in offline mode")
                self.offline_mode = True
            else:
                logger.error("❌ Cannot connect to RabbitMQ and offline mode disabled")
                sys.exit(1)
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        # Monitor RFID log
        try:
            self.monitor_rfid_log()
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        logger.info("🛑 Shutting down...")
        self.running = False
        
        # Save cached readings
        self._save_cached_readings()
        
        # Close RabbitMQ
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            try:
                self.rabbitmq_connection.close()
            except Exception as e:
                logger.debug(f"Error closing RabbitMQ connection: {e}")
        
        logger.info("👋 Agent stopped")


def main():
    cloud_url = os.environ.get('RFID_CLOUD_URL')
    
    if not cloud_url:
        # Try to read from bootstrap config
        try:
            with open('/etc/rfid/cloud_url', 'r') as f:
                cloud_url = f.read().strip()
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Error reading cloud_url file: {e}")
    
    if not cloud_url:
        logger.error("RFID_CLOUD_URL not set and /etc/rfid/cloud_url not found")
        logger.error("Run bootstrap.sh first to provision this device!")
        sys.exit(1)
    
    agent = RFIDDeviceAgent(cloud_url)
    agent.run()


if __name__ == "__main__":
    main()
