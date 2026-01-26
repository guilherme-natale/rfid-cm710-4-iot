#!/usr/bin/env python3
"""
RabbitMQ Consumer (Para executar na NUVEM)
Recebe leituras RFID de múltiplos Raspberry Pis e envia para Grafana
"""
import pika
import json
import requests
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configurações (ajustar conforme seu ambiente)
RABBITMQ_HOST = 'raspberry-pi-ip-or-cloud-rabbitmq'  # IP do RabbitMQ
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'rfid_user'
RABBITMQ_PASSWORD = 'rfid_password'
GRAFANA_API = 'http://your-grafana-api/metrics'  # URL da API do Grafana

# Lista de MACs dos Raspberry Pis que você quer monitorar
DEVICE_MACS = [
    'D8:3A:DD:B3:E0:7F',  # Adicionar todos os MACs dos seus dispositivos
    # 'AA:BB:CC:DD:EE:FF',
    # ...
]


class RFIDConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        
    def connect(self):
        """Conecta ao RabbitMQ"""
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
            logger.error(f"❌ Erro ao conectar: {e}")
            return False
    
    def send_to_grafana(self, reading):
        """Envia leitura para Grafana (ou outro sistema)"""
        try:
            # Formato para Grafana - ajustar conforme sua API
            payload = {
                "timestamp": reading['timestamp'],
                "device_mac": reading['mac_address'],
                "epc": reading['epc'],
                "antenna": reading['antenna'],
                "rssi": reading['rssi'],
                "tags": {
                    "device": reading['mac_address'],
                    "location": "warehouse"  # Adicionar metadata conforme necessário
                }
            }
            
            # Enviar para Grafana/InfluxDB/Prometheus
            response = requests.post(GRAFANA_API, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"📊 Enviado para Grafana: EPC={reading['epc']} RSSI={reading['rssi']}")
                return True
            else:
                logger.warning(f"⚠️ Erro ao enviar: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro ao enviar para Grafana: {e}")
            return False
    
    def process_reading(self, ch, method, properties, body):
        """Callback para processar mensagens"""
        try:
            reading = json.loads(body)
            
            logger.info(f"📡 Recebido: MAC={reading['mac_address']} EPC={reading['epc']} RSSI={reading['rssi']}")
            
            # Enviar para Grafana
            self.send_to_grafana(reading)
            
            # Acknowledge da mensagem
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")
            # NACK - mensagem volta para a fila
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def start_consuming(self):
        """Inicia consumo de todas as filas"""
        if not self.connect():
            return
        
        # Conectar em todas as filas (uma por MAC)
        for mac in DEVICE_MACS:
            queue_name = f"queue_{mac.replace(':', '_')}"
            
            try:
                # Declara fila (caso não exista)
                self.channel.queue_declare(queue=queue_name, durable=True)
                
                # Configura consumo
                self.channel.basic_qos(prefetch_count=10)  # Processa 10 mensagens por vez
                self.channel.basic_consume(
                    queue=queue_name,
                    on_message_callback=self.process_reading,
                    auto_ack=False  # Manual acknowledge
                )
                
                logger.info(f"✅ Consumindo fila: {queue_name}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao configurar fila {queue_name}: {e}")
        
        logger.info("🚀 Iniciando consumo de mensagens...")
        logger.info("Pressione CTRL+C para parar")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("\n🛑 Encerrando consumer...")
            self.channel.stop_consuming()
        finally:
            if self.connection and not self.connection.is_closed:
                self.connection.close()


if __name__ == "__main__":
    consumer = RFIDConsumer()
    consumer.start_consuming()
