#!/usr/bin/env python3
"""
RabbitMQ Producer - Monitora log RFID e publica mensagens
"""
import os
import time
import json
import pika
from datetime import datetime
from pymongo import MongoClient
import logging

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
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'rfid_db')
LOG_FILE = os.environ.get('LOG_FILE', '/logs/cm710-4.log')

# MAC Address do dispositivo (será extraído do log)
MAC_ADDRESS = None


class RFIDProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.mongo_client = None
        self.db = None
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
                logger.info(f"✅ Conectado ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Tentativa {attempt + 1}/{max_retries} falhou: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        logger.error("❌ Falha ao conectar ao RabbitMQ após múltiplas tentativas")
        return False
    
    def connect_mongodb(self):
        """Conecta ao MongoDB"""
        try:
            self.mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            self.db = self.mongo_client[DB_NAME]
            # Testa conexão
            self.db.admin.command('ping')
            logger.info(f"✅ Conectado ao MongoDB: {MONGO_URL}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar MongoDB: {e}")
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
                    delivery_mode=2,  # Mensagem persistente
                    content_type='application/json'
                )
            )
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao publicar mensagem: {e}")
            # Tenta reconectar
            if not self.connection or self.connection.is_closed:
                self.connect_rabbitmq()
            return False
    
    def save_to_mongodb(self, reading_data):
        """Salva leitura no MongoDB local (backup)"""
        try:
            collection = self.db.rfid_readings
            collection.insert_one(reading_data)
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar no MongoDB: {e}")
            return False
    
    def parse_log_line(self, line):
        """Parse linha do log RFID"""
        try:
            parts = line.strip().split()
            if len(parts) >= 5:
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
        
        # Aguarda arquivo existir
        while not os.path.exists(LOG_FILE):
            logger.info(f"⏳ Aguardando arquivo {LOG_FILE}...")
            time.sleep(5)
        
        with open(LOG_FILE, 'r') as f:
            # Move para o final do arquivo
            f.seek(0, 2)
            self.last_position = f.tell()
            
            logger.info("🚀 Iniciando monitoramento em tempo real...")
            
            while True:
                try:
                    # Verifica novas linhas
                    line = f.readline()
                    
                    if line:
                        reading = self.parse_log_line(line)
                        
                        if reading:
                            # Primeira leitura - extrai MAC e cria fila
                            if MAC_ADDRESS is None:
                                MAC_ADDRESS = reading['mac_address']
                                queue_name = self.declare_queue(MAC_ADDRESS)
                                logger.info(f"📡 MAC detectado: {MAC_ADDRESS}")
                            
                            # Salva no MongoDB (backup local)
                            mongo_saved = self.save_to_mongodb(reading)
                            
                            # Publica no RabbitMQ (nuvem)
                            rabbitmq_published = False
                            if queue_name:
                                rabbitmq_published = self.publish_reading(queue_name, reading)
                            
                            # Log status
                            status = "✅ MongoDB" if mongo_saved else "❌ MongoDB"
                            status += " | ✅ RabbitMQ" if rabbitmq_published else " | ⚠️ RabbitMQ (offline)"
                            logger.info(f"📊 EPC={reading['epc']} ANT={reading['antenna']} RSSI={reading['rssi']} | {status}")
                    else:
                        # Sem novas linhas, aguarda
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"❌ Erro no loop principal: {e}")
                    time.sleep(1)
    
    def run(self):
        """Executa o producer"""
        logger.info("🚀 Iniciando RFID Producer...")
        
        # Conecta serviços
        rabbitmq_ok = self.connect_rabbitmq()
        mongodb_ok = self.connect_mongodb()
        
        if not mongodb_ok:
            logger.warning("⚠️ MongoDB offline - apenas RabbitMQ será usado")
        
        if not rabbitmq_ok:
            logger.warning("⚠️ RabbitMQ offline - apenas MongoDB será usado")
        
        # Monitora log
        try:
            self.monitor_log_file()
        except KeyboardInterrupt:
            logger.info("\n🛑 Encerrando producer...")
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            if self.mongo_client:
                self.mongo_client.close()


if __name__ == "__main__":
    producer = RFIDProducer()
    producer.run()
