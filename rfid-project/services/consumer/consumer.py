#!/usr/bin/env python3
"""
RFID Cloud Consumer - Consome de múltiplos Raspberry Pis e armazena no InfluxDB
Versão atualizada com métricas Prometheus
"""
import os
import time
import json
import pika
import logging
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import psycopg2
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Configuração de logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações do ambiente
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'rfid_user')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'rfid_password')

INFLUXDB_URL = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
INFLUXDB_TOKEN = os.environ.get('INFLUXDB_TOKEN')
INFLUXDB_ORG = os.environ.get('INFLUXDB_ORG', 'rfid_org')
INFLUXDB_BUCKET = os.environ.get('INFLUXDB_BUCKET', 'rfid_readings')

POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.environ.get('POSTGRES_PORT', 5432))
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'rfid_user')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'rfid_password')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'rfid_metadata')

DEVICE_MACS = os.environ.get('DEVICE_MACS', '').split(',')
DEVICE_MACS = [mac.strip() for mac in DEVICE_MACS if mac.strip()]

PROMETHEUS_ENABLED = os.environ.get('PROMETHEUS_ENABLED', 'false').lower() == 'true'
METRICS_PORT = int(os.environ.get('METRICS_PORT', 9101))

# Métricas Prometheus
READINGS_CONSUMED = Counter('rfid_consumer_readings_total', 'Total RFID readings consumed', ['mac_address', 'antenna'])
READINGS_SAVED = Counter('rfid_consumer_readings_saved_total', 'Total RFID readings saved to InfluxDB', ['mac_address'])
READINGS_ERRORS = Counter('rfid_consumer_errors_total', 'Total errors processing readings', ['error_type'])
PROCESSING_TIME = Histogram('rfid_consumer_processing_seconds', 'Time to process a reading', buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5])
DEVICES_ONLINE = Gauge('rfid_devices_online', 'Number of devices currently online')
QUEUE_SIZE = Gauge('rfid_queue_size', 'Current queue size', ['queue_name'])
RSSI_GAUGE = Gauge('rfid_current_rssi', 'Current RSSI value', ['mac_address', 'antenna'])


class RFIDCloudConsumer:
    def __init__(self):
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.influxdb_client = None
        self.influxdb_write_api = None
        self.postgres_conn = None
        self.postgres_cursor = None
        self.stats = {
            'total_processed': 0,
            'total_errors': 0,
            'by_device': {}
        }
        
    def connect_rabbitmq(self):
        """Conecta ao RabbitMQ com retry"""
        max_retries = 10
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
                parameters = pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                self.rabbitmq_connection = pika.BlockingConnection(parameters)
                self.rabbitmq_channel = self.rabbitmq_connection.channel()
                logger.info(f"✅ Conectado ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                READINGS_ERRORS.labels(error_type='rabbitmq_connection').inc()
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        logger.error("❌ Falha ao conectar ao RabbitMQ")
        return False
    
    def connect_influxdb(self):
        """Conecta ao InfluxDB"""
        try:
            self.influxdb_client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            self.influxdb_write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
            health = self.influxdb_client.health()
            logger.info(f"✅ Conectado ao InfluxDB: {health.status}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar InfluxDB: {e}")
            READINGS_ERRORS.labels(error_type='influxdb_connection').inc()
            return False
    
    def connect_postgres(self):
        """Conecta ao PostgreSQL"""
        try:
            self.postgres_conn = psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                dbname=POSTGRES_DB
            )
            self.postgres_cursor = self.postgres_conn.cursor()
            
            self.postgres_cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    mac_address VARCHAR(17) PRIMARY KEY,
                    device_name VARCHAR(100),
                    location VARCHAR(100),
                    last_seen TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.postgres_cursor.execute("""
                CREATE TABLE IF NOT EXISTS epc_registry (
                    epc VARCHAR(24) PRIMARY KEY,
                    description TEXT,
                    category VARCHAR(50),
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_reads INT DEFAULT 1
                )
            """)
            
            self.postgres_conn.commit()
            logger.info("✅ Conectado ao PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar PostgreSQL: {e}")
            READINGS_ERRORS.labels(error_type='postgres_connection').inc()
            return False
    
    def save_to_influxdb(self, reading):
        """Salva leitura no InfluxDB"""
        try:
            timestamp = datetime.fromisoformat(reading['timestamp'].replace(' ', 'T'))
            
            point = Point("rfid_reading") \
                .tag("mac_address", reading['mac_address']) \
                .tag("epc", reading['epc']) \
                .tag("antenna", str(reading['antenna'])) \
                .field("rssi", float(reading['rssi'])) \
                .time(timestamp)
            
            self.influxdb_write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            READINGS_SAVED.labels(mac_address=reading['mac_address']).inc()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar no InfluxDB: {e}")
            READINGS_ERRORS.labels(error_type='influxdb_write').inc()
            return False
    
    def update_device_metadata(self, mac_address, epc):
        """Atualiza metadata do dispositivo e EPC"""
        try:
            # Atualiza dispositivo
            self.postgres_cursor.execute("""
                INSERT INTO devices (mac_address, last_seen, status)
                VALUES (%s, CURRENT_TIMESTAMP, 'online')
                ON CONFLICT (mac_address)
                DO UPDATE SET 
                    last_seen = CURRENT_TIMESTAMP,
                    status = 'online'
            """, (mac_address,))
            
            # Atualiza EPC
            self.postgres_cursor.execute("""
                INSERT INTO epc_registry (epc, last_seen, total_reads)
                VALUES (%s, CURRENT_TIMESTAMP, 1)
                ON CONFLICT (epc)
                DO UPDATE SET 
                    last_seen = CURRENT_TIMESTAMP,
                    total_reads = epc_registry.total_reads + 1
            """, (epc,))
            
            self.postgres_conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar metadata: {e}")
            READINGS_ERRORS.labels(error_type='postgres_write').inc()
            return False
    
    def update_online_devices_count(self):
        """Atualiza contagem de dispositivos online"""
        try:
            self.postgres_cursor.execute("""
                SELECT COUNT(*) FROM devices 
                WHERE status = 'online' 
                AND last_seen > NOW() - INTERVAL '5 minutes'
            """)
            count = self.postgres_cursor.fetchone()[0]
            DEVICES_ONLINE.set(count)
        except:
            pass
    
    def mark_devices_offline(self):
        """Marca dispositivos como offline"""
        try:
            self.postgres_cursor.execute("""
                UPDATE devices
                SET status = 'offline'
                WHERE last_seen < NOW() - INTERVAL '5 minutes'
                AND status = 'online'
            """)
            affected = self.postgres_cursor.rowcount
            if affected > 0:
                self.postgres_conn.commit()
                logger.warning(f"⚠️ {affected} dispositivo(s) marcado(s) como OFFLINE")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao verificar devices offline: {e}")
            return False
    
    def process_reading(self, ch, method, properties, body):
        """Callback para processar mensagens"""
        start_time = time.time()
        
        try:
            reading = json.loads(body)
            
            mac = reading['mac_address']
            epc = reading['epc']
            rssi = reading['rssi']
            antenna = str(reading['antenna'])
            
            # Métricas
            READINGS_CONSUMED.labels(mac_address=mac, antenna=antenna).inc()
            RSSI_GAUGE.labels(mac_address=mac, antenna=antenna).set(rssi)
            
            logger.info(f"📡 [{mac}] EPC={epc} ANT={antenna} RSSI={rssi:.1f} dBm")
            
            # Salvar no InfluxDB
            if self.save_to_influxdb(reading):
                self.update_device_metadata(mac, epc)
                
                self.stats['total_processed'] += 1
                if mac not in self.stats['by_device']:
                    self.stats['by_device'][mac] = 0
                self.stats['by_device'][mac] += 1
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
                if self.stats['total_processed'] % 100 == 0:
                    self.log_statistics()
                    self.update_online_devices_count()
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                self.stats['total_errors'] += 1
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            READINGS_ERRORS.labels(error_type='processing').inc()
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            self.stats['total_errors'] += 1
        finally:
            PROCESSING_TIME.observe(time.time() - start_time)
    
    def log_statistics(self):
        """Log estatísticas"""
        logger.info("=" * 60)
        logger.info(f"📊 ESTATÍSTICAS")
        logger.info(f"Total Processado: {self.stats['total_processed']}")
        logger.info(f"Total Erros: {self.stats['total_errors']}")
        logger.info(f"Por Dispositivo:")
        for mac, count in self.stats['by_device'].items():
            logger.info(f"  {mac}: {count} leituras")
        logger.info("=" * 60)
    
    def discover_queues(self):
        """Descobre filas disponíveis"""
        if DEVICE_MACS:
            logger.info(f"📋 Usando lista de MACs configurada: {len(DEVICE_MACS)} dispositivos")
            return DEVICE_MACS
        
        logger.warning("⚠️ DEVICE_MACS não configurado")
        logger.warning("⚠️ Configure DEVICE_MACS no docker-compose.yml")
        return []
    
    def start_consuming(self):
        """Inicia consumo"""
        if not self.connect_rabbitmq():
            return
        
        if not self.connect_influxdb():
            return
        
        if not self.connect_postgres():
            return
        
        macs = self.discover_queues()
        
        if not macs:
            logger.error("❌ Nenhum dispositivo para monitorar!")
            return
        
        for mac in macs:
            queue_name = f"queue_{mac.replace(':', '_')}"
            
            try:
                self.rabbitmq_channel.queue_declare(queue=queue_name, durable=True)
                self.rabbitmq_channel.basic_qos(prefetch_count=10)
                self.rabbitmq_channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self.process_reading,
                    auto_ack=False
                )
                
                logger.info(f"✅ Consumindo fila: {queue_name}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao configurar fila {queue_name}: {e}")
        
        logger.info("🚀 Iniciando consumo de mensagens...")
        logger.info(f"📡 Monitorando {len(macs)} dispositivo(s)")
        
        try:
            self.rabbitmq_channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("\n🛑 Encerrando consumer...")
            self.log_statistics()
            self.rabbitmq_channel.stop_consuming()
        finally:
            if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
                self.rabbitmq_connection.close()
            if self.influxdb_client:
                self.influxdb_client.close()
            if self.postgres_conn:
                self.postgres_cursor.close()
                self.postgres_conn.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 RFID Cloud Consumer - Iniciando")
    logger.info("=" * 60)
    
    # Inicia servidor de métricas
    if PROMETHEUS_ENABLED:
        start_http_server(METRICS_PORT)
        logger.info(f"📈 Métricas Prometheus em http://0.0.0.0:{METRICS_PORT}/metrics")
    
    consumer = RFIDCloudConsumer()
    consumer.start_consuming()
