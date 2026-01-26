#!/usr/bin/env python3
"""
RabbitMQ Producer - Monitora log RFID e publica mensagens
Versão atualizada com métricas Prometheus
"""
import os
import time
import json
import pika
from datetime import datetime
import logging
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações do ambiente
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'rfid_user')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'rfid_password')
LOG_FILE = os.environ.get('LOG_FILE', '/logs/cm710-4.log')
PROMETHEUS_ENABLED = os.environ.get('PROMETHEUS_ENABLED', 'false').lower() == 'true'
METRICS_PORT = int(os.environ.get('METRICS_PORT', 9100))

# MAC Address do dispositivo
MAC_ADDRESS = None

# Métricas Prometheus
READINGS_TOTAL = Counter('rfid_readings_total', 'Total RFID readings processed', ['mac_address', 'antenna'])
READINGS_PUBLISHED = Counter('rfid_readings_published_total', 'Total RFID readings published to RabbitMQ', ['mac_address'])
READINGS_FAILED = Counter('rfid_readings_failed_total', 'Total RFID readings failed to publish', ['mac_address'])
RSSI_HISTOGRAM = Histogram('rfid_rssi_dbm', 'RSSI distribution in dBm', ['mac_address', 'antenna'], buckets=[-60, -50, -40, -30, -20, -10, 0])
LAST_READING_TIMESTAMP = Gauge('rfid_last_reading_timestamp', 'Timestamp of last reading', ['mac_address'])
RABBITMQ_CONNECTION_STATUS = Gauge('rfid_rabbitmq_connection_status', 'RabbitMQ connection status (1=connected, 0=disconnected)')


class RFIDProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.last_position = 0
        
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
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                RABBITMQ_CONNECTION_STATUS.set(1)
                logger.info(f"✅ Conectado ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}")
                return True
            except Exception as e:
                RABBITMQ_CONNECTION_STATUS.set(0)
                logger.warning(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        logger.error("❌ Falha ao conectar ao RabbitMQ após múltiplas tentativas")
        return False
    
    def declare_queue(self, mac_address):
        """Declara fila nomeada pelo MAC"""
        queue_name = f"queue_{mac_address.replace(':', '_')}"
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            logger.info(f"✅ Fila '{queue_name}' declarada")
            return queue_name
        except Exception as e:
            logger.error(f"❌ Erro ao declarar fila: {e}")
            return None
    
    def publish_reading(self, queue_name, reading_data):
        """Publica leitura no RabbitMQ"""
        try:
            message = json.dumps(reading_data)
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            READINGS_PUBLISHED.labels(mac_address=reading_data['mac_address']).inc()
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao publicar mensagem: {e}")
            READINGS_FAILED.labels(mac_address=reading_data.get('mac_address', 'unknown')).inc()
            RABBITMQ_CONNECTION_STATUS.set(0)
            if not self.connection or self.connection.is_closed:
                self.connect_rabbitmq()
            return False
    
    def parse_log_line(self, line):
        """Parse linha do log RFID"""
        try:
            parts = line.strip().split()
            if len(parts) >= 6:
                timestamp_str = f"{parts[0]} {parts[1]}"
                mac = parts[2]
                epc = parts[3]
                antenna = int(parts[4])
                rssi = float(parts[5])
                
                return {
                    "timestamp": timestamp_str,
                    "mac_address": mac,
                    "epc": epc,
                    "antenna": antenna,
                    "rssi": rssi,
                    "processed_at": datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"Erro ao parsear linha: {line} - {e}")
        return None
    
    def monitor_log_file(self):
        """Monitora arquivo de log e processa novas linhas"""
        global MAC_ADDRESS
        queue_name = None
        
        logger.info(f"📖 Monitorando arquivo: {LOG_FILE}")
        
        while not os.path.exists(LOG_FILE):
            logger.info(f"⏳ Aguardando arquivo {LOG_FILE}...")
            time.sleep(5)
        
        with open(LOG_FILE, 'r') as f:
            f.seek(0, 2)
            self.last_position = f.tell()
            
            logger.info("🚀 Iniciando monitoramento em tempo real...")
            
            while True:
                try:
                    line = f.readline()
                    
                    if line:
                        reading = self.parse_log_line(line)
                        
                        if reading:
                            mac = reading['mac_address']
                            antenna = str(reading['antenna'])
                            
                            if MAC_ADDRESS is None:
                                MAC_ADDRESS = mac
                                queue_name = self.declare_queue(MAC_ADDRESS)
                                logger.info(f"📡 MAC detectado: {MAC_ADDRESS}")
                            
                            # Métricas
                            READINGS_TOTAL.labels(mac_address=mac, antenna=antenna).inc()
                            RSSI_HISTOGRAM.labels(mac_address=mac, antenna=antenna).observe(reading['rssi'])
                            LAST_READING_TIMESTAMP.labels(mac_address=mac).set(time.time())
                            
                            # Publica no RabbitMQ
                            if queue_name:
                                published = self.publish_reading(queue_name, reading)
                                status = "✅ RabbitMQ" if published else "❌ RabbitMQ"
                            else:
                                status = "⚠️ No queue"
                            
                            logger.info(f"📊 EPC={reading['epc']} ANT={reading['antenna']} RSSI={reading['rssi']:.1f} | {status}")
                    else:
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"❌ Erro no loop principal: {e}")
                    time.sleep(1)
    
    def run(self):
        """Executa o producer"""
        logger.info("🚀 Iniciando RFID Producer...")
        
        # Inicia servidor de métricas Prometheus
        if PROMETHEUS_ENABLED:
            start_http_server(METRICS_PORT)
            logger.info(f"📈 Métricas Prometheus em http://0.0.0.0:{METRICS_PORT}/metrics")
        
        # Conecta ao RabbitMQ
        rabbitmq_ok = self.connect_rabbitmq()
        
        if not rabbitmq_ok:
            logger.warning("⚠️ RabbitMQ offline - tentará reconectar")
        
        # Monitora log
        try:
            self.monitor_log_file()
        except KeyboardInterrupt:
            logger.info("\n🛑 Encerrando producer...")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()


if __name__ == "__main__":
    producer = RFIDProducer()
    producer.run()
