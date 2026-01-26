#!/bin/bash

# ============================================================
# RASPBERRY PI - SETUP INICIAL (ONE-TIME CONFIGURATION)
# Execute APENAS UMA VEZ antes de entregar ao cliente
# ============================================================

echo "=========================================="
echo "  RFID Raspberry Pi - Setup Inicial"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================
# CONFIGURAÇÕES - EDITE AQUI ANTES DE EXECUTAR
# ============================================================

# IP/Hostname do servidor na nuvem (OBRIGATÓRIO)
CLOUD_SERVER_IP="seu-servidor-cloud.com"

# Credenciais RabbitMQ (manter padrão ou mudar se alterou na nuvem)
RABBITMQ_USER="rfid_user"
RABBITMQ_PASSWORD="rfid_password"

# ============================================================
# NÃO EDITE DAQUI PRA BAIXO
# ============================================================

echo -e "${BLUE}Configurações:${NC}"
echo "  Servidor Cloud: $CLOUD_SERVER_IP"
echo "  RabbitMQ User: $RABBITMQ_USER"
echo ""

# Validar configuração
if [ "$CLOUD_SERVER_IP" == "seu-servidor-cloud.com" ]; then
    echo -e "${RED}❌ ERRO: Configure CLOUD_SERVER_IP no topo deste script!${NC}"
    echo ""
    echo "Edite este arquivo e defina o IP/hostname do servidor cloud:"
    echo "  nano $(basename $0)"
    echo ""
    exit 1
fi

read -p "Confirmar configuração? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelado."
    exit 1
fi

echo ""
echo "=========================================="
echo "  Instalando Dependências"
echo "=========================================="

# Atualizar sistema
echo -e "${YELLOW}Atualizando sistema...${NC}"
sudo apt update && sudo apt upgrade -y

# Instalar dependências
echo -e "${YELLOW}Instalando dependências...${NC}"
sudo apt install -y python3-pip python3-dev git docker.io docker-compose

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER
sudo usermod -aG gpio $USER
sudo usermod -aG dialout $USER

# Instalar bibliotecas Python
pip3 install RPi.GPIO pyserial pymongo pika python-dotenv --user

echo -e "${GREEN}✅ Dependências instaladas${NC}"

echo ""
echo "=========================================="
echo "  Configurando Docker Compose"
echo "=========================================="

# Criar docker-compose.yml SEM .env
cat > /app/docker/docker-compose.yml <<EOF
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    container_name: rfid_rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: unless-stopped
    networks:
      - rfid_network

  producer:
    build:
      context: ../producer
      dockerfile: Dockerfile
    container_name: rfid_producer
    depends_on:
      - rabbitmq
    privileged: true
    devices:
      - "/dev/ttyUSB0:/dev/ttyUSB0"
      - "/dev/ttyACM0:/dev/ttyACM0"
    volumes:
      - /home/cpcon/cm710-4:/logs
      - ../producer:/app
    environment:
      # RabbitMQ Local (para backup offline)
      RABBITMQ_LOCAL_HOST: rabbitmq
      RABBITMQ_LOCAL_PORT: 5672
      RABBITMQ_LOCAL_USER: ${RABBITMQ_USER}
      RABBITMQ_LOCAL_PASSWORD: ${RABBITMQ_PASSWORD}
      
      # RabbitMQ Cloud (principal)
      RABBITMQ_CLOUD_HOST: ${CLOUD_SERVER_IP}
      RABBITMQ_CLOUD_PORT: 5672
      RABBITMQ_CLOUD_USER: ${RABBITMQ_USER}
      RABBITMQ_CLOUD_PASSWORD: ${RABBITMQ_PASSWORD}
      
      # MongoDB Local (backup)
      MONGO_URL: mongodb://host.docker.internal:27017
      DB_NAME: rfid_db
      
      # Logs
      LOG_FILE: /logs/cm710-4.log
      LOG_LEVEL: INFO
    restart: unless-stopped
    networks:
      - rfid_network
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  rfid_network:
    driver: bridge

volumes:
  rabbitmq_data:
EOF

echo -e "${GREEN}✅ docker-compose.yml configurado${NC}"

echo ""
echo "=========================================="
echo "  Atualizando Producer"
echo "=========================================="

# Atualizar producer.py para dual-mode (local + cloud)
cat > /app/producer/producer.py <<'PRODUCER_EOF'
#!/usr/bin/env python3
"""
RFID Producer - Dual Mode (Local + Cloud)
Publica em RabbitMQ local E cloud (se disponível)
"""
import os
import time
import json
import pika
from datetime import datetime
from pymongo import MongoClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configs
LOG_FILE = os.environ.get('LOG_FILE', '/logs/cm710-4.log')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'rfid_db')

# RabbitMQ Local (sempre disponível)
RABBITMQ_LOCAL_HOST = os.environ.get('RABBITMQ_LOCAL_HOST', 'localhost')
RABBITMQ_LOCAL_PORT = int(os.environ.get('RABBITMQ_LOCAL_PORT', 5672))
RABBITMQ_LOCAL_USER = os.environ.get('RABBITMQ_LOCAL_USER', 'rfid_user')
RABBITMQ_LOCAL_PASSWORD = os.environ.get('RABBITMQ_LOCAL_PASSWORD', 'rfid_password')

# RabbitMQ Cloud (pode estar offline)
RABBITMQ_CLOUD_HOST = os.environ.get('RABBITMQ_CLOUD_HOST')
RABBITMQ_CLOUD_PORT = int(os.environ.get('RABBITMQ_CLOUD_PORT', 5672))
RABBITMQ_CLOUD_USER = os.environ.get('RABBITMQ_CLOUD_USER', 'rfid_user')
RABBITMQ_CLOUD_PASSWORD = os.environ.get('RABBITMQ_CLOUD_PASSWORD', 'rfid_password')

MAC_ADDRESS = None


class DualRFIDProducer:
    def __init__(self):
        self.local_conn = None
        self.local_channel = None
        self.cloud_conn = None
        self.cloud_channel = None
        self.mongo_client = None
        self.db = None
        self.queue_name = None
        
    def connect_rabbitmq_local(self):
        """Conecta ao RabbitMQ local"""
        try:
            credentials = pika.PlainCredentials(RABBITMQ_LOCAL_USER, RABBITMQ_LOCAL_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_LOCAL_HOST,
                port=RABBITMQ_LOCAL_PORT,
                credentials=credentials,
                heartbeat=600,
                connection_attempts=3,
                retry_delay=2
            )
            self.local_conn = pika.BlockingConnection(parameters)
            self.local_channel = self.local_conn.channel()
            logger.info(f"✅ RabbitMQ LOCAL conectado: {RABBITMQ_LOCAL_HOST}")
            return True
        except Exception as e:
            logger.error(f"❌ RabbitMQ LOCAL falhou: {e}")
            return False
    
    def connect_rabbitmq_cloud(self):
        """Conecta ao RabbitMQ cloud (opcional)"""
        if not RABBITMQ_CLOUD_HOST:
            logger.info("⚠️ RabbitMQ CLOUD não configurado - modo local apenas")
            return False
            
        try:
            credentials = pika.PlainCredentials(RABBITMQ_CLOUD_USER, RABBITMQ_CLOUD_PASSWORD)
            parameters = pika.ConnectionParameters(
                host=RABBITMQ_CLOUD_HOST,
                port=RABBITMQ_CLOUD_PORT,
                credentials=credentials,
                heartbeat=600,
                connection_attempts=2,
                retry_delay=5
            )
            self.cloud_conn = pika.BlockingConnection(parameters)
            self.cloud_channel = self.cloud_conn.channel()
            logger.info(f"✅ RabbitMQ CLOUD conectado: {RABBITMQ_CLOUD_HOST}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ RabbitMQ CLOUD offline: {e}")
            return False
    
    def connect_mongodb(self):
        """Conecta ao MongoDB local"""
        try:
            self.mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            self.db = self.mongo_client[DB_NAME]
            self.db.admin.command('ping')
            logger.info(f"✅ MongoDB conectado: {MONGO_URL}")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB falhou: {e}")
            return False
    
    def declare_queue(self, mac_address):
        """Declara fila em ambos RabbitMQ"""
        self.queue_name = f"queue_{mac_address.replace(':', '_')}"
        
        if self.local_channel:
            try:
                self.local_channel.queue_declare(queue=self.queue_name, durable=True)
                logger.info(f"✅ Fila LOCAL: {self.queue_name}")
            except Exception as e:
                logger.error(f"❌ Erro fila local: {e}")
        
        if self.cloud_channel:
            try:
                self.cloud_channel.queue_declare(queue=self.queue_name, durable=True)
                logger.info(f"✅ Fila CLOUD: {self.queue_name}")
            except Exception as e:
                logger.warning(f"⚠️ Erro fila cloud: {e}")
    
    def publish_reading(self, reading_data):
        """Publica em todos os destinos disponíveis"""
        message = json.dumps(reading_data)
        results = {'local': False, 'cloud': False, 'mongo': False}
        
        # Publicar LOCAL
        if self.local_channel:
            try:
                self.local_channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=message,
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                results['local'] = True
            except:
                pass
        
        # Publicar CLOUD (se disponível)
        if self.cloud_channel:
            try:
                self.cloud_channel.basic_publish(
                    exchange='',
                    routing_key=self.queue_name,
                    body=message,
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                results['cloud'] = True
            except:
                # Cloud pode estar offline - tentar reconectar depois
                self.cloud_channel = None
                self.cloud_conn = None
        
        # Salvar MongoDB
        if self.db:
            try:
                self.db.rfid_readings.insert_one(reading_data)
                results['mongo'] = True
            except:
                pass
        
        return results
    
    def parse_log_line(self, line):
        """Parse linha do log"""
        try:
            parts = line.strip().split()
            if len(parts) >= 5:
                return {
                    "timestamp": f"{parts[0]} {parts[1]}",
                    "mac_address": parts[2],
                    "epc": parts[3],
                    "antenna": int(parts[4]),
                    "rssi": float(parts[5]),
                    "processed_at": datetime.utcnow().isoformat()
                }
        except:
            pass
        return None
    
    def monitor_log(self):
        """Monitora log e processa leituras"""
        global MAC_ADDRESS
        
        logger.info(f"📖 Monitorando: {LOG_FILE}")
        
        while not os.path.exists(LOG_FILE):
            logger.info("⏳ Aguardando arquivo...")
            time.sleep(5)
        
        with open(LOG_FILE, 'r') as f:
            f.seek(0, 2)
            
            # Tentativas de reconexão cloud
            cloud_retry_counter = 0
            cloud_retry_interval = 60  # 1 minuto
            
            # Monitor de health
            health_check_counter = 0
            health_check_interval = 300  # 5 minutos
            
            while True:
                try:
                    # Tentar reconectar cloud periodicamente
                    if not self.cloud_channel and cloud_retry_counter % cloud_retry_interval == 0:
                        logger.info("🔄 Tentando reconectar RabbitMQ CLOUD...")
                        self.connect_rabbitmq_cloud()
                        if self.cloud_channel and self.queue_name:
                            self.declare_queue(MAC_ADDRESS)
                    
                    # Verificar health dos serviços
                    if health_check_counter % health_check_interval == 0:
                        self.check_services_health()
                    
                    cloud_retry_counter += 1
                    health_check_counter += 1
                    
                    line = f.readline()
                    
                    if line:
                        reading = self.parse_log_line(line)
                        
                        if reading:
                            if MAC_ADDRESS is None:
                                MAC_ADDRESS = reading['mac_address']
                                self.declare_queue(MAC_ADDRESS)
                            
                            results = self.publish_reading(reading)
                            
                            status = []
                            status.append("✅ Local" if results['local'] else "❌ Local")
                            status.append("✅ Cloud" if results['cloud'] else "⚠️ Cloud")
                            status.append("✅ Mongo" if results['mongo'] else "❌ Mongo")
                            
                            logger.info(f"📊 EPC={reading['epc']} | {' | '.join(status)}")
                    else:
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"❌ Erro: {e}")
                    time.sleep(1)
    
    def check_services_health(self):
        """Verifica health dos serviços"""
        status = {
            'local_rabbitmq': bool(self.local_channel),
            'cloud_rabbitmq': bool(self.cloud_channel),
            'mongodb': bool(self.db)
        }
        
        logger.info("🏥 Health Check:")
        logger.info(f"  Local RabbitMQ: {'✅ OK' if status['local_rabbitmq'] else '❌ DOWN'}")
        logger.info(f"  Cloud RabbitMQ: {'✅ OK' if status['cloud_rabbitmq'] else '⚠️ OFFLINE'}")
        logger.info(f"  MongoDB: {'✅ OK' if status['mongodb'] else '❌ DOWN'}")
        
        # Tentar reconectar serviços down
        if not status['local_rabbitmq']:
            logger.warning("⚠️ Local RabbitMQ down - tentando reconectar...")
            self.connect_rabbitmq_local()
        
        if not status['mongodb']:
            logger.warning("⚠️ MongoDB down - tentando reconectar...")
            self.connect_mongodb()
    
    def run(self):
        """Executa producer"""
        logger.info("🚀 RFID Producer - Dual Mode")
        logger.info("=" * 60)
        
        # Conectar serviços
        local_ok = self.connect_rabbitmq_local()
        cloud_ok = self.connect_rabbitmq_cloud()
        mongo_ok = self.connect_mongodb()
        
        if not local_ok and not cloud_ok:
            logger.error("❌ CRÍTICO: Nenhum RabbitMQ disponível!")
            return
        
        if not mongo_ok:
            logger.warning("⚠️ MongoDB offline - backup desabilitado")
        
        logger.info("=" * 60)
        self.monitor_log()


if __name__ == "__main__":
    producer = DualRFIDProducer()
    producer.run()
PRODUCER_EOF

echo -e "${GREEN}✅ Producer atualizado (dual-mode)${NC}"

echo ""
echo "=========================================="
echo "  Criando Serviço Systemd (RFID Reader)"
echo "=========================================="

# Criar serviço systemd para rfid_reader
sudo tee /etc/systemd/system/rfid-reader.service > /dev/null <<EOF
[Unit]
Description=RFID Reader CM710-4
After=network.target

[Service]
Type=simple
User=cpcon
WorkingDirectory=/app/rfid_scripts
ExecStart=/usr/bin/python3 /app/rfid_scripts/rfid_reader.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Ativar serviço
sudo systemctl daemon-reload
sudo systemctl enable rfid-reader

echo -e "${GREEN}✅ Serviço rfid-reader criado${NC}"

echo ""
echo "=========================================="
echo "  Criando Diretórios"
echo "=========================================="

mkdir -p /home/cpcon/cm710-4

echo -e "${GREEN}✅ Diretórios criados${NC}"

echo ""
echo "=========================================="
echo "  Iniciando Serviços Docker"
echo "=========================================="

cd /app/docker
docker-compose up -d

sleep 10

echo ""
echo "=========================================="
echo "  Verificando Status"
echo "=========================================="

docker-compose ps

echo ""
echo "=========================================="
echo -e "${GREEN}  SETUP CONCLUÍDO!${NC}"
echo "=========================================="
echo ""
echo -e "${BLUE}Próximos Passos:${NC}"
echo ""
echo "1. Iniciar leitura RFID:"
echo "   sudo systemctl start rfid-reader"
echo ""
echo "2. Ver logs:"
echo "   sudo journalctl -u rfid-reader -f"
echo "   docker logs -f rfid_producer"
echo ""
echo "3. Testar leituras:"
echo "   tail -f /home/cpcon/cm710-4/cm710-4.log"
echo ""
echo -e "${YELLOW}IMPORTANTE:${NC}"
echo "  - Raspberry configurado para funcionar OFFLINE"
echo "  - Dados salvos localmente se cloud estiver offline"
echo "  - Auto-reconexão cloud a cada 1 minuto"
echo "  - Zero manutenção necessária"
echo ""
echo -e "${GREEN}Sistema pronto para entrega ao cliente!${NC}"
echo ""
